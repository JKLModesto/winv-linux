"""
Gerenciador de Abas Persistentes e Abas Cofre do winv-linux.

A aba "Histórico" continua sendo responsabilidade do HybridStorage; este módulo
gerencia apenas as abas criadas pelo usuário.

Layout em disco (BASE/Tabs):
  index.json                      {"order": [tab_id, ...]}
  <tab_id>/tab_meta.json          {"id", "name", "encrypted", ["vault" header]}
  <tab_id>/items.json             (aba normal)  lista de itens; texto inline
  <tab_id>/<item_id>.png          (aba normal)  imagens
  <tab_id>/vault.enc              (aba cofre)   TODOS os itens num único blob cifrado

Este módulo não depende de GTK/GLib (é testável isoladamente). O timer de
auto-lock é disparado externamente chamando check_autolock() periodicamente.
"""

import base64
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import crypto
from .config import MAX_ITEM_SIZE_BYTES
from .models import ClipboardItem, ClipboardFormat

AUTOLOCK_SECONDS = 5 * 60


class TabError(Exception):
    """Operação inválida sobre uma aba (inexistente, trancada, etc.)."""


class TabInfo:
    """Visão somente-leitura de uma aba, para a UI."""

    def __init__(self, tab_id: str, name: str, encrypted: bool, locked: bool, count: Optional[int]):
        self.id = tab_id
        self.name = name
        self.encrypted = encrypted
        self.locked = locked
        self.count = count  # None quando trancada (quantidade não é revelada)

    def __repr__(self):
        return f"TabInfo({self.name!r}, encrypted={self.encrypted}, locked={self.locked})"


class _Tab:
    def __init__(self, tab_id: str, name: str, encrypted: bool, header: Optional[dict] = None):
        self.id = tab_id
        self.name = name
        self.encrypted = encrypted
        self.header = header
        self.items: List[ClipboardItem] = []
        self.key: Optional[crypto.VaultKey] = None
        self.last_used = 0.0

    @property
    def locked(self) -> bool:
        return self.encrypted and self.key is None


# ------------------------------------------------------------------------------
# Serialização de itens
# ------------------------------------------------------------------------------
def _item_to_dict(item: ClipboardItem, inline_image: bool) -> dict:
    d = {
        "id": item.id,
        "format": item.format_type,
        "timestamp": item.timestamp,
        "source": item.source_app,
        "text": item.text_content,
        "html": item.html_content,
    }
    if inline_image and item.image_bytes:
        d["image_b64"] = base64.b64encode(item.image_bytes).decode("ascii")
    return d


def _item_from_dict(d: dict, image_bytes: Optional[bytes] = None) -> ClipboardItem:
    if image_bytes is None and d.get("image_b64"):
        image_bytes = base64.b64decode(d["image_b64"])
    return ClipboardItem(
        item_id=d["id"],
        format_type=d.get("format", ClipboardFormat.TEXT),
        text_content=d.get("text"),
        html_content=d.get("html"),
        image_bytes=image_bytes,
        timestamp=d.get("timestamp"),
        is_pinned=False,
        source_app=d.get("source", "Local"),
    )


def _clone_item(item: ClipboardItem) -> ClipboardItem:
    """Cópia independente, com novo id, para não compartilhar estado com o Histórico."""
    return ClipboardItem(
        format_type=item.format_type,
        text_content=item.text_content,
        html_content=item.html_content,
        image_bytes=item.image_bytes,
        source_app=item.source_app,
    )


def _atomic_write(path: Path, data: bytes):
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# ------------------------------------------------------------------------------
# TabManager
# ------------------------------------------------------------------------------
class TabManager:
    def __init__(self, base_dir: Path, autolock_seconds: float = AUTOLOCK_SECONDS,
                 clock: Callable[[], float] = time.monotonic,
                 scrypt_params: Optional[dict] = None):
        self.base_dir = Path(base_dir)
        self.autolock_seconds = autolock_seconds
        self._clock = clock
        self._scrypt = scrypt_params or {}
        self._lock = threading.RLock()
        self._tabs: Dict[str, _Tab] = {}
        self._order: List[str] = []

        self.base_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.base_dir, 0o700)
        self._load()

    # ---------------------------------------------------------------- disco
    def _tab_dir(self, tab_id: str) -> Path:
        return self.base_dir / tab_id

    def _load(self):
        index_file = self.base_dir / "index.json"
        order = []
        if index_file.exists():
            try:
                order = json.loads(index_file.read_text("utf-8")).get("order", [])
            except Exception as e:
                print(f"[Tabs] index.json inválido: {e}")

        # Inclui abas presentes em disco mas ausentes do índice (recuperação)
        on_disk = sorted(p.name for p in self.base_dir.iterdir()
                         if p.is_dir() and (p / "tab_meta.json").exists())
        order = [t for t in order if t in on_disk] + [t for t in on_disk if t not in order]

        for tab_id in order:
            try:
                meta = json.loads((self._tab_dir(tab_id) / "tab_meta.json").read_text("utf-8"))
                tab = _Tab(tab_id, meta["name"], bool(meta.get("encrypted")), meta.get("vault"))
                if not tab.encrypted:
                    self._load_plain_items(tab)
                self._tabs[tab_id] = tab
                self._order.append(tab_id)
            except Exception as e:
                print(f"[Tabs] Falha ao carregar aba {tab_id}: {e}")

    def _load_plain_items(self, tab: _Tab):
        items_file = self._tab_dir(tab.id) / "items.json"
        if not items_file.exists():
            return
        for d in json.loads(items_file.read_text("utf-8")):
            img = None
            if d.get("format") == ClipboardFormat.IMAGE:
                img_file = self._tab_dir(tab.id) / f"{d['id']}.png"
                if not img_file.exists():
                    continue
                img = img_file.read_bytes()
            tab.items.append(_item_from_dict(d, img))

    def _save_index(self):
        _atomic_write(self.base_dir / "index.json",
                      json.dumps({"order": self._order}).encode("utf-8"))

    def _save_meta(self, tab: _Tab):
        d = self._tab_dir(tab.id)
        d.mkdir(mode=0o700, exist_ok=True)
        meta = {"id": tab.id, "name": tab.name, "encrypted": tab.encrypted}
        if tab.encrypted:
            meta["vault"] = tab.header
        _atomic_write(d / "tab_meta.json", json.dumps(meta, indent=2).encode("utf-8"))

    def _save_items(self, tab: _Tab):
        d = self._tab_dir(tab.id)
        if tab.encrypted:
            if tab.key is None:
                raise TabError("Aba trancada")
            payload = {"items": [_item_to_dict(i, inline_image=True) for i in tab.items]}
            _atomic_write(d / "vault.enc", crypto.encrypt_vault_payload(tab.key, tab.id, payload))
            return

        keep = set()
        for item in tab.items:
            if item.format_type == ClipboardFormat.IMAGE and item.image_bytes:
                img_file = d / f"{item.id}.png"
                keep.add(img_file.name)
                if not img_file.exists():
                    _atomic_write(img_file, item.image_bytes)
        for f in d.glob("*.png"):
            if f.name not in keep:
                f.unlink(missing_ok=True)
        data = [_item_to_dict(i, inline_image=False) for i in tab.items]
        _atomic_write(d / "items.json", json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))

    # ---------------------------------------------------------------- helpers
    def _get(self, tab_id: str) -> _Tab:
        tab = self._tabs.get(tab_id)
        if tab is None:
            raise TabError(f"Aba inexistente: {tab_id}")
        return tab

    def _get_unlocked(self, tab_id: str) -> _Tab:
        tab = self._get(tab_id)
        if tab.locked:
            raise TabError("Aba trancada")
        tab.last_used = self._clock()
        return tab

    # ---------------------------------------------------------------- abas
    def list_tabs(self) -> List[TabInfo]:
        with self._lock:
            return [TabInfo(t.id, t.name, t.encrypted, t.locked,
                            None if t.locked else len(t.items))
                    for t in (self._tabs[i] for i in self._order)]

    def create_tab(self, name: str, password: Optional[str] = None) -> str:
        name = (name or "").strip()
        if not name:
            raise TabError("O nome da aba não pode ser vazio")
        with self._lock:
            tab_id = uuid.uuid4().hex
            if password:
                header, key = crypto.create_vault_header(tab_id, password, **self._scrypt)
                tab = _Tab(tab_id, name, True, header)
                tab.key = key
                tab.last_used = self._clock()
            else:
                tab = _Tab(tab_id, name, False)
            self._save_meta(tab)
            self._save_items(tab)
            self._tabs[tab_id] = tab
            self._order.append(tab_id)
            self._save_index()
            return tab_id

    def rename_tab(self, tab_id: str, new_name: str):
        new_name = (new_name or "").strip()
        if not new_name:
            raise TabError("O nome da aba não pode ser vazio")
        with self._lock:
            tab = self._get(tab_id)
            tab.name = new_name
            self._save_meta(tab)

    def delete_tab(self, tab_id: str):
        with self._lock:
            tab = self._get(tab_id)
            if tab.key:
                tab.key.wipe()
            tab.items.clear()
            del self._tabs[tab_id]
            self._order.remove(tab_id)
            shutil.rmtree(self._tab_dir(tab_id), ignore_errors=True)
            self._save_index()

    def move_tab(self, tab_id: str, new_index: int):
        with self._lock:
            self._get(tab_id)
            self._order.remove(tab_id)
            new_index = max(0, min(new_index, len(self._order)))
            self._order.insert(new_index, tab_id)
            self._save_index()

    # ---------------------------------------------------------------- itens
    def get_items(self, tab_id: str, search_query: str = "") -> List[ClipboardItem]:
        with self._lock:
            tab = self._get_unlocked(tab_id)
            items = list(tab.items)
        if not search_query:
            return items
        q = search_query.lower()
        return [i for i in items if i.text_content and q in i.text_content.lower()]

    def add_item(self, tab_id: str, item: ClipboardItem) -> bool:
        """Adiciona uma cópia do item no topo da aba. Duplicatas sobem para o topo."""
        if item.size_bytes > MAX_ITEM_SIZE_BYTES:
            return False
        with self._lock:
            tab = self._get_unlocked(tab_id)
            h = item.content_hash
            tab.items = [i for i in tab.items if i.content_hash != h]
            tab.items.insert(0, _clone_item(item))
            self._save_items(tab)
            return True

    def add_text(self, tab_id: str, text: str) -> bool:
        if not text or not text.strip():
            return False
        return self.add_item(tab_id, ClipboardItem(format_type=ClipboardFormat.TEXT,
                                                   text_content=text, source_app="Manual"))

    def delete_item(self, tab_id: str, item_id: str) -> bool:
        with self._lock:
            tab = self._get_unlocked(tab_id)
            before = len(tab.items)
            tab.items = [i for i in tab.items if i.id != item_id]
            if len(tab.items) == before:
                return False
            self._save_items(tab)
            return True

    def find_item(self, item_id: str):
        """Localiza um item em abas destrancadas. Retorna (tab_id, item, encrypted) ou None."""
        with self._lock:
            for tab in self._tabs.values():
                if tab.locked:
                    continue
                for i in tab.items:
                    if i.id == item_id:
                        return tab.id, i, tab.encrypted
        return None

    # ---------------------------------------------------------------- cofre
    def is_locked(self, tab_id: str) -> bool:
        with self._lock:
            return self._get(tab_id).locked

    def unlock(self, tab_id: str, password: str):
        """Destranca a aba. Lança crypto.InvalidPassword se a senha estiver errada."""
        with self._lock:
            tab = self._get(tab_id)
            if not tab.encrypted or tab.key is not None:
                tab.last_used = self._clock()
                return
            header = tab.header
        # A derivação (~0,4 s) roda fora do lock para não travar outras operações
        key = crypto.unlock_vault(tab_id, header, password)
        vault_file = self._tab_dir(tab_id) / "vault.enc"
        try:
            payload = crypto.decrypt_vault_payload(key, tab_id, vault_file.read_bytes()) \
                if vault_file.exists() else {"items": []}
        except Exception:
            key.wipe()
            raise
        with self._lock:
            tab.items = [_item_from_dict(d) for d in payload.get("items", [])]
            tab.key = key
            tab.last_used = self._clock()

    def lock(self, tab_id: str):
        with self._lock:
            tab = self._get(tab_id)
            if not tab.encrypted:
                return
            if tab.key:
                tab.key.wipe()
            tab.key = None
            tab.items = []

    def lock_all(self):
        with self._lock:
            for tab_id in list(self._tabs):
                self.lock(tab_id)

    def touch(self, tab_id: str):
        """Registra uso da aba (renova o prazo do auto-lock)."""
        with self._lock:
            tab = self._tabs.get(tab_id)
            if tab:
                tab.last_used = self._clock()

    def check_autolock(self) -> List[str]:
        """Tranca cofres inativos há mais de autolock_seconds. Retorna os ids trancados."""
        now = self._clock()
        locked = []
        with self._lock:
            for tab in self._tabs.values():
                if tab.encrypted and tab.key is not None and now - tab.last_used >= self.autolock_seconds:
                    self.lock(tab.id)
                    locked.append(tab.id)
        return locked
