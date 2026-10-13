"""
Testes unitários para o módulo de verificação de atualizações (updater.py).
"""

import unittest
from unittest.mock import patch, MagicMock
import io
import json

from winv.updater import parse_version, UpdateChecker


class TestUpdater(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("1.0.0"), (1, 0, 0))
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("V2.0"), (2, 0))
        self.assertEqual(parse_version("0.9.5-beta"), (0, 9, 5))
        self.assertTrue(parse_version("1.1.0") > parse_version("1.0.0"))
        self.assertTrue(parse_version("v2.0.0") > parse_version("v1.9.9"))
        self.assertFalse(parse_version("1.0.0") > parse_version("1.0.0"))

    @patch("urllib.request.urlopen")
    def test_update_available(self, mock_urlopen):
        payload = {
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/JKLModesto/winv-linux/releases/tag/v1.2.0",
            "assets": [
                {
                    "name": "winv-linux_1.2.0_all.deb",
                    "browser_download_url": "https://github.com/JKLModesto/winv-linux/releases/download/v1.2.0/winv-linux_1.2.0_all.deb"
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        checker = UpdateChecker(current_version="1.0.0", repo="JKLModesto/winv-linux")
        checker._worker()

        self.assertIsNotNone(checker.update_info)
        self.assertTrue(checker.update_info["available"])
        self.assertEqual(checker.update_info["latest_version"], "v1.2.0")
        self.assertEqual(checker.update_info["download_url"], "https://github.com/JKLModesto/winv-linux/releases/download/v1.2.0/winv-linux_1.2.0_all.deb")

    @patch("urllib.request.urlopen")
    def test_no_update_when_same_or_older(self, mock_urlopen):
        payload = {
            "tag_name": "v1.0.0",
            "html_url": "https://github.com/JKLModesto/winv-linux/releases/tag/v1.0.0",
            "assets": []
        }
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        checker = UpdateChecker(current_version="1.0.0", repo="JKLModesto/winv-linux")
        checker._worker()

        self.assertIsNone(checker.update_info)

    @patch("urllib.request.urlopen")
    def test_network_failure_handled_gracefully(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")

        checker = UpdateChecker(current_version="1.0.0", repo="JKLModesto/winv-linux")
        checker._worker()

        # Falha de rede não lança exceção e mantém update_info None
        self.assertIsNone(checker.update_info)


if __name__ == "__main__":
    unittest.main()
