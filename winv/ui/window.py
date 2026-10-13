"""
Janela principal (Flyout) do winv-linux, inspirada no Win+V da Microsoft.
Combina os mixins de abas (TabBarMixin), cards (CardsMixin) e popovers (PopoversMixin).
"""

import subprocess
from typing import List, Optional
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ..config import (
    POPUP_WIDTH,
    POPUP_MAX_HEIGHT,
    SCREEN_PADDING,
    GITHUB_REPO,
)
from ..models import ClipboardItem
from ..storage import HybridStorage
from ..tabs import TabManager
from ..x11_helper import X11Helper

from .constants import HISTORY_TAB
from .styles import CSS_STYLES
from .tabs_bar import TabBarMixin
from .cards import CardsMixin
from .popovers import PopoversMixin


class ClipboardFlyoutWindow(Gtk.Window, TabBarMixin, CardsMixin, PopoversMixin):
    """Janela Flyout de histórico de área de transferência rápida e frameless."""

    def __init__(self, storage: HybridStorage, x11_helper: X11Helper, monitor, tabs: TabManager, updater=None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.storage = storage
        self.x11_helper = x11_helper
        self.monitor = monitor
        self.tabs = tabs
        self.updater = updater

        self.target_xid: Optional[int] = None
        self.target_wm_class: str = "Unknown"
        self._current_items: List[ClipboardItem] = []
        self._can_close_on_focus_out: bool = False
        self.active_tab: Optional[str] = HISTORY_TAB
        self._open_popover: Optional[Gtk.Popover] = None
        self._status_timer: Optional[int] = None
        self._current_update_url: Optional[str] = None
        self._drag_state = {
            "tab_id": None,
            "widget": None,
            "start_x": 0,
            "has_dragged": False,
        }

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
        tab_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        tab_row.get_style_context().add_class("tab-bar")
        tab_row.add_events(Gdk.EventMask.SCROLL_MASK)
        tab_row.connect("scroll-event", self._on_tabs_scroll_event)

        self.tabs_scroller = Gtk.ScrolledWindow()
        self.tabs_scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.tabs_scroller.set_propagate_natural_height(True)
        self.tabs_scroller.set_shadow_type(Gtk.ShadowType.NONE)
        self.tabs_scroller.set_kinetic_scrolling(True)
        self.tabs_scroller.add_events(Gdk.EventMask.SCROLL_MASK)
        self.tabs_scroller.connect("scroll-event", self._on_tabs_scroll_event)

        self.tabs_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.tabs_box.add_events(Gdk.EventMask.SCROLL_MASK)
        self.tabs_box.connect("scroll-event", self._on_tabs_scroll_event)
        self.tabs_scroller.add(self.tabs_box)
        tab_row.pack_start(self.tabs_scroller, True, True, 0)

        self.add_tab_btn = self._make_icon_button(["list-add-symbolic"], "+")
        self.add_tab_btn.set_tooltip_text("Nova aba")
        self.add_tab_btn.add_events(Gdk.EventMask.SCROLL_MASK)
        self.add_tab_btn.connect("scroll-event", self._on_tabs_scroll_event)
        self.add_tab_btn.connect("clicked", lambda b: self._show_create_tab_popover())
        tab_row.pack_end(self.add_tab_btn, False, False, 0)
        header_box.pack_start(tab_row, False, False, 0)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Pesquisar no histórico...")
        self.search_entry.get_style_context().add_class("search-entry")
        self.search_entry.connect("changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        header_box.pack_start(self.search_entry, False, False, 0)

        # Banner de Notificação de Atualização (GitHub Releases)
        self.update_revealer = Gtk.Revealer()
        self.update_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.update_revealer.set_transition_duration(200)

        update_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        update_box.get_style_context().add_class("update-banner")

        self.update_label = Gtk.Label(label="")
        self.update_label.get_style_context().add_class("update-label")
        self.update_label.set_xalign(0.0)
        update_box.pack_start(self.update_label, True, True, 0)

        self.update_btn = Gtk.Button(label="Baixar")
        self.update_btn.get_style_context().add_class("update-btn")
        self.update_btn.connect("clicked", self._on_update_clicked)
        update_box.pack_end(self.update_btn, False, False, 0)

        dismiss_btn = Gtk.Button(label="✕")
        dismiss_btn.get_style_context().add_class("update-dismiss-btn")
        dismiss_btn.connect("clicked", lambda b: self.update_revealer.set_reveal_child(False))
        update_box.pack_end(dismiss_btn, False, False, 0)

        self.update_revealer.add(update_box)
        header_box.pack_start(self.update_revealer, False, False, 0)
        root_box.pack_start(header_box, False, False, 0)

        # 2. Lista Rolável de Cards
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.get_style_context().add_class("cards-scroller")
        
        self.cards_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.scroller.add(self.cards_box)
        root_box.pack_start(self.scroller, True, True, 0)

        self._rebuild_tab_bar()

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

        # Checagem instantânea em memória de atualização disponível (zero latência)
        if self.updater and self.updater.update_info and self.updater.update_info.get("available"):
            info = self.updater.update_info
            latest_v = info.get("latest_version", "")
            self.update_label.set_text(f"🚀 Nova versão {latest_v} disponível!")
            self._current_update_url = info.get("download_url") or info.get("url")
            self.update_revealer.set_reveal_child(True)
        else:
            self.update_revealer.set_reveal_child(False)

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

    def _on_update_clicked(self, btn):
        """Abre a página do release ou o instalador no navegador padrão e fecha o flyout."""
        self.hide()
        url = self._current_update_url or f"https://github.com/{GITHUB_REPO}/releases"
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception:
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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
