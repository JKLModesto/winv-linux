"""
Servidor e cliente IPC via Unix Domain Socket
Garante acionamento instantâneo (< 10ms) ao pressionar o atalho global Super+V
"""

import os
import socket
import threading
from typing import Callable, Optional
import gi
from gi.repository import GLib

from .config import SOCKET_PATH

class IPCServer:
    def __init__(self, on_command_callback: Callable[[str], str]):
        self.on_command_callback = on_command_callback
        self.server_sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Inicia o servidor de socket Unix."""
        if SOCKET_PATH.exists():
            try:
                SOCKET_PATH.unlink()
            except Exception:
                pass

        self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_sock.bind(str(SOCKET_PATH))
        self.server_sock.listen(5)
        self._running = True

        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print(f"[IPC] Servidor ouvindo em: {SOCKET_PATH}")

    def _listen_loop(self):
        while self._running:
            try:
                client_sock, _ = self.server_sock.accept()
                data = client_sock.recv(1024).decode("utf-8").strip()
                if data:
                    # Executa o comando no loop principal do GTK
                    def _dispatch(cmd=data, sock=client_sock):
                        try:
                            response = self.on_command_callback(cmd)
                            sock.sendall(f"{response}\n".encode("utf-8"))
                        except Exception as e:
                            print(f"[IPC] Erro ao despachar comando '{cmd}': {e}")
                        finally:
                            sock.close()
                        return False

                    GLib.idle_add(_dispatch)
                else:
                    client_sock.close()
            except Exception:
                if not self._running:
                    break

    def stop(self):
        self._running = False
        if self.server_sock:
            self.server_sock.close()
        if SOCKET_PATH.exists():
            try:
                SOCKET_PATH.unlink()
            except Exception:
                pass

def send_command(command: str = "TOGGLE", timeout: float = 1.0) -> bool:
    """Cliente leve utilizado pelo comando CLI do atalho Super+V."""
    if not SOCKET_PATH.exists():
        return False

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(str(SOCKET_PATH))
        sock.sendall(f"{command}\n".encode("utf-8"))
        res = sock.recv(1024).decode("utf-8").strip()
        sock.close()
        return res == "OK" or len(res) > 0
    except Exception as e:
        print(f"[IPC Client] Falha ao conectar ao daemon: {e}")
        return False
