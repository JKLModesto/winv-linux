"""
Configurações e constantes do subsistema winv-linux
Espelhando com fidelidade as constantes extraídas da engenharia reversa do Windows
(cbdhsvc.dll e SuggestionUIUndocked.dll)
"""

import os
import getpass
from pathlib import Path

# Limites extraídos de cbdhsvc.dll
MAX_BUFFER_ITEMS = 25
MAX_ITEM_SIZE_BYTES = 4 * 1024 * 1024  # 4 MB (4.194.304 bytes)

# Intervalos de tempo
FOCUS_STABILIZATION_DELAY_SEC = 0.025  # 25 ms de espera após restaurar foco

# Diretórios de armazenamento (espelho de %LOCALAPPDATA%\Microsoft\Windows\Clipboard\)
USER_HOME = Path.home()
BASE_DATA_DIR = USER_HOME / ".local" / "share" / "winv-clipboard"
PINNED_DIR = BASE_DATA_DIR / "Pinned"
PINNED_METADATA_FILE = PINNED_DIR / "metadata.json"
TABS_DIR = BASE_DATA_DIR / "Tabs"

# Socket IPC para acionamento instantâneo via Super+V
UID = os.getuid() if hasattr(os, "getuid") else 1000
SOCKET_PATH = Path(f"/tmp/winv-linux-{UID}.sock")

# Dimensões da Interface Gráfica
POPUP_WIDTH = 380
POPUP_MAX_HEIGHT = 540
SCREEN_PADDING = 10
THUMBNAIL_MAX_WIDTH = 320
THUMBNAIL_MAX_HEIGHT = 160

# Lista de WM_CLASS correspondente a emuladores de terminal
# No Linux X11, terminais utilizam Ctrl+Shift+V para colar, enquanto outras janelas usam Ctrl+V
TERMINAL_WM_CLASSES = {
    "gnome-terminal",
    "gnome-terminal-server",
    "tilix",
    "kitty",
    "alacritty",
    "xfce4-terminal",
    "mate-terminal",
    "konsole",
    "terminator",
    "xterm",
    "uxterm",
    "urxvt",
    "rxvt",
    "foot",
    "wezterm",
    "hyper",
    "guake",
    "tilda",
    "lxterminal"
}

def ensure_directories():
    """Garante que a estrutura de diretórios em disco exista."""
    BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PINNED_DIR.mkdir(parents=True, exist_ok=True)
