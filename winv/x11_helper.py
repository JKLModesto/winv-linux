"""
Utilitários de integração com o servidor de janelas X11 do Cinnamon (Linux Mint)
Captura de foco da janela alvo, restauração e injeção do atalho de colagem (SendInput equivalente)
"""

import time
import subprocess
import shutil
from typing import Tuple, Optional

from .config import TERMINAL_WM_CLASSES, FOCUS_STABILIZATION_DELAY_SEC

class X11Helper:
    def __init__(self):
        self.has_xdotool = shutil.which("xdotool") is not None
        self._last_active_xid: Optional[int] = None
        self._last_active_wm_class: str = "Unknown"

    def get_active_window_info(self) -> Tuple[Optional[int], str]:
        """
        Captura o XID e a WM_CLASS da janela ativa antes de abrir o popup.
        """
        if not self.has_xdotool:
            return None, "Unknown"

        try:
            # Obtém XID da janela ativa
            res = subprocess.run(
                ["xdotool", "getactivewindow"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=0.3
            )
            if res.returncode != 0 or not res.stdout.strip():
                return None, "Unknown"

            xid = int(res.stdout.strip())

            # Obtém WM_CLASS via xprop
            wm_class = "Unknown"
            prop_res = subprocess.run(
                ["xprop", "-id", str(xid), "WM_CLASS"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=0.3
            )
            if prop_res.returncode == 0 and "WM_CLASS" in prop_res.stdout:
                parts = prop_res.stdout.split("=")
                if len(parts) > 1:
                    raw_classes = parts[1].replace('"', '').strip().split(",")
                    if raw_classes:
                        wm_class = raw_classes[-1].strip().lower()

            self._last_active_xid = xid
            self._last_active_wm_class = wm_class
            return xid, wm_class

        except Exception as e:
            print(f"[X11Helper] Erro ao obter janela ativa: {e}")
            return None, "Unknown"

    def get_active_window_class(self) -> str:
        """Retorna apenas o nome da classe da aplicação ativa."""
        _, wm_class = self.get_active_window_info()
        return wm_class

    def restore_focus_and_paste(self, target_xid: Optional[int], target_wm_class: str):
        """
        Restaura o foco na janela anterior e injeta a sequência de colagem.
        Detecta emuladores de terminal para disparar Ctrl+Shift+V, ou Ctrl+V para os demais.
        """
        if not self.has_xdotool or target_xid is None:
            return

        try:
            # 1. Restaura o foco na janela de destino
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", str(target_xid)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=0.5
            )

            # 2. Pausa de estabilização de foco (25 ms, espelhando o Windows)
            time.sleep(FOCUS_STABILIZATION_DELAY_SEC)

            # 3. Identifica a combinação de teclas necessária
            is_terminal = target_wm_class.lower() in TERMINAL_WM_CLASSES
            key_combo = "ctrl+shift+v" if is_terminal else "ctrl+v"

            # 4. Injeta a simulação do teclado via XTest / xdotool
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", key_combo],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=0.5
            )

        except Exception as e:
            print(f"[X11Helper] Erro ao injetar colagem na janela {target_xid}: {e}")
