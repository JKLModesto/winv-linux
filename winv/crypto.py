"""
Módulo de criptografia das Abas Cofre do winv-linux.

Esquema:
  - KDF: Scrypt (memory-hard) -> chave de 256 bits a partir da senha da aba.
  - Cifra: AES-256-GCM, nonce aleatório de 12 bytes por gravação.
  - AAD: o tab_id é usado como dado associado, impedindo que o blob de uma
    aba seja trocado pelo de outra sem ser detectado.
  - Verificação de senha: um bloco conhecido ("verifier") cifrado com a chave.
    Se a tag GCM falhar ao decifrá-lo, a senha está incorreta. A senha nunca
    é persistida.

Formato de um blob cifrado (bytes):  VERSION(1) || NONCE(12) || CIPHERTEXT+TAG

Limitação conhecida: o Python não garante a remoção de cópias internas de
objetos imutáveis (str/bytes). A chave é mantida num bytearray e zerada ao
trancar ("melhor esforço"); a proteção forte é a do disco.
"""

import json
import os
import secrets
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

BLOB_VERSION = 1
NONCE_SIZE = 12
KEY_SIZE = 32
SALT_SIZE = 16

# Parâmetros padrão do Scrypt: n=2^17, r=8 -> ~128 MiB de RAM, ~0,3-0,6 s.
DEFAULT_SCRYPT_N = 2 ** 17
DEFAULT_SCRYPT_R = 8
DEFAULT_SCRYPT_P = 1

VERIFIER_PLAINTEXT = b"winv-linux:vault-verifier:v1"


class CryptoError(Exception):
    """Erro genérico de criptografia (dados corrompidos ou adulterados)."""


class InvalidPassword(CryptoError):
    """A senha informada não corresponde à aba cofre."""


class VaultLocked(CryptoError):
    """Operação exigiu a chave, mas ela já foi descartada."""


class VaultKey:
    """Chave derivada mantida em memória mutável, com descarte explícito."""

    def __init__(self, key: bytearray):
        if len(key) != KEY_SIZE:
            raise ValueError("Tamanho de chave inválido")
        self._key: Optional[bytearray] = key

    @property
    def is_wiped(self) -> bool:
        return self._key is None

    def _aead(self) -> AESGCM:
        if self._key is None:
            raise VaultLocked("A chave do cofre foi descartada")
        return AESGCM(bytes(self._key))

    def encrypt(self, plaintext: bytes, aad: bytes) -> bytes:
        nonce = os.urandom(NONCE_SIZE)
        ct = self._aead().encrypt(nonce, plaintext, aad)
        return bytes([BLOB_VERSION]) + nonce + ct

    def decrypt(self, blob: bytes, aad: bytes) -> bytes:
        if len(blob) < 1 + NONCE_SIZE + 16 or blob[0] != BLOB_VERSION:
            raise CryptoError("Blob cifrado inválido ou de versão desconhecida")
        nonce, ct = blob[1:1 + NONCE_SIZE], blob[1 + NONCE_SIZE:]
        try:
            return self._aead().decrypt(nonce, ct, aad)
        except InvalidTag as e:
            raise CryptoError("Falha de autenticação: dados corrompidos ou adulterados") from e

    def encrypt_json(self, obj: Any, aad: bytes) -> bytes:
        return self.encrypt(json.dumps(obj, ensure_ascii=False).encode("utf-8"), aad)

    def decrypt_json(self, blob: bytes, aad: bytes) -> Any:
        return json.loads(self.decrypt(blob, aad).decode("utf-8"))

    def wipe(self):
        """Sobrescreve a chave com zeros e a descarta."""
        if self._key is not None:
            for i in range(len(self._key)):
                self._key[i] = 0
            self._key = None

    def __del__(self):
        self.wipe()


def _aad(tab_id: str, purpose: str) -> bytes:
    return f"winv-linux|{purpose}|{tab_id}".encode("utf-8")


def derive_key(password: str, salt: bytes, n: int = DEFAULT_SCRYPT_N,
               r: int = DEFAULT_SCRYPT_R, p: int = DEFAULT_SCRYPT_P) -> VaultKey:
    if not password:
        raise ValueError("A senha não pode ser vazia")
    kdf = Scrypt(salt=salt, length=KEY_SIZE, n=n, r=r, p=p)
    return VaultKey(bytearray(kdf.derive(password.encode("utf-8"))))


def create_vault_header(tab_id: str, password: str, n: int = DEFAULT_SCRYPT_N,
                        r: int = DEFAULT_SCRYPT_R, p: int = DEFAULT_SCRYPT_P):
    """
    Cria os parâmetros de um novo cofre.
    Retorna (header, key): header é seguro para gravar em tab_meta.json.
    """
    salt = secrets.token_bytes(SALT_SIZE)
    key = derive_key(password, salt, n, r, p)
    verifier = key.encrypt(VERIFIER_PLAINTEXT, _aad(tab_id, "verifier"))
    header = {
        "kdf": {"name": "scrypt", "n": n, "r": r, "p": p, "salt": salt.hex()},
        "cipher": "aes-256-gcm",
        "verifier": verifier.hex(),
    }
    return header, key


def unlock_vault(tab_id: str, header: Dict[str, Any], password: str) -> VaultKey:
    """Deriva a chave e valida a senha contra o verifier. Lança InvalidPassword."""
    kdf = header.get("kdf", {})
    if kdf.get("name") != "scrypt":
        raise CryptoError(f"KDF não suportado: {kdf.get('name')}")
    try:
        key = derive_key(password, bytes.fromhex(kdf["salt"]),
                         int(kdf["n"]), int(kdf["r"]), int(kdf["p"]))
    except ValueError as e:
        raise InvalidPassword(str(e)) from e
    try:
        plain = key.decrypt(bytes.fromhex(header["verifier"]), _aad(tab_id, "verifier"))
    except CryptoError:
        key.wipe()
        raise InvalidPassword("Senha incorreta")
    if plain != VERIFIER_PLAINTEXT:
        key.wipe()
        raise InvalidPassword("Senha incorreta")
    return key


def encrypt_vault_payload(key: VaultKey, tab_id: str, payload: Any) -> bytes:
    """Cifra o conteúdo completo de uma aba cofre (gravado em vault.enc)."""
    return key.encrypt_json(payload, _aad(tab_id, "payload"))


def decrypt_vault_payload(key: VaultKey, tab_id: str, blob: bytes) -> Any:
    return key.decrypt_json(blob, _aad(tab_id, "payload"))
