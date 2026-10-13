"""
Gerenciador de armazenamento híbrido: RAM (FIFO para unpinned) e Disco (JSON/Files para pinned)
Replicação da arquitetura ClipboardHistoryBuffer e ClipboardHistoryDataStore de cbdhsvc.dll
"""

import json
import shutil
import threading
from collections import deque
from pathlib import Path
from typing import List, Optional, Dict

from .config import (
    MAX_BUFFER_ITEMS,
    MAX_ITEM_SIZE_BYTES,
    PINNED_DIR,
    PINNED_METADATA_FILE,
    ensure_directories
)
from .models import ClipboardItem, ClipboardFormat

class HybridStorage:
    def __init__(self):
        self._lock = threading.Lock()
        # Buffer circular em memória RAM (FIFO com limite estrito de 25 itens)
        self._unpinned_items: deque[ClipboardItem] = deque()
        # Dicionário de itens fixados (mantidos em RAM para baixa latência e sincronizados em disco)
        self._pinned_items: Dict[str, ClipboardItem] = {}

        ensure_directories()
        self.restore_pinned_items()

    def restore_pinned_items(self):
        """Restaura itens fixados salvos no disco (~/.local/share/winv-clipboard/Pinned/)."""
        with self._lock:
            if not PINNED_METADATA_FILE.exists():
                return

            try:
                raw_json = json.loads(PINNED_METADATA_FILE.read_text(encoding="utf-8"))
                items_dict = raw_json.get("items", {})
                for item_id, item_meta in items_dict.items():
                    item = ClipboardItem.from_metadata_dict(item_id, item_meta, PINNED_DIR)
                    if item:
                        self._pinned_items[item.id] = item
            except Exception as e:
                print(f"[Storage] Erro ao carregar metadata.json de itens fixados: {e}")

    def _sync_pinned_metadata(self):
        """Grava atomicamente o arquivo metadata.json de itens fixados."""
        metadata = {"items": {}}
        for item_id, item in self._pinned_items.items():
            metadata["items"][item_id] = item.to_metadata_dict()

        temp_file = PINNED_DIR / "metadata.json.tmp"
        temp_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        temp_file.replace(PINNED_METADATA_FILE)

    def add_item(self, item: ClipboardItem) -> bool:
        """
        Adiciona um novo item capturado.
        Verifica o limite de tamanho (4 MB) e remove duplicatas no topo.
        """
        if item.size_bytes > MAX_ITEM_SIZE_BYTES:
            print(f"[Storage] Item {item.id} descartado: tamanho ({item.size_bytes}B) excede 4MB.")
            return False

        with self._lock:
            new_hash = item.content_hash

            # Verifica se já está nos itens fixados
            for p_item in self._pinned_items.values():
                if p_item.content_hash == new_hash:
                    return False

            # Verifica duplicata no topo do buffer em RAM
            for existing in list(self._unpinned_items):
                if existing.content_hash == new_hash:
                    self._unpinned_items.remove(existing)
                    break

            # Se atingir o limite de 25 itens, remove o mais antigo (FIFO)
            while len(self._unpinned_items) >= MAX_BUFFER_ITEMS:
                discarded = self._unpinned_items.pop()
                print(f"[Storage] FIFO Expurgo: descartando item volátil {discarded.id}")

            self._unpinned_items.appendleft(item)
            return True

    def pin_item(self, item_id: str) -> bool:
        """Fixa um item, movendo-o para a persistência em disco."""
        with self._lock:
            target_item: Optional[ClipboardItem] = None

            # Localiza no buffer de unpinned
            for item in list(self._unpinned_items):
                if item.id == item_id:
                    target_item = item
                    self._unpinned_items.remove(item)
                    break

            if not target_item:
                return False

            target_item.is_pinned = True
            self._pinned_items[target_item.id] = target_item

            # Persiste os payloads no disco
            item_dir = PINNED_DIR / target_item.id
            item_dir.mkdir(parents=True, exist_ok=True)

            if target_item.format_type == ClipboardFormat.IMAGE and target_item.image_bytes:
                img_path = item_dir / "image.png"
                img_path.write_bytes(target_item.image_bytes)
                target_item.image_path = str(img_path)
            else:
                if target_item.text_content:
                    (item_dir / "content.txt").write_text(target_item.text_content, encoding="utf-8")
                if target_item.html_content:
                    (item_dir / "content.html").write_text(target_item.html_content, encoding="utf-8")

            self._sync_pinned_metadata()
            return True

    def unpin_item(self, item_id: str) -> bool:
        """Desafixa um item, removendo-o do disco e devolvendo ao topo da RAM."""
        with self._lock:
            if item_id not in self._pinned_items:
                return False

            item = self._pinned_items.pop(item_id)
            item.is_pinned = False

            # Remove pasta do disco
            item_dir = PINNED_DIR / item_id
            if item_dir.exists():
                shutil.rmtree(item_dir, ignore_errors=True)

            self._sync_pinned_metadata()

            # Devolve ao topo da RAM, respeitando o limite de 25
            while len(self._unpinned_items) >= MAX_BUFFER_ITEMS:
                self._unpinned_items.pop()

            self._unpinned_items.appendleft(item)
            return True

    def delete_item(self, item_id: str) -> bool:
        """Remove definitivamente um item (da RAM ou do disco se estiver fixado)."""
        with self._lock:
            # Tenta remover do buffer em RAM
            for item in list(self._unpinned_items):
                if item.id == item_id:
                    self._unpinned_items.remove(item)
                    return True

            # Tenta remover dos fixados
            if item_id in self._pinned_items:
                del self._pinned_items[item_id]
                item_dir = PINNED_DIR / item_id
                if item_dir.exists():
                    shutil.rmtree(item_dir, ignore_errors=True)
                self._sync_pinned_metadata()
                return True

            return False

    def clear_unpinned(self):
        """Limpa todo o histórico volátil (RAM), preservando todos os itens fixados."""
        with self._lock:
            self._unpinned_items.clear()
            print("[Storage] Histórico em memória limpo. Itens fixados preservados.")

    def get_all_items(self, search_query: str = "") -> List[ClipboardItem]:
        """
        Retorna a lista combinada de itens:
        Primeiro os itens Fixados (Pinned), depois os itens mais recentes em RAM.
        Permite filtro opcional por termo de busca.
        """
        with self._lock:
            pinned = sorted(self._pinned_items.values(), key=lambda x: x.timestamp, reverse=True)
            unpinned = list(self._unpinned_items)
            combined = pinned + unpinned

            if not search_query:
                return combined

            query = search_query.lower()
            return [
                item for item in combined
                if (item.text_content and query in item.text_content.lower())
            ]
