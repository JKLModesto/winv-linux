"""
Módulo de gerenciamento da barra de abas e ordenação Kanban (drag-and-drop).
"""

from typing import List, Optional
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, Pango, GLib

from .constants import HISTORY_TAB


class TabBarMixin:
    """Mixin responsável pela barra de abas, scroll horizontal e reordenação Kanban."""

    def _tab_order(self) -> List[Optional[str]]:
        return [HISTORY_TAB] + [t.id for t in self.tabs.list_tabs()]

    def _on_tabs_scroll_event(self, widget, event):
        """Converte qualquer scroll vertical (rodinha do mouse) em scroll horizontal fluido."""
        adj = self.tabs_scroller.get_hadjustment()
        if not adj:
            return False

        delta = 0
        if event.direction == Gdk.ScrollDirection.UP:
            delta = -50
        elif event.direction == Gdk.ScrollDirection.DOWN:
            delta = 50
        elif event.direction == Gdk.ScrollDirection.LEFT:
            delta = -50
        elif event.direction == Gdk.ScrollDirection.RIGHT:
            delta = 50
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            ret = event.get_scroll_deltas()
            if len(ret) == 3:
                _, dx, dy = ret
            elif len(ret) == 2:
                dx, dy = ret
            else:
                dx, dy = 0, 0
            delta = (dx + dy) * 40

        if delta != 0:
            cur = adj.get_value()
            page = adj.get_page_size()
            lower = adj.get_lower()
            upper = adj.get_upper()
            new_val = max(lower, min(upper - page, cur + delta))
            adj.set_value(new_val)
            return True
        return False

    def _rebuild_tab_bar(self):
        for child in self.tabs_box.get_children():
            self.tabs_box.remove(child)

        entries = [(HISTORY_TAB, "Histórico", None)]
        for t in self.tabs.list_tabs():
            icon = None
            if t.encrypted:
                icon = "changes-prevent-symbolic" if t.locked else "changes-allow-symbolic"
            entries.append((t.id, t.name, icon))

        active_btn = None

        for tab_id, name, icon in entries:
            eb = Gtk.EventBox()
            eb.set_visible_window(True)
            eb.set_above_child(True)
            eb.get_style_context().add_class("tab-btn")
            eb._tab_id = tab_id
            eb.add_events(
                Gdk.EventMask.POINTER_MOTION_MASK
                | Gdk.EventMask.BUTTON_PRESS_MASK
                | Gdk.EventMask.BUTTON_RELEASE_MASK
                | Gdk.EventMask.SCROLL_MASK
            )

            if tab_id == self.active_tab:
                eb.get_style_context().add_class("tab-active")
                active_btn = eb

            def _on_realize_cursor(w):
                w_win = w.get_window()
                if w_win:
                    w_win.set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "pointer"))
            eb.connect("realize", _on_realize_cursor)

            inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            inner.get_style_context().add_class("tab-inner")
            if icon:
                inner.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU), False, False, 0)

            # Nome cheio da aba, sem truncar
            label = Gtk.Label(label=name)
            label.set_single_line_mode(True)
            label.set_ellipsize(Pango.EllipsizeMode.NONE)
            inner.pack_start(label, False, False, 0)
            eb.add(inner)

            # Rolar com a rodinha sobre qualquer aba
            eb.connect("scroll-event", self._on_tabs_scroll_event)

            if tab_id is HISTORY_TAB:
                def _on_hist_click(w, event):
                    if event.button == 1:
                        self.switch_tab(HISTORY_TAB)
                        return True
                    return False
                eb.connect("button-press-event", _on_hist_click)
            else:
                eb.set_tooltip_text(f"{name} — arraste para reorganizar ou clique com botão direito")
                eb.connect("button-press-event", self._on_tab_button_press, tab_id)
                eb.connect("motion-notify-event", self._on_tab_motion, tab_id)
                eb.connect("button-release-event", self._on_tab_button_release, tab_id)

            self.tabs_box.pack_start(eb, False, False, 0)

        self.tabs_box.show_all()

        # Rola suavemente até a aba ativa para garantir visibilidade
        if active_btn:
            def _scroll_to_active():
                alloc = active_btn.get_allocation()
                adj = self.tabs_scroller.get_hadjustment()
                if adj and alloc.width > 0:
                    btn_x = alloc.x
                    btn_w = alloc.width
                    cur_val = adj.get_value()
                    page = adj.get_page_size()
                    if btn_x < cur_val:
                        adj.set_value(max(adj.get_lower(), btn_x - 12))
                    elif (btn_x + btn_w) > (cur_val + page):
                        adj.set_value(min(adj.get_upper() - page, btn_x + btn_w - page + 12))
                return False
            GLib.idle_add(_scroll_to_active)

    def _on_tab_button_press(self, eb, event, tab_id):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self._show_tab_menu(eb, tab_id)
            return True
        elif event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            self._drag_state = {
                "tab_id": tab_id,
                "widget": eb,
                "start_x": event.x_root,
                "has_dragged": False,
            }
            return True
        return False

    def _on_tab_motion(self, eb, event, tab_id):
        source_id = self._drag_state.get("tab_id")
        dragged_widget = self._drag_state.get("widget")
        if not source_id or source_id is HISTORY_TAB or not dragged_widget:
            return False

        if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
            return False

        dx = abs(event.x_root - self._drag_state["start_x"])
        if dx > 6:
            if not self._drag_state["has_dragged"]:
                self._drag_state["has_dragged"] = True
                dragged_widget.get_style_context().add_class("tab-dragging")
                win = dragged_widget.get_window()
                if win:
                    cursor = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "grabbing")
                    win.set_cursor(cursor)

            children = self.tabs_box.get_children()
            if dragged_widget not in children:
                return False

            current_pos = children.index(dragged_widget)

            # Auto-scroll nas bordas do scroller ao arrastar
            adj = self.tabs_scroller.get_hadjustment()
            if adj:
                scroller_alloc = self.tabs_scroller.get_allocation()
                scroller_coords = eb.translate_coordinates(self.tabs_scroller, int(event.x), int(event.y))
                if scroller_coords and scroller_alloc.width > 0:
                    sx = scroller_coords[0]
                    cur_val = adj.get_value()
                    page_size = adj.get_page_size()
                    if sx < 28 and cur_val > adj.get_lower():
                        adj.set_value(max(adj.get_lower(), cur_val - 15))
                    elif sx > (scroller_alloc.width - 28) and (cur_val + page_size) < adj.get_upper():
                        adj.set_value(min(adj.get_upper() - page_size, cur_val + 15))

            # Coordenadas relativas ao tabs_box
            coords = eb.translate_coordinates(self.tabs_box, int(event.x), int(event.y))
            if not coords:
                return False
            cursor_x = coords[0]

            # Movimento para a esquerda (posição 0 é o Histórico)
            if current_pos > 1:
                prev_child = children[current_pos - 1]
                alloc = prev_child.get_allocation()
                mid_x = alloc.x + (alloc.width / 2.0)
                if cursor_x < mid_x:
                    self.tabs_box.reorder_child(dragged_widget, current_pos - 1)
                    return True

            # Movimento para a direita
            if current_pos < len(children) - 1:
                next_child = children[current_pos + 1]
                alloc = next_child.get_allocation()
                mid_x = alloc.x + (alloc.width / 2.0)
                if cursor_x > mid_x:
                    self.tabs_box.reorder_child(dragged_widget, current_pos + 1)
                    return True

        return True

    def _on_tab_button_release(self, eb, event, tab_id):
        if event.button == 1:
            had_dragged = self._drag_state.get("has_dragged", False)
            dragged_id = self._drag_state.get("tab_id")
            dragged_widget = self._drag_state.get("widget")

            if dragged_widget:
                dragged_widget.get_style_context().remove_class("tab-dragging")
                win = dragged_widget.get_window()
                if win:
                    win.set_cursor(Gdk.Cursor.new_from_name(Gdk.Display.get_default(), "pointer"))

            self._drag_state = {"tab_id": None, "widget": None, "start_x": 0, "has_dragged": False}

            if had_dragged and dragged_id:
                # Salva a nova ordem no TabManager e persiste em disco
                children = self.tabs_box.get_children()
                new_tab_ids = [c._tab_id for c in children if hasattr(c, "_tab_id") and c._tab_id is not HISTORY_TAB]
                with self.tabs._lock:
                    self.tabs._order = [t for t in new_tab_ids if t in self.tabs._tabs]
                    self.tabs._save_index()
                return True
            else:
                self.switch_tab(tab_id)
                return True
        return False

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
