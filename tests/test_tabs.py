"""Testes do TabManager. Rodar: python3 -m unittest discover tests"""

import json
import tempfile
import unittest
from pathlib import Path

from winv.crypto import InvalidPassword
from winv.models import ClipboardItem, ClipboardFormat
from winv.tabs import TabManager, TabError

FAST = {"n": 2 ** 10, "r": 8, "p": 1}
PNG = b"\x89PNG\r\n\x1a\n" + b"fake-image-data" * 10


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def text(t):
    return ClipboardItem(format_type=ClipboardFormat.TEXT, text_content=t)


class TestTabManager(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "Tabs"
        self.clock = FakeClock()
        self.tm = self.new_manager()

    def tearDown(self):
        self.tmp.cleanup()

    def new_manager(self):
        return TabManager(self.dir, autolock_seconds=300, clock=self.clock, scrypt_params=FAST)

    # ----------------------------------------------------------- abas normais
    def test_plain_tab_persists_across_restart(self):
        tid = self.tm.create_tab("Comandos")
        self.tm.add_text(tid, "git status")
        img = ClipboardItem(format_type=ClipboardFormat.IMAGE, image_bytes=PNG)
        self.tm.add_item(tid, img)

        tm2 = self.new_manager()
        tabs = tm2.list_tabs()
        self.assertEqual([t.name for t in tabs], ["Comandos"])
        items = tm2.get_items(tid)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].image_bytes, PNG)
        self.assertEqual(items[1].text_content, "git status")

    def test_dedup_moves_to_top(self):
        tid = self.tm.create_tab("A")
        self.tm.add_text(tid, "um")
        self.tm.add_text(tid, "dois")
        self.tm.add_text(tid, "um\n")
        self.assertEqual([i.text_content.strip() for i in self.tm.get_items(tid)], ["um", "dois"])

    def test_added_item_is_independent_copy(self):
        tid = self.tm.create_tab("A")
        original = text("x")
        self.tm.add_item(tid, original)
        self.assertNotEqual(self.tm.get_items(tid)[0].id, original.id)

    def test_delete_item_removes_image_file(self):
        tid = self.tm.create_tab("A")
        self.tm.add_item(tid, ClipboardItem(format_type=ClipboardFormat.IMAGE, image_bytes=PNG))
        item = self.tm.get_items(tid)[0]
        self.assertTrue((self.dir / tid / f"{item.id}.png").exists())
        self.tm.delete_item(tid, item.id)
        self.assertFalse((self.dir / tid / f"{item.id}.png").exists())

    def test_rename_move_delete(self):
        a = self.tm.create_tab("A")
        b = self.tm.create_tab("B")
        self.tm.rename_tab(a, "Alfa")
        self.tm.move_tab(b, 0)
        self.assertEqual([t.name for t in self.new_manager().list_tabs()], ["B", "Alfa"])
        self.tm.delete_tab(a)
        self.assertFalse((self.dir / a).exists())
        self.assertEqual([t.name for t in self.new_manager().list_tabs()], ["B"])

    def test_invalid_names(self):
        with self.assertRaises(TabError):
            self.tm.create_tab("   ")

    def test_search(self):
        tid = self.tm.create_tab("A")
        self.tm.add_text(tid, "docker ps")
        self.tm.add_text(tid, "git log")
        self.assertEqual(len(self.tm.get_items(tid, "DOCKER")), 1)

    # ----------------------------------------------------------- cofre
    def test_vault_nothing_in_clear_on_disk(self):
        tid = self.tm.create_tab("Tokens", password="pw")
        self.tm.add_text(tid, "AKIA-SEGREDO-123")
        self.tm.add_item(tid, ClipboardItem(format_type=ClipboardFormat.IMAGE, image_bytes=PNG))
        files = list((self.dir / tid).iterdir())
        self.assertEqual(sorted(f.name for f in files), ["tab_meta.json", "vault.enc"])
        for f in files:
            data = f.read_bytes()
            self.assertNotIn(b"AKIA", data)
            self.assertNotIn(b"pw\"", data)
            self.assertNotIn(b"fake-image-data", data)
        self.assertEqual((self.dir / tid / "vault.enc").stat().st_mode & 0o777, 0o600)

    def test_vault_starts_locked_after_restart(self):
        tid = self.tm.create_tab("Tokens", password="pw")
        self.tm.add_text(tid, "segredo")
        tm2 = self.new_manager()
        info = tm2.list_tabs()[0]
        self.assertTrue(info.locked)
        self.assertIsNone(info.count)
        with self.assertRaises(TabError):
            tm2.get_items(tid)
        with self.assertRaises(TabError):
            tm2.add_text(tid, "x")

    def test_vault_unlock_wrong_and_right_password(self):
        tid = self.tm.create_tab("Tokens", password="pw")
        self.tm.add_text(tid, "segredo")
        tm2 = self.new_manager()
        with self.assertRaises(InvalidPassword):
            tm2.unlock(tid, "errada")
        self.assertTrue(tm2.is_locked(tid))
        tm2.unlock(tid, "pw")
        self.assertEqual(tm2.get_items(tid)[0].text_content, "segredo")

    def test_vault_lock_clears_memory(self):
        tid = self.tm.create_tab("Tokens", password="pw")
        self.tm.add_text(tid, "segredo")
        key = self.tm._tabs[tid].key
        self.tm.lock(tid)
        self.assertTrue(key.is_wiped)
        self.assertEqual(self.tm._tabs[tid].items, [])
        self.assertIsNone(self.tm.find_item("qualquer"))

    def test_autolock_after_inactivity(self):
        tid = self.tm.create_tab("Tokens", password="pw")
        self.clock.t += 200
        self.tm.touch(tid)  # uso renova o prazo
        self.clock.t += 200
        self.assertEqual(self.tm.check_autolock(), [])
        self.clock.t += 101
        self.assertEqual(self.tm.check_autolock(), [tid])
        self.assertTrue(self.tm.is_locked(tid))

    def test_lock_all_keeps_plain_tabs(self):
        plain = self.tm.create_tab("A")
        self.tm.add_text(plain, "x")
        vault = self.tm.create_tab("V", password="pw")
        self.tm.lock_all()
        self.assertTrue(self.tm.is_locked(vault))
        self.assertEqual(len(self.tm.get_items(plain)), 1)

    def test_vault_header_in_meta(self):
        tid = self.tm.create_tab("Tokens", password="pw")
        meta = json.loads((self.dir / tid / "tab_meta.json").read_text())
        self.assertTrue(meta["encrypted"])
        self.assertEqual(meta["name"], "Tokens")
        self.assertEqual(meta["vault"]["kdf"]["name"], "scrypt")

    def test_find_item_reports_encrypted(self):
        tid = self.tm.create_tab("V", password="pw")
        self.tm.add_text(tid, "s")
        item = self.tm.get_items(tid)[0]
        self.assertEqual(self.tm.find_item(item.id)[2], True)


if __name__ == "__main__":
    unittest.main()
