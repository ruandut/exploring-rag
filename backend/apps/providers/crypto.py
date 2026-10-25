"""Symmetric encryption for secrets stored in the database (Fernet = AES-128-CBC + HMAC).

A database dump alone doesn't reveal API keys; you'd also need FIELD_ENCRYPTION_KEY from
the environment. Rotating that key means re-encrypting every stored secret.
"""

from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode())


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
