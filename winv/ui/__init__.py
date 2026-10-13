"""
Módulo de interface gráfica (UI) do winv-linux.
Exporta ClipboardFlyoutWindow e constantes para compatibilidade direta.
"""

from .constants import HISTORY_TAB
from .window import ClipboardFlyoutWindow

__all__ = [
    "ClipboardFlyoutWindow",
    "HISTORY_TAB",
]
