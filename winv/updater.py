"""
Módulo de verificação assíncrona de atualizações (Update Checker) via GitHub Releases.
Não bloqueia o loop da interface e não adiciona latência ao acionamento do flyout.
"""

import json
import re
import threading
import urllib.request
import urllib.error
from typing import Callable, Optional, Tuple
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib

from .config import VERSION, GITHUB_REPO, GITHUB_API_RELEASES_URL


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Converte strings como 'v1.2.3' ou '1.2' em tupla comparável (1, 2, 3)."""
    clean = re.sub(r"^[vV]", "", str(version_str).strip())
    parts = []
    for piece in clean.split("."):
        nums = re.findall(r"\d+", piece)
        parts.append(int(nums[0]) if nums else 0)
    return tuple(parts) if parts else (0,)


class UpdateChecker:
    """Verificador silencioso de novas versões no GitHub Releases em background."""

    def __init__(self, current_version: str = VERSION, repo: str = GITHUB_REPO):
        self.current_version = current_version
        self.repo = repo
        self.update_info: Optional[dict] = None
        self._lock = threading.Lock()
        self._is_checking = False

    def check_async(self, on_result: Optional[Callable[[Optional[dict]], None]] = None):
        """Inicia uma checagem em thread separada com timeout estrito de 5s."""
        with self._lock:
            if self._is_checking:
                return
            self._is_checking = True

        thread = threading.Thread(
            target=self._worker,
            args=(on_result,),
            name="winv-update-checker",
            daemon=True
        )
        thread.start()

    def _worker(self, on_result: Optional[Callable[[Optional[dict]], None]] = None):
        result = None
        try:
            url = f"https://api.github.com/repos/{self.repo}/releases/latest"
            headers = {
                "User-Agent": f"winv-linux/{self.current_version} (Linux X11)",
                "Accept": "application/vnd.github.v3+json"
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    latest_tag = data.get("tag_name", "").strip()
                    html_url = data.get("html_url", f"https://github.com/{self.repo}/releases")

                    # Procura asset .deb direto nos anexos da release
                    deb_download_url = html_url
                    for asset in data.get("assets", []):
                        asset_name = asset.get("name", "")
                        if asset_name.endswith(".deb"):
                            deb_download_url = asset.get("browser_download_url", html_url)
                            break

                    latest_ver = parse_version(latest_tag)
                    curr_ver = parse_version(self.current_version)

                    if latest_ver > curr_ver:
                        result = {
                            "available": True,
                            "latest_version": latest_tag,
                            "current_version": self.current_version,
                            "url": html_url,
                            "download_url": deb_download_url,
                        }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            # Falhas de rede ou offline são ignoradas silenciosamente
            result = None
        except Exception as e:
            print(f"[Updater] Erro silencioso ao consultar GitHub Releases: {e}")
            result = None
        finally:
            with self._lock:
                self._is_checking = False
                if result:
                    self.update_info = result

            if on_result:
                GLib.idle_add(on_result, result)
