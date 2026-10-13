"""
Módulo responsável pela renderização dos cards do histórico e injeção de colagem.
"""

from typing import List, Optional
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, Pango, GLib

from ..config import THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_HEIGHT
from ..models import ClipboardItem, ClipboardFormat
from ..tabs import TabError
from .constants import HISTORY_TAB


class CardsMixin:
    """Mixin responsável pela renderização de itens, miniaturas e execução de colagem."""

    def refresh_items(self, search_query: Optional[str] = None):
        """Recria os cards da lista com base nos itens da aba ativa."""
        if search_query is None:
            search_query = self.search_entry.get_text().strip()

        # Limpa cards existentes
        for child in self.cards_box.get_children():
            self.cards_box.remove(child)

        empty_text = "Nenhum item no histórico"
        if self.active_tab is HISTORY_TAB:
            self._current_items = self.storage.get_all_items(search_query)
        else:
            try:
                if self.tabs.is_locked(self.active_tab):
                    self._current_items = []
                    self._render_unlock_view(self.active_tab)
                    return
                else:
                    self._current_items = self.tabs.get_items(self.active_tab, search_query)
                    empty_text = "Aba vazia — use \"+ Novo item\" ou envie\nitens a partir do Histórico"
            except TabError:
                # A aba deixou de existir: volta para o Histórico
                self.active_tab = HISTORY_TAB
                self._update_header()
                self._rebuild_tab_bar()
                self._current_items = self.storage.get_all_items(search_query)

        if not self._current_items:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            empty_box.set_margin_top(40)
            empty_label = Gtk.Label(label=empty_text)
            empty_label.set_justify(Gtk.Justification.CENTER)
            empty_label.get_style_context().add_class("meta-label")
            empty_box.pack_start(empty_label, True, True, 0)
            self.cards_box.pack_start(empty_box, True, True, 0)
            self.cards_box.show_all()
            return

        for item in self._current_items:
            try:
                card = self._create_card(item)
                if card:
                    self.cards_box.pack_start(card, False, False, 0)
            except Exception as e:
                print(f"[UI] Erro ao renderizar card {item.id}: {e}")

        self.cards_box.show_all()

    def _create_card(self, item: ClipboardItem) -> Gtk.Widget:
        event_box = Gtk.EventBox()
        event_box.set_can_focus(True)

        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card_box.get_style_context().add_class("card-item")
        if item.is_pinned:
            card_box.get_style_context().add_class("card-pinned")

        # Conteúdo do Card
        if item.format_type == ClipboardFormat.IMAGE and item.image_bytes:
            try:
                loader = GdkPixbuf.PixbufLoader.new()
                loader.write(item.image_bytes)
                loader.close()
                pixbuf = loader.get_pixbuf()
                if pixbuf:
                    orig_w = pixbuf.get_width()
                    orig_h = pixbuf.get_height()
                    scale = min(THUMBNAIL_MAX_WIDTH / orig_w, THUMBNAIL_MAX_HEIGHT / orig_h, 1.0)
                    scaled_w = max(1, int(orig_w * scale))
                    scaled_h = max(1, int(orig_h * scale))
                    scaled_pixbuf = pixbuf.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)

                    image_widget = Gtk.Image.new_from_pixbuf(scaled_pixbuf)
                    image_widget.set_halign(Gtk.Align.START)
                    card_box.pack_start(image_widget, False, False, 0)
            except Exception as e:
                err_label = Gtk.Label(label=f"[Imagem indisponível: {e}]")
                err_label.set_halign(Gtk.Align.START)
                card_box.pack_start(err_label, False, False, 0)
        else:
            text_preview = item.get_display_text()
            label = Gtk.Label(label=text_preview)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            label.set_max_width_chars(44)
            label.set_xalign(0.0)
            label.get_style_context().add_class("card-text")
            card_box.pack_start(label, False, False, 0)

        # Barra inferior do card: Horário e Botões de Ação (Pin e Delete)
        meta_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        time_label = Gtk.Label(label=f"{item.get_time_display()} • {item.source_app}")
        time_label.get_style_context().add_class("meta-label")
        time_label.set_xalign(0.0)
        meta_row.pack_start(time_label, True, True, 0)

        # Botão Pin
        pin_btn = self._make_icon_button(
            ["view-pin-symbolic", "pin-symbolic", "starred-symbolic"] if item.is_pinned
            else ["view-pin-symbolic", "pin-symbolic", "non-starred-symbolic"],
            "◆" if item.is_pinned else "◇",
        )
        if item.is_pinned:
            pin_btn.get_style_context().add_class("pinned")
        pin_btn.set_tooltip_text("Desafixar" if item.is_pinned else "Fixar item")
        pin_btn.connect("clicked", lambda b, i=item: self._on_toggle_pin(i))
        if self.active_tab is HISTORY_TAB:
            meta_row.pack_end(pin_btn, False, False, 0)

            # Botão Enviar para aba
            send_btn = self._make_icon_button(
                ["mail-send-symbolic", "document-send-symbolic", "go-next-symbolic"], "→"
            )
            send_btn.set_tooltip_text("Enviar para aba...")
            send_btn.connect("clicked", lambda b, i=item: self._show_send_popover(b, i))
            meta_row.pack_end(send_btn, False, False, 0)

        # Botão Delete
        del_btn = self._make_icon_button(
            ["user-trash-symbolic", "edit-delete-symbolic"], "✕"
        )
        del_btn.set_tooltip_text("Excluir item")
        del_btn.connect("clicked", lambda b, i=item: self._on_delete_item(i))
        meta_row.pack_end(del_btn, False, False, 0)

        card_box.pack_start(meta_row, False, False, 0)
        event_box.add(card_box)

        # Clique no card para colar
        event_box.connect("button-press-event", lambda w, e, i=item: self._on_card_clicked(e, i))
        return event_box

    def _make_icon_button(self, icon_names: List[str], fallback: str) -> Gtk.Button:
        """Cria um botão com ícone simbólico monocromático."""
        theme = Gtk.IconTheme.get_default()
        btn = Gtk.Button()
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("action-btn")
        for name in icon_names:
            if theme and theme.has_icon(name):
                btn.set_image(Gtk.Image.new_from_icon_name(name, Gtk.IconSize.MENU))
                btn.set_always_show_image(True)
                return btn
        btn.set_label(fallback)
        return btn

    def _on_toggle_pin(self, item: ClipboardItem):
        if item.is_pinned:
            self.storage.unpin_item(item.id)
        else:
            self.storage.pin_item(item.id)
        self.refresh_items()

    def _on_delete_item(self, item: ClipboardItem):
        if self.active_tab is HISTORY_TAB:
            self.storage.delete_item(item.id)
        else:
            try:
                self.tabs.delete_item(self.active_tab, item.id)
            except TabError as e:
                self._flash_status(str(e))
        self.refresh_items()

    def _on_card_clicked(self, event, item: ClipboardItem):
        if event.button == 1:
            self.execute_paste(item)
            return True
        return False

    def execute_paste(self, item: ClipboardItem):
        """
        Fluxo de injeção de colagem equivalente ao Windows:
        1. Se for item confidencial de Cofre, guarda o clipboard anterior para restauração em 1.5s.
        2. Atualiza o clipboard e marca a flag anti-loop.
        3. Fecha o flyout.
        4. Restaura o foco na janela alvo.
        5. Aguarda e injeta atalho de colagem.
        6. Se for cofre, restaura o clipboard anterior após 1.5s (Anti-Leak).
        """
        is_vault = False
        if self.active_tab is not HISTORY_TAB:
            info = self._active_tab_info()
            if info and info.encrypted:
                is_vault = True
        else:
            found = self.tabs.find_item(item.id)
            if found and found[2]:
                is_vault = True

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        prev_text: Optional[str] = None
        prev_image: Optional[GdkPixbuf.Pixbuf] = None

        if is_vault:
            prev_text = clipboard.wait_for_text()
            if not prev_text:
                prev_image = clipboard.wait_for_image()

        # 1. Marca flag anti-loop com o hash do item
        self.monitor.mark_internal_paste(item.content_hash)

        # Atualiza a seleção do clipboard do sistema
        if item.format_type == ClipboardFormat.IMAGE and item.image_bytes:
            try:
                loader = GdkPixbuf.PixbufLoader.new()
                loader.write(item.image_bytes)
                loader.close()
                pixbuf = loader.get_pixbuf()
                if pixbuf:
                    clipboard.set_image(pixbuf)
                    clipboard.store()
            except Exception as e:
                print(f"[UI] Erro ao colocar imagem no clipboard: {e}")
        else:
            clipboard.set_text(item.text_content or "", -1)
            clipboard.store()

        # 2. Fecha o popup
        self.hide()

        # 3. Restaura foco e injeta colagem em background
        target_xid = self.target_xid
        target_wm_class = self.target_wm_class

        def _do_paste():
            self.x11_helper.restore_focus_and_paste(target_xid, target_wm_class)
            return False

        GLib.timeout_add(15, _do_paste)

        # 4. Anti-Leak: Restauração do Clipboard após 1.5 segundos se for item de cofre
        if is_vault:
            def _restore_clipboard():
                if prev_image is not None:
                    try:
                        ok, img_bytes = prev_image.save_to_bufferv("png", [], [])
                        if ok:
                            img_hash = ClipboardItem(format_type=ClipboardFormat.IMAGE, image_bytes=img_bytes).content_hash
                            self.monitor.mark_internal_paste(img_hash)
                        clipboard.set_image(prev_image)
                        clipboard.store()
                    except Exception as ex:
                        print(f"[UI] Erro ao restaurar imagem anterior: {ex}")
                elif prev_text is not None and prev_text:
                    txt_hash = ClipboardItem(format_type=ClipboardFormat.TEXT, text_content=prev_text).content_hash
                    self.monitor.mark_internal_paste(txt_hash)
                    clipboard.set_text(prev_text, -1)
                    clipboard.store()
                else:
                    clipboard.clear()
                return False

            GLib.timeout_add(1500, _restore_clipboard)
