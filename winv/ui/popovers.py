"""
Módulo de popovers, menus contextuais e visualização de desbloqueio de cofre.
"""

from typing import Optional
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GLib

from ..crypto import InvalidPassword
from ..tabs import TabError
from ..models import ClipboardItem
from .constants import HISTORY_TAB


class PopoversMixin:
    """Mixin responsável por popovers de criação, menus contextuais e tela de cofre."""

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
        box.set_size_request(260, -1)

        # 1. Campo Nome
        lbl_name = Gtk.Label(label="Nome da aba:")
        lbl_name.get_style_context().add_class("form-label")
        lbl_name.set_xalign(0.0)
        box.pack_start(lbl_name, False, False, 0)

        entry = self._make_entry("Ex: Comandos, Senhas...")
        box.pack_start(entry, False, False, 0)

        # 2. Checkbox Cofre
        check = Gtk.CheckButton(label="Proteger com senha (Cofre 🔒)")
        check.get_style_context().add_class("checkbox-label")
        check.set_margin_top(8)
        box.pack_start(check, False, False, 0)

        # 3. Bloco de Senha
        pwd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        pwd_box.set_no_show_all(True)
        pwd_box.hide()

        lbl_pwd = Gtk.Label(label="Senha do cofre:")
        lbl_pwd.get_style_context().add_class("form-label")
        lbl_pwd.set_xalign(0.0)
        pwd_box.pack_start(lbl_pwd, False, False, 0)

        pwd_entry = self._make_entry("Digite a senha")
        pwd_entry.set_visibility(False)
        pwd_entry.set_property("caps-lock-warning", True)
        pwd_box.pack_start(pwd_entry, False, False, 0)

        lbl_conf = Gtk.Label(label="Confirmar senha:")
        lbl_conf.get_style_context().add_class("form-label")
        lbl_conf.set_xalign(0.0)
        pwd_box.pack_start(lbl_conf, False, False, 0)

        pwd_conf = self._make_entry("Repita a senha")
        pwd_conf.set_visibility(False)
        pwd_conf.set_property("caps-lock-warning", True)
        pwd_box.pack_start(pwd_conf, False, False, 0)

        box.pack_start(pwd_box, False, False, 0)

        # 4. Mensagem de Erro
        error = Gtk.Label(label="")
        error.get_style_context().add_class("error-label")
        error.set_xalign(0.0)
        box.pack_start(error, False, False, 0)

        def _set_pwd_box_visible(visible: bool):
            if visible:
                pwd_box.show()
                for c in pwd_box.get_children():
                    c.show()
            else:
                pwd_box.hide()

        def _on_toggle_check(btn):
            is_active = btn.get_active()
            _set_pwd_box_visible(is_active)
            if is_active:
                if entry.get_text().strip():
                    pwd_entry.grab_focus()
                else:
                    entry.grab_focus()
            error.set_text("")
            pop.queue_resize()

        check.connect("toggled", _on_toggle_check)

        def _create():
            error.set_text("")
            name = entry.get_text().strip()
            if not name:
                error.set_text("Por favor, preencha o Nome da aba.")
                entry.grab_focus()
                return

            password = None
            if check.get_active():
                p1 = pwd_entry.get_text()
                p2 = pwd_conf.get_text()
                if not p1:
                    error.set_text("Por favor, digite a senha do cofre.")
                    pwd_entry.grab_focus()
                    return
                if p1 != p2:
                    error.set_text("As senhas digitadas não coincidem.")
                    pwd_conf.grab_focus()
                    return
                password = p1

            try:
                tab_id = self.tabs.create_tab(name, password=password)
            except (TabError, ValueError) as e:
                error.set_text(str(e))
                return

            pop.popdown()
            self.switch_tab(tab_id)

        def _on_entry_activate(e):
            if check.get_active():
                pwd_entry.grab_focus()
            else:
                _create()

        entry.connect("activate", _on_entry_activate)
        pwd_entry.connect("activate", lambda e: pwd_conf.grab_focus())
        pwd_conf.connect("activate", lambda e: _create())

        btn_create = Gtk.Button(label="Criar aba")
        btn_create.get_style_context().add_class("form-btn")
        btn_create.connect("clicked", lambda b: _create())
        box.pack_start(btn_create, False, False, 0)

        self._popup(pop, entry)

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

        # Mover esquerda / direita
        tabs_list = [t.id for t in self.tabs.list_tabs()]
        cur_idx = tabs_list.index(tab_id) if tab_id in tabs_list else -1

        if cur_idx > 0:
            def _move_left():
                self.tabs.move_tab(tab_id, cur_idx - 1)
                pop.popdown()
                self._rebuild_tab_bar()
            box.pack_start(self._make_menu_button("⬅ Mover para a esquerda", _move_left), False, False, 0)

        if cur_idx >= 0 and cur_idx < len(tabs_list) - 1:
            def _move_right():
                self.tabs.move_tab(tab_id, cur_idx + 1)
                pop.popdown()
                self._rebuild_tab_bar()
            box.pack_start(self._make_menu_button("➡ Mover para a direita", _move_right), False, False, 0)

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
        unlock_btn.get_style_context().add_class("form-btn")
        unlock_btn.connect("clicked", lambda b: _do_unlock())
        pwd_entry.connect("activate", lambda e: _do_unlock())
        box.pack_start(unlock_btn, False, False, 0)

        self.cards_box.pack_start(box, True, True, 0)
        self.cards_box.show_all()
        GLib.idle_add(pwd_entry.grab_focus)
