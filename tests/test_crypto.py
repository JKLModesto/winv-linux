"""Testes do módulo de criptografia das Abas Cofre. Rodar: python3 -m unittest discover tests"""

import unittest

from winv import crypto
from winv.crypto import (
    CryptoError, InvalidPassword, VaultLocked,
    create_vault_header, unlock_vault,
    encrypt_vault_payload, decrypt_vault_payload,
)

# Parâmetros leves para os testes rodarem rápido (produção usa n=2^17)
FAST = {"n": 2 ** 10, "r": 8, "p": 1}
TAB = "tab-1234"


class TestVaultCrypto(unittest.TestCase):
    def setUp(self):
        self.header, self.key = create_vault_header(TAB, "s3nh@", **FAST)

    def test_header_has_no_secrets(self):
        dump = str(self.header)
        self.assertNotIn("s3nh@", dump)
        self.assertEqual(self.header["kdf"]["name"], "scrypt")
        self.assertEqual(len(bytes.fromhex(self.header["kdf"]["salt"])), crypto.SALT_SIZE)

    def test_roundtrip(self):
        payload = {"items": [{"text": "token-ação-😀", "pinned": True}]}
        blob = encrypt_vault_payload(self.key, TAB, payload)
        self.assertNotIn(b"token", blob)
        key2 = unlock_vault(TAB, self.header, "s3nh@")
        self.assertEqual(decrypt_vault_payload(key2, TAB, blob), payload)

    def test_wrong_password(self):
        with self.assertRaises(InvalidPassword):
            unlock_vault(TAB, self.header, "errada")

    def test_empty_password(self):
        with self.assertRaises(InvalidPassword):
            unlock_vault(TAB, self.header, "")
        with self.assertRaises(ValueError):
            create_vault_header(TAB, "", **FAST)

    def test_tampered_blob(self):
        blob = bytearray(encrypt_vault_payload(self.key, TAB, {"a": 1}))
        blob[-1] ^= 0x01
        with self.assertRaises(CryptoError):
            decrypt_vault_payload(self.key, TAB, bytes(blob))

    def test_blob_bound_to_tab(self):
        blob = encrypt_vault_payload(self.key, TAB, {"a": 1})
        with self.assertRaises(CryptoError):
            decrypt_vault_payload(self.key, "outra-aba", blob)

    def test_header_bound_to_tab(self):
        with self.assertRaises(InvalidPassword):
            unlock_vault("outra-aba", self.header, "s3nh@")

    def test_unique_nonce_per_write(self):
        a = encrypt_vault_payload(self.key, TAB, {"a": 1})
        b = encrypt_vault_payload(self.key, TAB, {"a": 1})
        self.assertNotEqual(a, b)

    def test_unique_salt_per_vault(self):
        h2, _ = create_vault_header(TAB, "s3nh@", **FAST)
        self.assertNotEqual(self.header["kdf"]["salt"], h2["kdf"]["salt"])

    def test_wipe(self):
        raw = self.key._key
        self.key.wipe()
        self.assertTrue(self.key.is_wiped)
        self.assertEqual(bytes(raw), b"\x00" * crypto.KEY_SIZE)
        with self.assertRaises(VaultLocked):
            encrypt_vault_payload(self.key, TAB, {})

    def test_invalid_blob(self):
        with self.assertRaises(CryptoError):
            decrypt_vault_payload(self.key, TAB, b"\x09lixo")

    def test_default_params_strength(self):
        self.assertGreaterEqual(crypto.DEFAULT_SCRYPT_N, 2 ** 17)


if __name__ == "__main__":
    unittest.main()
