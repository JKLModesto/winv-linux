"""
Interface gráfica do Flyout de Histórico de Clipboard (GTK 3 / X11)
Estilização inspirada no Fluent Design do Windows 11, frameless, cantos arredondados,
suporte a Dual-Monitor e baixa latência através de pré-carregamento.
"""

import subprocess
from typing import Optional, List
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Gio, Pango

from .config import (
    POPUP_WIDTH,
    POPUP_MAX_HEIGHT,
    SCREEN_PADDING,
    THUMBNAIL_MAX_WIDTH,
    THUMBNAIL_MAX_HEIGHT
)
from .models import ClipboardItem, ClipboardFormat
from .storage import HybridStorage
from .tabs import TabManager, TabError
from .crypto import InvalidPassword
from .x11_helper import X11Helper

HISTORY_TAB = None  # A aba Histórico é representada por None

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
    color: #ffffff;
}
.action-btn image {
    -gtk-icon-shadow: none;
}

.tab-bar {
    margin-top: 4px;
}
.tab-btn {
    font-size: 11px;
    color: #9a9a9a;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 3px 8px;
    box-shadow: none;
}
.tab-btn:hover {
    color: #ffffff;
}
.tab-btn.tab-active {
    color: #ffffff;
    border-bottom-color: #ffffff;
}
.status-label {
    font-size: 10px;
    color: #bdbdbd;
    margin-right: 6px;
}

popover {
    background-color: #2b2b2b;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
}
.popover-box {
    padding: 8px;
}
.popover-title {
    font-size: 11px;
    font-weight: bold;
    color: #d0d0d0;
}
.menu-btn {
    font-size: 12px;
    color: #e0e0e0;
    background: transparent;
    border: none;
    border-radius: 4px;
    padding: 4px 8px;
    box-shadow: none;
}
.menu-btn:hover {
    background-color: rgba(255, 255, 255, 0.08);
}
.menu-btn:disabled {
    color: #666666;
}
.danger-btn:hover {
    background-color: rgba(255, 255, 255, 0.14);
    color: #ffffff;
}
.error-label {
    font-size: 10px;
    color: #e0e0e0;
}
.unlock-box {
    padding: 30px 20px;
}
.unlock-title {
    font-size: 13px;
    font-weight: bold;
    color: #ffffff;
    margin-top: 8px;
}
.unlock-subtitle {
    font-size: 11px;
    color: #8e8e8e;
    margin-bottom: 12px;
}
.primary-btn {
    background-color: #0078d4;
    color: #ffffff;
    font-size: 12px;
    font-weight: bold;
    border-radius: 6px;
    border: none;
    padding: 6px 12px;
    margin-top: 4px;
}
.primary-btn:hover {
    background-color: #1084d9;
}
.checkbox-label {
    font-size: 11px;
    color: #cccccc;
}
textview, textview text {
    background-color: rgba(45, 45, 45, 0.9);
    color: #ffffff;
    font-size: 12px;
}
"""

class ClipboardFlyoutWindow(Gtk.Window):
    def __init__(self, storage: HybridStorage, x11_helper: X11Helper, monitor, tabs: TabManager):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.storage = storage
        self.x11_helper = x11_helper
        self.monitor = monitor
        self.tabs = tabs

        self.target_xid: Optional[int] = None
        self.target_wm_class: str = "Unknown"
        self._current_items: List[ClipboardItem] = []
        self._can_close_on_focus_out: bool = False
        self.active_tab: Optional[str] = HISTORY_TAB
        self._open_popover: Optional[Gtk.Popover] = None
        self._status_timer: Optional[int] = None

        self._setup_window_properties()
        self._setup_css()
        self._build_ui()

        # Oculta imediatamente após a inicialização (Pré-carregado em background)
        self.hide()

    def _setup_window_properties(self):
        """Configura a janela como popup frameless Always-On-Top com foco ativo."""
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_can_focus(True)
        self.set_focus_on_map(True)
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

        # Botão de ação contextual: "Limpar tudo" no Histórico, "+ Novo item" nas abas
        self.action_btn = Gtk.Button(label="Limpar tudo")
        self.action_btn.get_style_context().add_class("clear-btn")
        self.action_btn.connect("clicked", self._on_action_clicked)
        top_row.pack_end(self.action_btn, False, False, 0)

        self.status_label = Gtk.Label(label="")
        self.status_label.get_style_context().add_class("status-label")
        top_row.pack_end(self.status_label, False, False, 0)
        header_box.pack_start(top_row, False, False, 0)

        # Barra de abas
        tab_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        tab_row.get_style_context().add_class("tab-bar")
        tabs_scroller = Gtk.ScrolledWindow()
        tabs_scroller.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        tabs_scroller.set_propagate_natural_height(True)
        self.tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        tabs_scroller.add(self.tabs_box)
        tab_row.pack_start(tabs_scroller, True, True, 0)

        self.add_tab_btn = self._make_icon_button(["list-add-symbolic"], "+")
        self.add_tab_btn.set_tooltip_text("Nova aba")
        self.add_tab_btn.connect("clicked", lambda b: self._show_create_tab_popover())
        tab_row.pack_end(self.add_tab_btn, False, False, 0)
        header_box.pack_start(tab_row, False, False, 0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Pesquisar no histórico...")
        self.search_entry.get_style_context().add_class("search-entry")
        self.search_entry.connect("changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        header_box.pack_start(self.search_entry, False, False, 0)
        root_box.pack_start(header_box, False, False, 0)

        # 2. Lista Rolável de Cards
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.get_style_context().add_class("cards-scroller")
        
        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.scroller.add(self.cards_box)
        root_box.pack_start(self.scroller, True, True, 0)

        self._rebuild_tab_bar()

    # ------------------------------------------------------------------ abas
    def _tab_order(self) -> List[Optional[str]]:
        return [HISTORY_TAB] + [t.id for t in self.tabs.list_tabs()]

    def _rebuild_tab_bar(self):
        for child in self.tabs_box.get_children():
            self.tabs_box.remove(child)

        entries = [(HISTORY_TAB, "Histórico", None)]
        for t in self.tabs.list_tabs():
            icon = None
            if t.encrypted:
                icon = "changes-prevent-symbolic" if t.locked else "changes-allow-symbolic"
            entries.append((t.id, t.name, icon))

        for tab_id, name, icon in entries:
            btn = Gtk.Button()
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.get_style_context().add_class("tab-btn")
            if tab_id == self.active_tab:
                btn.get_style_context().add_class("tab-active")
            inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            if icon:
                inner.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)
            label = Gtk.Label(label=name)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(14)
            inner.pack_start(label, False, False, 0)
            btn.add(inner)
            btn.connect("clicked", lambda b, tid=tab_id: self.switch_tab(tid))
            if tab_id is not HISTORY_TAB:
                btn.set_tooltip_text(f"{name} — clique direito para opções")
                btn.connect("button-press-event", self._on_tab_button_press, tab_id)
            self.tabs_box.pack_start(btn, False, False, 0)
        self.tabs_box.show_all()

    def switch_tab(self, tab_id: Optional[str]):
        if tab_id is not HISTORY_TAB and tab_id not in self._tab_order():
            tab_id = HISTORY_TAB
        self.active_tab = tab_id
        if tab_id is not HISTORY_TAB:
            self.tabs.touch(tab_id)
        self._update_header()
        self._rebuild_tab_bar()
        if self.search_entry.get_text():
            self.search_entry.set_text("")  # dispara refresh via "changed"
        else:
            self.refresh_items()
        self.search_entry.grab_focus()

    def on_tabs_changed(self):
        """Chamado pelo daemon quando o estado das abas muda (ex.: auto-lock)."""
        if self.get_visible():
            self._rebuild_tab_bar()
            self.refresh_items()

    def _active_tab_info(self):
        for t in self.tabs.list_tabs():
            if t.id == self.active_tab:
                return t
        return None

    def _update_header(self):
        if self.active_tab is HISTORY_TAB:
            self.action_btn.set_label("Limpar tudo")
            self.action_btn.set_sensitive(True)
            self.search_entry.set_placeholder_text("Pesquisar no histórico...")
            return
        info = self._active_tab_info()
        name = info.name if info else "aba"
        self.action_btn.set_label("+ Novo item")
        self.action_btn.set_sensitive(not (info and info.locked))
        self.search_entry.set_placeholder_text(f"Pesquisar em {name}...")

    def _on_action_clicked(self, widget):
        if self.active_tab is HISTORY_TAB:
            self.storage.clear_unpinned()
            self.refresh_items()
        else:
            self._show_new_item_popover()

    def _flash_status(self, text: str):
        """Mostra uma mensagem curta de confirmação no cabeçalho."""
        self.status_label.set_text(text)
        if self._status_timer:
            GLib.source_remove(self._status_timer)

        def _clear():
            self.status_label.set_text("")
            self._status_timer = None
            return False

        self._status_timer = GLib.timeout_add(1500, _clear)

    # ------------------------------------------------------------------ popovers
    def _popup(self, popover: Gtk.Popover, focus_widget: Optional[Gtk.Widget] = None):
        if self._open_popover:
            self._open_popover.popdown()
        self._open_popover = popover

        def _on_closed(p):
            if self._open_popover is p:
                self._open_popover = None

        popover.connect("closed", _on_closed)
        popover.get_child().show_all()
        popover.popup()
        if focus_widget:
            GLib.idle_add(lambda: (focus_widget.grab_focus(), False)[1])

    def _new_popover(self, relative_to: Gtk.Widget, title: str):
        pop = Gtk.Popover.new(relative_to)
        pop.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.get_style_context().add_class("popover-box")
        title_lbl = Gtk.Label(label=title)
        title_lbl.set_xalign(0.0)
        title_lbl.get_style_context().add_class("popover-title")
        box.pack_start(title_lbl, False, False, 0)
        pop.add(box)
        return pop, box

    def _make_entry(self, placeholder: str, text: str = "") -> Gtk.Entry:
        entry = Gtk.Entry()
        entry.set_placeholder_text(placeholder)
        entry.set_text(text)
        entry.get_style_context().add_class("search-entry")
        entry.set_width_chars(24)
        return entry

    def _make_menu_button(self, label: str, callback, danger: bool = False) -> Gtk.Button:
        btn = Gtk.Button(label=label)
        btn.set_relief(Gtk.ReliefStyle.NONE)
        btn.get_style_context().add_class("menu-btn")
        if danger:
            btn.get_style_context().add_class("danger-btn")
        btn.get_child().set_xalign(0.0)
        btn.connect("clicked", lambda b: callback())
        return btn

    def _show_create_tab_popover(self):
        pop, box = self._new_popover(self.add_tab_btn, "Nova aba")
        entry = self._make_entry("Nome da aba")
        box.pack_start(entry, False, False, 0)

        # Checkbox Cofre
        check = Gtk.CheckButton(label="Proteger com senha (Cofre 🔒)")
        check.get_style_context().add_class("checkbox-label")
        box.pack_start(check, False, False, 0)

        pwd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        pwd_box.set_no_show_all(True)
        pwd_box.hide()

        pwd_entry = self._make_entry("Senha do cofre")
        pwd_entry.set_visibility(False)
        pwd_entry.set_property("caps-lock-warning", True)

        pwd_conf = self._make_entry("Confirmar senha")
        pwd_conf.set_visibility(False)
        pwd_conf.set_property("caps-lock-warning", True)

        pwd_box.pack_start(pwd_entry, False, False, 0)
        pwd_box.pack_start(pwd_conf, False, False, 0)
        box.pack_start(pwd_box, False, False, 0)

        def _on_toggle_check(btn):
            if btn.get_active():
                pwd_box.show_all()
            else:
                pwd_box.hide()

        check.connect("toggled", _on_toggle_check)

        error = Gtk.Label(label="")
        error.get_style_context().add_class("error-label")
        error.set_xalign(0.0)
        box.pack_start(error, False, False, 0)

        def _create():
            name = entry.get_text().strip()
            password = None
            if check.get_active():
                p1 = pwd_entry.get_text()
                p2 = pwd_conf.get_text()
                if not p1:
                    error.set_text("A senha não pode ser vazia")
                    return
                if p1 != p2:
                    error.set_text("As senhas não coincidem")
                    return
                password = p1

            try:
                tab_id = self.tabs.create_tab(name, password=password)
            except (TabError, ValueError) as e:
                error.set_text(str(e))
                return
            pop.popdown()
            self.switch_tab(tab_id)

        entry.connect("activate", lambda e: _create())
        pwd_entry.connect("activate", lambda e: _create())
        pwd_conf.connect("activate", lambda e: _create())

        box.pack_start(self._make_menu_button("Criar aba", _create), False, False, 0)
        self._popup(pop, entry)

    def _on_tab_button_press(self, btn, event, tab_id):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self._show_tab_menu(btn, tab_id)
            return True
        return False

    def _show_tab_menu(self, btn: Gtk.Widget, tab_id: str):
        info = next((t for t in self.tabs.list_tabs() if t.id == tab_id), None)
        if not info:
            return
        pop, box = self._new_popover(btn, info.name)

        def _rename_mode():
            for child in box.get_children()[1:]:
                box.remove(child)
            entry = self._make_entry("Novo nome", info.name)

            def _apply():
                try:
                    self.tabs.rename_tab(tab_id, entry.get_text())
                except TabError:
                    return
                pop.popdown()
                self._rebuild_tab_bar()
                self._update_header()

            entry.connect("activate", lambda e: _apply())
            box.pack_start(entry, False, False, 0)
            box.pack_start(self._make_menu_button("Salvar", _apply), False, False, 0)
            box.show_all()
            entry.grab_focus()

        def _delete_confirm():
            for child in box.get_children()[1:]:
                box.remove(child)
            warn = Gtk.Label(label="Excluir a aba e todos os seus itens?")
            warn.get_style_context().add_class("error-label")
            box.pack_start(warn, False, False, 0)

            def _delete():
                self.tabs.delete_tab(tab_id)
                pop.popdown()
                self.switch_tab(HISTORY_TAB if self.active_tab == tab_id else self.active_tab)

            box.pack_start(self._make_menu_button("Excluir definitivamente", _delete, danger=True), False, False, 0)
            box.pack_start(self._make_menu_button("Cancelar", pop.popdown), False, False, 0)
            box.show_all()

        if info.encrypted:
            if not info.locked:
                def _lock_now():
                    self.tabs.lock(tab_id)
                    pop.popdown()
                    self._rebuild_tab_bar()
                    self._update_header()
                    self.refresh_items()
                    self._flash_status("Cofre trancado")

                box.pack_start(self._make_menu_button("Trancar cofre agora (Ctrl+L)", _lock_now), False, False, 0)

        box.pack_start(self._make_menu_button("Renomear", _rename_mode), False, False, 0)
        box.pack_start(self._make_menu_button("Excluir aba", _delete_confirm, danger=True), False, False, 0)
        self._popup(pop)

    def _show_new_item_popover(self):
        tab_id = self.active_tab
        pop, box = self._new_popover(self.action_btn, "Novo item")
        sc = Gtk.ScrolledWindow()
        sc.set_size_request(300, 110)
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        view = Gtk.TextView()
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.set_left_margin(6)
        view.set_top_margin(4)
        sc.add(view)
        box.pack_start(sc, True, True, 0)

        def _from_clipboard():
            text = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
            if text:
                view.get_buffer().set_text(text)

        def _save():
            buf = view.get_buffer()
            text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
            try:
                if self.tabs.add_text(tab_id, text):
                    pop.popdown()
                    self.refresh_items()
                    self._flash_status("Item salvo")
            except TabError as e:
                self._flash_status(str(e))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row.pack_start(self._make_menu_button("Usar clipboard atual", _from_clipboard), False, False, 0)
        row.pack_end(self._make_menu_button("Salvar", _save), False, False, 0)
        box.pack_start(row, False, False, 0)
        self._popup(pop, view)

    def _show_send_popover(self, btn: Gtk.Widget, item: ClipboardItem):
        pop, box = self._new_popover(btn, "Enviar para aba")
        tabs = self.tabs.list_tabs()
        if not tabs:
            hint = Gtk.Label(label="Nenhuma aba criada.\nUse o + ao lado das abas.")
            hint.get_style_context().add_class("meta-label")
            hint.set_xalign(0.0)
            box.pack_start(hint, False, False, 0)

        for t in tabs:
            def _send(t=t):
                try:
                    self.tabs.add_item(t.id, item)
                    self._flash_status(f"Enviado para {t.name}")
                except TabError as e:
                    self._flash_status(str(e))
                pop.popdown()

            b = self._make_menu_button(t.name, _send)
            if t.locked:
                b.set_sensitive(False)
                b.set_tooltip_text("Destranque a aba primeiro")
            box.pack_start(b, False, False, 0)
        self._popup(pop)

    # ------------------------------------------------------------------ busca
    def _on_search_changed(self, entry):
        self.refresh_items()

    def _on_search_activate(self, entry):
        """Ao pressionar Enter na busca, cola o primeiro item filtrado imediatamente."""
        if self._current_items:
            self.execute_paste(self._current_items[0])

    def _on_focus_out(self, widget, event):
        if getattr(self, "_can_close_on_focus_out", False):
            self.hide()
        return True

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            # Esc fecha primeiro o popover aberto; só depois o flyout
            if self._open_popover:
                self._open_popover.popdown()
                return True
            self.hide()
            return True

        mods = event.state & Gtk.accelerator_get_default_mod_mask()
        order = self._tab_order()

        # Ctrl+L: trancar cofre atual se for cofre destrancado
        if mods == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_l, Gdk.KEY_L):
            if self.active_tab is not HISTORY_TAB:
                info = self._active_tab_info()
                if info and info.encrypted and not info.locked:
                    self.tabs.lock(self.active_tab)
                    self._rebuild_tab_bar()
                    self._update_header()
                    self.refresh_items()
                    self._flash_status("Cofre trancado")
                    return True

        # Alt+1..9: salta direto para a aba N (1 = Histórico)
        if mods == Gdk.ModifierType.MOD1_MASK and Gdk.KEY_1 <= event.keyval <= Gdk.KEY_9:
            idx = event.keyval - Gdk.KEY_1
            if idx < len(order):
                self.switch_tab(order[idx])
            return True

        # Ctrl+PgUp / Ctrl+PgDn: aba anterior / próxima (circular)
        if mods == Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_Page_Up, Gdk.KEY_Page_Down):
            step = 1 if event.keyval == Gdk.KEY_Page_Down else -1
            cur = order.index(self.active_tab) if self.active_tab in order else 0
            self.switch_tab(order[(cur + step) % len(order)])
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
        """Abre o flyout instantaneamente com os itens atualizados e foco na busca."""
        self.target_xid = target_xid
        self.target_wm_class = target_wm_class
        self._can_close_on_focus_out = False

        # Sempre abre na aba Histórico (comportamento padrão do Win+V)
        self.active_tab = HISTORY_TAB
        self._update_header()
        self._rebuild_tab_bar()
        self.search_entry.set_text("")
        self.refresh_items()
        self.position_at_pointer()

        self.show_all()
        self.present()

        # Força o foco de digitação na caixa de busca imediatamente
        self._activate_focus()

        # Permite fechamento por perda de foco após estabilização do foco inicial
        def _enable_focus_out():
            self._can_close_on_focus_out = True
            return False

        GLib.timeout_add(200, _enable_focus_out)

    def _activate_focus(self):
        """Garante que a janela ganhe o foco do X11 e a entrada de texto comece ativa."""
        self.search_entry.grab_focus()

        gdk_win = self.get_window()
        if gdk_win and hasattr(gdk_win, "get_xid"):
            try:
                xid = gdk_win.get_xid()
                subprocess.Popen(
                    ["xdotool", "windowactivate", "--sync", str(xid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception:
                pass

        def _refocus():
            if self.get_visible():
                self.search_entry.grab_focus()
            return False

        GLib.timeout_add(40, _refocus)

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

    def _render_unlock_view(self, tab_id: str):
        """Renderiza a interface de desbloqueio de cofre com foco na senha."""
        info = self._active_tab_info()
        tab_name = info.name if info else "Cofre"

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.get_style_context().add_class("unlock-box")
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("dialog-password-symbolic", Gtk.IconSize.DIALOG)
        box.pack_start(icon, False, False, 0)

        title = Gtk.Label(label=f"Cofre: {tab_name}")
        title.get_style_context().add_class("unlock-title")
        box.pack_start(title, False, False, 0)

        subtitle = Gtk.Label(label="Digite a senha para descriptografar os itens")
        subtitle.get_style_context().add_class("unlock-subtitle")
        box.pack_start(subtitle, False, False, 0)

        pwd_entry = Gtk.Entry()
        pwd_entry.set_placeholder_text("Senha do cofre...")
        pwd_entry.set_visibility(False)
        pwd_entry.set_property("caps-lock-warning", True)
        pwd_entry.get_style_context().add_class("search-entry")
        pwd_entry.set_width_chars(22)
        box.pack_start(pwd_entry, False, False, 0)

        err_label = Gtk.Label(label="")
        err_label.get_style_context().add_class("error-label")
        box.pack_start(err_label, False, False, 0)

        def _do_unlock():
            pw = pwd_entry.get_text()
            if not pw:
                err_label.set_text("Digite a senha")
                return
            try:
                self.tabs.unlock(tab_id, pw)
                self._update_header()
                self._rebuild_tab_bar()
                self.refresh_items()
                self._flash_status("Cofre destrancado")
            except InvalidPassword:
                err_label.set_text("Senha incorreta!")
                pwd_entry.set_text("")
                pwd_entry.grab_focus()
            except Exception as ex:
                err_label.set_text(f"Erro: {ex}")

        unlock_btn = Gtk.Button(label="Desbloquear")
        unlock_btn.get_style_context().add_class("primary-btn")
        unlock_btn.connect("clicked", lambda b: _do_unlock())
        pwd_entry.connect("activate", lambda e: _do_unlock())
        box.pack_start(unlock_btn, False, False, 0)

        self.cards_box.pack_start(box, True, True, 0)
        self.cards_box.show_all()
        GLib.idle_add(pwd_entry.grab_focus)

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
                    # Redimensiona mantendo proporção
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
        """Cria um botão com ícone simbólico (monocromático, herda a cor do CSS).
        Usa o primeiro ícone disponível no tema; se nenhum existir, um glifo de texto."""
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
        if event.button == 1:  # Botão esquerdo
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
        5. Aguarda 25ms e injeta Ctrl+V (ou Ctrl+Shift+V se for terminal).
        6. Se for cofre, restaura o clipboard anterior após 1.5s (Anti-Leak).
        """
        # Identifica se é originário de um cofre
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
            # Captura snapshot prévio do clipboard para restauração posterior
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

        # 3. Restaura foco e injeta colagem em background para não travar o loop de UI
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
