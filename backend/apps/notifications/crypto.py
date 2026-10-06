import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet() -> Fernet:
    configured = getattr(settings, "MATEERP_SETTINGS_ENCRYPTION_KEY", "").strip()
    if configured:
        raw = configured.encode("utf-8")
        try:
            return Fernet(raw)
        except ValueError as exc:
            raise RuntimeError(
                "MATEERP_SETTINGS_ENCRYPTION_KEY must be a valid Fernet key."
            ) from exc

    digest = hashlib.sha256(
        f"mateerp-integration-settings:v1:{settings.SECRET_KEY}".encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored integration secret cannot be decrypted.") from exc
