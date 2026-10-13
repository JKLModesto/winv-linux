"""
Modelos de dados e serialização de itens do histórico de clipboard
"""

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional, List

class ClipboardFormat:
    TEXT = "text"
    HTML = "html"
    IMAGE = "image"

class ClipboardItem:
    def __init__(
        self,
        item_id: Optional[str] = None,
        format_type: str = ClipboardFormat.TEXT,
        text_content: Optional[str] = None,
        html_content: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        image_path: Optional[str] = None,
        timestamp: Optional[str] = None,
        is_pinned: bool = False,
        source_app: str = "Unknown",
        size_bytes: int = 0
    ):
        self.id = item_id or str(uuid.uuid4())
        self.format_type = format_type
        self.text_content = text_content
        self.html_content = html_content
        self.image_bytes = image_bytes
        self.image_path = image_path
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.is_pinned = is_pinned
        self.source_app = source_app

        # Cálculo do tamanho do item em bytes
        if size_bytes > 0:
            self.size_bytes = size_bytes
        elif self.image_bytes is not None:
            self.size_bytes = len(self.image_bytes)
        elif self.text_content is not None:
            self.size_bytes = len(self.text_content.encode("utf-8", errors="ignore"))
            if self.html_content:
                self.size_bytes += len(self.html_content.encode("utf-8", errors="ignore"))
        else:
            self.size_bytes = 0

    @property
    def content_hash(self) -> str:
        """Gera um hash SHA-256 para verificação de duplicidade e controle anti-loop."""
        # TEXT e HTML compartilham o mesmo "domínio" de hash: o conteúdo visível
        # é o que importa. Apps como o Chrome publicam text/plain e depois
        # text/html para a mesma cópia, o que antes gerava itens duplicados.
        hasher = hashlib.sha256()
        if self.format_type == ClipboardFormat.IMAGE and self.image_bytes:
            hasher.update(b"image:")
            hasher.update(self.image_bytes)
        elif self.text_content:
            normalized = self.text_content.replace("\r\n", "\n").replace("\r", "\n").strip()
            hasher.update(b"text:")
            hasher.update(normalized.encode("utf-8", errors="ignore"))
        return hasher.hexdigest()

    def get_display_text(self, max_chars: int = 240) -> str:
        """Retorna uma prévia de texto limpa para renderização no card."""
        if self.format_type == ClipboardFormat.IMAGE:
            return "Imagem da Área de Transferência"
        if not self.text_content:
            return ""
        # Normaliza quebras de linha múltiplas para exibição compacta
        lines = [line.strip() for line in self.text_content.splitlines() if line.strip()]
        preview = "\n".join(lines[:4])
        if len(preview) > max_chars:
            preview = preview[:max_chars].rstrip() + "..."
        return preview

    def get_time_display(self) -> str:
        """Retorna hora formatada no padrão local HH:MM."""
        try:
            dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            return local_dt.strftime("%H:%M")
        except Exception:
            return ""

    def to_metadata_dict(self) -> dict:
        """Serializa o item no formato exato descoberto no metadata.json do Windows."""
        return {
            "timestamp": self.timestamp,
            "source": self.source_app,
            "format": self.format_type,
            "size_bytes": self.size_bytes,
            "cloud_id": None,
            "EnterpriseId": None
        }

    @classmethod
    def from_metadata_dict(cls, item_id: str, data: dict, payload_dir) -> Optional["ClipboardItem"]:
        """Reconstrói um ClipboardItem a partir do metadata.json e seus arquivos de disco."""
        fmt = data.get("format", ClipboardFormat.TEXT)
        timestamp = data.get("timestamp")
        source = data.get("source", "Local")
        size_bytes = data.get("size_bytes", 0)

        item_dir = payload_dir / item_id
        if not item_dir.exists():
            return None

        text_content = None
        html_content = None
        image_bytes = None
        image_path = None

        if fmt == ClipboardFormat.IMAGE:
            img_file = item_dir / "image.png"
            if img_file.exists():
                image_bytes = img_file.read_bytes()
                image_path = str(img_file)
            else:
                return None
        else:
            txt_file = item_dir / "content.txt"
            if txt_file.exists():
                text_content = txt_file.read_text(encoding="utf-8", errors="ignore")
            html_file = item_dir / "content.html"
            if html_file.exists():
                html_content = html_file.read_text(encoding="utf-8", errors="ignore")

        return cls(
            item_id=item_id,
            format_type=fmt,
            text_content=text_content,
            html_content=html_content,
            image_bytes=image_bytes,
            image_path=image_path,
            timestamp=timestamp,
            is_pinned=True,
            source_app=source,
            size_bytes=size_bytes
        )
