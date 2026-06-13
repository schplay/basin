"""Symmetric encryption for stored SMB passwords using Fernet."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from ...config import settings


def _fernet() -> Fernet:
    # Derive a valid 32-byte Fernet key from the configured secret
    digest = hashlib.sha256(settings.encryption_key.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_password(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
