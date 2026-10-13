"""
Interface gráfica do Flyout de Histórico de Clipboard (GTK 3 / X11)
Estilização inspirada no Fluent Design do Windows 11, frameless, cantos arredondados,
suporte a Dual-Monitor e baixa latência através de pré-carregamento.
"""

from typing import Optional, List
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio

from .config import (
    POPUP_WIDTH,
    POPUP_MAX_HEIGHT,
    SCREEN_PADDING,
    THUMBNAIL_MAX_WIDTH,
    THUMBNAIL_MAX_HEIGHT
)
from .models import ClipboardItem, ClipboardFormat
from .storage import HybridStorage
from .x11_helper import X11Helper

CSS_STYLES = """
window.winv-popup {
    background-color: rgba(30, 30, 30, 0.96);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
}

.header-box {
    padding: 12px 14px 8px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.title-label {
    font-size: 13px;
    font-weight: bold;
    color: #e0e0e0;
}

.clear-btn {
    font-size: 11px;
    color: #a0a0a0;
    background: transparent;
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}
.clear-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}

.search-entry {
    background-color: rgba(45, 45, 45, 0.9);
    color: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
    margin-top: 6px;
}
.search-entry:focus {
    border-color: #0078d4;
}

.cards-scroller {
    padding: 8px 10px;
}

.card-item {
    background-color: rgba(44, 44, 44, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
    transition: all 120ms ease;
}
.card-item:hover, .card-item:focus {
    background-color: rgba(58, 58, 58, 0.98);
    border-color: #0078d4;
}

.card-pinned {
    border-left: 3px solid #0078d4;
}

.card-text {
    font-size: 12px;
    color: #f0f0f0;
    line-height: 1.35;
}

.meta-label {
    font-size: 10px;
    color: #888888;
}

.action-btn {
    background: transparent;
    border: none;
    padding: 4px;
    border-radius: 4px;
    color: #a0a0a0;
}
.action-btn:hover {
    background-color: rgba(255, 255, 255, 0.1);
    color: #ffffff;
}
.action-btn.pinned {
    color: #0078d4;
}
"""

class ClipboardFlyoutWindow(Gtk.Window):
    def __init__(self, storage: HybridStorage, x11_helper: X11Helper, monitor):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.storage = storage
        self.x11_helper = x11_helper
        self.monitor = monitor

        self.target_xid: Optional[int] = None
        self.target_wm_class: str = "Unknown"
        self._current_items: List[ClipboardItem] = []

        self._setup_window_properties()
        self._setup_css()
        self._build_ui()

        # Oculta imediatamente após a inicialização (Pré-carregado em background)
        self.hide()

    def _setup_window_properties(self):
        """Configura a janela como popup frameless Always-On-Top."""
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
        self.set_default_size(POPUP_WIDTH, POPUP_MAX_HEIGHT)
        self.set_name("winv-popup")
        self.get_style_context().add_class("winv-popup")

        # Habilita suporte a transparência RGBA
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)

        # Eventos para fechar ao perder foco ou apertar ESC
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("key-press-event", self._on_key_press)

    def _setup_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_STYLES.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def _build_ui(self):
        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root_box)

        # 1. Header com Título, Botão Limpar Tudo e Barra de Busca
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        header_box.get_style_context().add_class("header-box")

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        title_label = Gtk.Label(label="Área de Transferência")
        title_label.set_xalign(0.0)
        title_label.get_style_context().add_class("title-label")
        top_row.pack_start(title_label, True, True, 0)

        clear_btn = Gtk.Button(label="Limpar tudo")
        clear_btn.get_style_context().add_class("clear-btn")
        clear_btn.connect("clicked", self._on_clear_all_clicked)
        top_row.pack_end(clear_btn, False, False, 0)
        header_box.pack_start(top_row, False, False, 0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Pesquisar no histórico...")
        self.search_entry.get_style_context().add_class("search-entry")
        self.search_entry.connect("changed", self._on_search_changed)
        header_box.pack_start(self.search_entry, False, False, 0)
        root_box.pack_start(header_box, False, False, 0)

        # 2. Lista Rolável de Cards
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.get_style_context().add_class("cards-scroller")
        
        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.scroller.add(self.cards_box)
        root_box.pack_start(self.scroller, True, True, 0)

    def _on_clear_all_clicked(self, widget):
        self.storage.clear_unpinned()
        self.refresh_items()

    def _on_search_changed(self, entry):
        query = entry.get_text().strip()
        self.refresh_items(search_query=query)

    def _on_focus_out(self, widget, event):
        self.hide()
        return True

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def position_at_pointer(self):
        """
        Calcula a posição exata de abertura considerando setups Dual-Monitor
        e área útil da tela (respeitando o painel do Cinnamon e bordas com padding).
        """
        display = Gdk.Display.get_default()
        if not display:
            return

        seat = display.get_default_seat()
        pointer = seat.get_pointer() if seat else None
        if not pointer:
            return

        screen, cursor_x, cursor_y = pointer.get_position()
        monitor = display.get_monitor_at_point(cursor_x, cursor_y)
        if not monitor:
            monitor = display.get_primary_monitor() or display.get_monitor(0)

        workarea = monitor.get_workarea()
        popup_w = POPUP_WIDTH
        popup_h = min(POPUP_MAX_HEIGHT, workarea.height - (SCREEN_PADDING * 2))

        # Posicionamento Vertical: tenta abaixo do cursor primeiro
        target_y = cursor_y + 12
        if (target_y + popup_h) > (workarea.y + workarea.height - SCREEN_PADDING):
            # Inverte para cima se ultrapassar a borda inferior
            target_y = cursor_y - popup_h - 12

        # Clamp vertical
        if target_y < workarea.y + SCREEN_PADDING:
            target_y = workarea.y + SCREEN_PADDING

        # Posicionamento Horizontal
        target_x = cursor_x
        if (target_x + popup_w) > (workarea.x + workarea.width - SCREEN_PADDING):
            target_x = workarea.x + workarea.width - popup_w - SCREEN_PADDING

        # Clamp horizontal
        if target_x < workarea.x + SCREEN_PADDING:
            target_x = workarea.x + SCREEN_PADDING

        self.move(int(target_x), int(target_y))

    def show_flyout(self, target_xid: Optional[int], target_wm_class: str):
        """Abre o flyout instantaneamente com os itens atualizados."""
        self.target_xid = target_xid
        self.target_wm_class = target_wm_class

        self.search_entry.set_text("")
        self.refresh_items()
        self.position_at_pointer()

        self.show_all()
        self.present()
        self.search_entry.grab_focus()

    def refresh_items(self, search_query: str = ""):
        """Recria os cards da lista com base nos itens do storage."""
        # Limpa cards existentes
        for child in self.cards_box.get_children():
            self.cards_box.remove(child)

        self._current_items = self.storage.get_all_items(search_query)

        if not self._current_items:
            empty_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            empty_box.set_margin_top(40)
            empty_label = Gtk.Label(label="Nenhum item no histórico")
            empty_label.get_style_context().add_class("meta-label")
            empty_box.pack_start(empty_label, True, True, 0)
            self.cards_box.pack_start(empty_box, True, True, 0)
            self.cards_box.show_all()
            return

        for item in self._current_items:
            card = self._create_card(item)
            self.cards_box.pack_start(card, False, False, 0)

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
                loader = GdkPixbuf.PixbufLoader.new_with_type("png")
                loader.write(item.image_bytes)
                loader.close()
                pixbuf = loader.get_pixbuf()
                if pixbuf:
                    # Redimensiona mantendo proporção
                    orig_w = pixbuf.get_width()
                    orig_h = pixbuf.get_height()
                    scale = min(THUMBNAIL_MAX_WIDTH / orig_w, THUMBNAIL_MAX_HEIGHT / orig_h, 1.0)
                    scaled_w = int(orig_w * scale)
                    scaled_h = int(orig_h * scale)
                    scaled_pixbuf = pixbuf.scale_simple(scaled_w, scaled_h, GdkPixbuf.InterpType.BILINEAR)

                    image_widget = Gtk.Image.new_from_pixbuf(scaled_pixbuf)
                    image_widget.set_xalign(0.0)
                    card_box.pack_start(image_widget, False, False, 0)
            except Exception as e:
                err_label = Gtk.Label(label=f"[Imagem indisponível: {e}]")
                card_box.pack_start(err_label, False, False, 0)
        else:
            text_preview = item.get_display_text()
            label = Gtk.Label(label=text_preview)
            label.set_line_wrap(True)
            label.set_line_wrap_mode(3)  # PANGO_WRAP_WORD_CHAR
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
        pin_btn = Gtk.Button(label="📌" if item.is_pinned else "📍")
        pin_btn.get_style_context().add_class("action-btn")
        if item.is_pinned:
            pin_btn.get_style_context().add_class("pinned")
        pin_btn.set_tooltip_text("Desafixar" if item.is_pinned else "Fixar item")
        pin_btn.connect("clicked", lambda b, i=item: self._on_toggle_pin(i))
        meta_row.pack_end(pin_btn, False, False, 0)

        # Botão Delete
        del_btn = Gtk.Button(label="🗑️")
        del_btn.get_style_context().add_class("action-btn")
        del_btn.set_tooltip_text("Excluir item")
        del_btn.connect("clicked", lambda b, i=item: self._on_delete_item(i))
        meta_row.pack_end(del_btn, False, False, 0)

        card_box.pack_start(meta_row, False, False, 0)
        event_box.add(card_box)

        # Clique no card para colar
        event_box.connect("button-press-event", lambda w, e, i=item: self._on_card_clicked(e, i))
        return event_box

    def _on_toggle_pin(self, item: ClipboardItem):
        if item.is_pinned:
            self.storage.unpin_item(item.id)
        else:
            self.storage.pin_item(item.id)
        self.refresh_items()

    def _on_delete_item(self, item: ClipboardItem):
        self.storage.delete_item(item.id)
        self.refresh_items()

    def _on_card_clicked(self, event, item: ClipboardItem):
        if event.button == 1:  # Botão esquerdo
            self.execute_paste(item)
            return True
        return False

    def execute_paste(self, item: ClipboardItem):
        """
        Fluxo de injeção de colagem equivalente ao Windows:
        1. Atualiza o clipboard e marca a flag anti-loop.
        2. Fecha o flyout.
        3. Restaura o foco na janela alvo.
        4. Aguarda 25ms e injeta Ctrl+V (ou Ctrl+Shift+V se for terminal).
        """
        # 1. Marca flag anti-loop com o hash do item
        self.monitor.mark_internal_paste(item.content_hash)

        # Atualiza a seleção do clipboard do sistema
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        if item.format_type == ClipboardFormat.IMAGE and item.image_bytes:
            try:
                loader = GdkPixbuf.PixbufLoader.new_with_type("png")
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

        # 3. Restaura foco e injeta colagem em background para não travar o loop de UI
        target_xid = self.target_xid
        target_wm_class = self.target_wm_class

        def _do_paste():
            self.x11_helper.restore_focus_and_paste(target_xid, target_wm_class)
            return False

        GLib.timeout_add(15, _do_paste)
