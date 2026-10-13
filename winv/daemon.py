"""
Daemon principal do winv-linux
Orquestra o monitor de clipboard, armazenamento híbrido, interface GTK pré-carregada e IPC
"""

import sys
import signal
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from .config import ensure_directories
from .storage import HybridStorage
from .x11_helper import X11Helper
from .monitor import ClipboardMonitor
from .ui import ClipboardFlyoutWindow
from .ipc import IPCServer

class WinVDaemon:
    def __init__(self):
        ensure_directories()

        print("[Daemon] Inicializando subsistemas winv-linux...")
        self.storage = HybridStorage()
        self.x11_helper = X11Helper()

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
            monitor=self.monitor
        )

        # Inicia o servidor IPC de disparo rápido
        self.ipc_server = IPCServer(on_command_callback=self._handle_ipc_command)

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
