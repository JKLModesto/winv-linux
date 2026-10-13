"""
Monitor de área de transferência com filtro anti-loop
Replicação do ClipboardMonitor e ExcludeClipboardContentFromMonitorProcessing de cbdhsvc.dll
"""

import time
import threading
from typing import Optional, Set

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from .models import ClipboardItem, ClipboardFormat
from .storage import HybridStorage
from .x11_helper import X11Helper

class ClipboardMonitor:
    def __init__(self, storage: HybridStorage, x11_helper: X11Helper, on_item_added_callback=None):
        self.storage = storage
        self.x11_helper = x11_helper
        self.on_item_added_callback = on_item_added_callback

        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        
        # Filtro Anti-Loop (ExcludeClipboardContentFromMonitorProcessing)
        # Armazena hashes de itens colocados no clipboard pelo próprio winv-mint
        self._internal_paste_hashes: Set[str] = set()
        self._lock = threading.Lock()

        # Conecta ao sinal nativo de alteração de proprietário do X11
        self.clipboard.connect("owner-change", self._on_clipboard_owner_change)

    def mark_internal_paste(self, content_hash: str):
        """
        Registra a flag de colagem interna (ExcludeClipboardContentFromMonitorProcessing).
        Evita que a própria injeção de colagem seja capturada como um novo item pelo monitor.
        """
        with self._lock:
            self._internal_paste_hashes.add(content_hash)

    def _consume_internal_paste(self, content_hash: str) -> bool:
        """Verifica e consome a flag anti-loop."""
        with self._lock:
            if content_hash in self._internal_paste_hashes:
                self._internal_paste_hashes.remove(content_hash)
                return True
            return False

    def _on_clipboard_owner_change(self, clipboard, event):
        """Handler acionado no evento X11 SelectionNotify / owner-change."""
        # Agenda extração no loop principal do GLib
        GLib.idle_add(self._process_clipboard_content)

    def _process_clipboard_content(self):
        try:
            # 1. Verifica se há imagem disponível no clipboard
            if self.clipboard.wait_is_image_available():
                pixbuf = self.clipboard.wait_for_image()
                if pixbuf:
                    success, buffer = pixbuf.save_to_bufferv("png", [], [])
                    if success and buffer:
                        image_bytes = bytes(buffer)
                        item = ClipboardItem(
                            format_type=ClipboardFormat.IMAGE,
                            image_bytes=image_bytes,
                            source_app=self.x11_helper.get_active_window_class()
                        )
                        if self._consume_internal_paste(item.content_hash):
                            return False

                        if self.storage.add_item(item):
                            if self.on_item_added_callback:
                                self.on_item_added_callback(item)
                        return False

            # 2. Verifica se há texto ou HTML disponível
            if self.clipboard.wait_is_text_available():
                text = self.clipboard.wait_for_text()
                if not text or not text.strip():
                    return False

                # Tenta capturar HTML complementar
                html_content = None
                targets = self.clipboard.wait_for_targets()
                if targets:
                    target_names = [target.name() for target in targets[1]]
                    if "text/html" in target_names:
                        html_atom = Gdk.Atom.intern("text/html", False)
                        selection_data = self.clipboard.wait_for_contents(html_atom)
                        if selection_data:
                            html_bytes = selection_data.get_data()
                            if html_bytes:
                                html_content = html_bytes.decode("utf-8", errors="ignore")

                item = ClipboardItem(
                    format_type=ClipboardFormat.HTML if html_content else ClipboardFormat.TEXT,
                    text_content=text,
                    html_content=html_content,
                    source_app=self.x11_helper.get_active_window_class()
                )

                if self._consume_internal_paste(item.content_hash):
                    return False

                if self.storage.add_item(item):
                    if self.on_item_added_callback:
                        self.on_item_added_callback(item)

        except Exception as e:
            print(f"[Monitor] Erro ao processar evento de clipboard: {e}")

        return False
