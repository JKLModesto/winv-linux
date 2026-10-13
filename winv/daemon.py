"""
Daemon principal do winv-linux
Orquestra o monitor de clipboard, armazenamento híbrido, interface GTK pré-carregada e IPC
"""

import sys
import signal
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from .config import ensure_directories, TABS_DIR, VERSION, GITHUB_REPO
from .storage import HybridStorage
from .tabs import TabManager
from .x11_helper import X11Helper
from .monitor import ClipboardMonitor
from .ui import ClipboardFlyoutWindow
from .ipc import IPCServer
from .updater import UpdateChecker

AUTOLOCK_CHECK_INTERVAL_SEC = 30
INITIAL_UPDATE_CHECK_SEC = 15
DAILY_UPDATE_CHECK_SEC = 86400  # 24 horas

class WinVDaemon:
    def __init__(self):
        ensure_directories()

        print("[Daemon] Inicializando subsistemas winv-linux...")
        self.storage = HybridStorage()
        self.tabs = TabManager(TABS_DIR)
        self.x11_helper = X11Helper()
        self.updater = UpdateChecker(current_version=VERSION, repo=GITHUB_REPO)

        # Instancia a janela de UI pré-carregada (em estado oculto)
        self.flyout: ClipboardFlyoutWindow = None
        self.monitor = ClipboardMonitor(
            storage=self.storage,
            x11_helper=self.x11_helper,
            on_item_added_callback=self._on_item_added
        )

        self.flyout = ClipboardFlyoutWindow(
            storage=self.storage,
            x11_helper=self.x11_helper,
            monitor=self.monitor,
            tabs=self.tabs,
            updater=self.updater
        )

        # Verificação periódica de auto-lock das Abas Cofre
        GLib.timeout_add_seconds(AUTOLOCK_CHECK_INTERVAL_SEC, self._autolock_tick)

        # Checagem assíncrona de atualização (15s após inicialização para estabilizar a rede)
        GLib.timeout_add_seconds(INITIAL_UPDATE_CHECK_SEC, self._on_initial_update_check)

        # Inicia o servidor IPC de disparo rápido
        self.ipc_server = IPCServer(on_command_callback=self._handle_ipc_command)

    def _on_initial_update_check(self):
        """Dispara a checagem inicial de atualização e agenda o ciclo diário."""
        self.updater.check_async()
        GLib.timeout_add_seconds(DAILY_UPDATE_CHECK_SEC, self._on_daily_update_check)
        return False

    def _on_daily_update_check(self):
        """Checagem periódica diária de novas releases."""
        self.updater.check_async()
        return True

    def _autolock_tick(self):
        if self.tabs.check_autolock():
            print("[Daemon] Auto-lock: aba(s) cofre trancada(s) por inatividade.")
            self.flyout.on_tabs_changed()
        return True

    def _on_item_added(self, item):
        """Callback acionado quando um novo item entra no histórico."""
        # Se o flyout estiver visível, atualiza a lista de cards
        if self.flyout and self.flyout.get_visible():
            self.flyout.refresh_items()

    def _handle_ipc_command(self, cmd: str) -> str:
        """Despachante de comandos recebidos pelo socket Unix."""
        cmd = cmd.strip().upper()

        if cmd == "TOGGLE":
            if self.flyout.get_visible():
                self.flyout.hide()
            else:
                # Captura a janela ativa no Cinnamon antes de exibir o flyout
                xid, wm_class = self.x11_helper.get_active_window_info()
                self.flyout.show_flyout(target_xid=xid, target_wm_class=wm_class)
            return "OK"

        elif cmd == "SHOW":
            xid, wm_class = self.x11_helper.get_active_window_info()
            self.flyout.show_flyout(target_xid=xid, target_wm_class=wm_class)
            return "OK"

        elif cmd == "HIDE":
            self.flyout.hide()
            return "OK"

        elif cmd == "CLEAR":
            self.storage.clear_unpinned()
            if self.flyout.get_visible():
                self.flyout.refresh_items()
            return "OK"

        elif cmd == "PING":
            return "PONG"

        return "UNKNOWN_COMMAND"

    def run(self):
        """Inicia o loop principal de eventos do GTK."""
        self.ipc_server.start()

        # Captura sinais de término do sistema
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print("[Daemon] winv-linux em execução com sucesso.")
        try:
            Gtk.main()
        except KeyboardInterrupt:
            self.shutdown()

    def _signal_handler(self, sig, frame):
        print(f"\n[Daemon] Sinal {sig} recebido. Encerrando...")
        self.shutdown()

    def shutdown(self):
        if self.ipc_server:
            self.ipc_server.stop()
        Gtk.main_quit()
        sys.exit(0)

def main():
    daemon = WinVDaemon()
    daemon.run()

if __name__ == "__main__":
    main()
