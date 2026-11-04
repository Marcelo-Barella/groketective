from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from grokbot_dogfood._lib import DEFAULT_CONFIG_ROOT, mask_id

SECRETS_KEY = "cursor-machine-id"
V11_PREFIX = b"v11"


class MachineIdError(RuntimeError):
    pass


def _config_root() -> Path:
    return Path(os.environ.get("GROKBOT_CONFIG_ROOT", str(DEFAULT_CONFIG_ROOT))).expanduser()


def _secrets_path() -> Path:
    return _config_root() / "sand-secrets.json"


def _read_secrets_raw(path: Path | None = None) -> str:
    secrets_path = path or _secrets_path()
    if not secrets_path.is_file():
        raise MachineIdError(
            "sand-secrets.json not found at "
            f"{secrets_path} (launch Grok Bot once or run bootstrap)"
        )
    try:
        payload = json.loads(secrets_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MachineIdError(f"sand-secrets.json is invalid JSON: {exc}") from exc
    raw = payload.get(SECRETS_KEY)
    if not isinstance(raw, str) or not raw.strip():
        raise MachineIdError(
            f"sand-secrets.json missing string key {SECRETS_KEY!r}"
        )
    return raw


def _machine_id_from_secrets(*, allow_keyring: bool) -> str:
    raw = _read_secrets_raw()
    decoded = base64.b64decode(raw, validate=False)
    if decoded.startswith(V11_PREFIX):
        if not allow_keyring:
            raise MachineIdError(
                "Encrypted machine id requires keyring; set GROKBOT_MACHINE_ID "
                "or unlock GNOME keyring for bootstrap"
            )
        return _decrypt_v11(decoded[3:])
    try:
        text = decoded.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise MachineIdError("cursor-machine-id is not v11 and not utf-8") from exc
    if not text:
        raise MachineIdError("cursor-machine-id decoded empty")
    return text


def resolve_machine_id(
    *,
    allow_keyring: bool = True,
    allow_bootstrap: bool = True,
) -> str:
    env_val = os.environ.get("GROKBOT_MACHINE_ID", "").strip()
    if env_val:
        return env_val

    secrets_path = _secrets_path()
    if secrets_path.is_file():
        try:
            return _machine_id_from_secrets(allow_keyring=allow_keyring)
        except MachineIdError:
            if not allow_bootstrap:
                raise

    if allow_bootstrap:
        from grokbot_dogfood.bootstrap import bootstrap_machine_id

        return bootstrap_machine_id(allow_keyring=allow_keyring)

    raise MachineIdError(
        "GROKBOT_MACHINE_ID is unset, no usable sand-secrets.json, and bootstrap "
        "is disabled. Install Grok Bot from https://x.ai/bot or set "
        "GROKBOT_MACHINE_ID in Automation Memory."
    )


def _decrypt_v11(ciphertext: bytes) -> str:
    try:
        import secretstorage
    except ImportError as exc:
        raise MachineIdError(
            "python3-secretstorage is required to decrypt cursor-machine-id (v11). "
            "Install secretstorage or set GROKBOT_MACHINE_ID."
        ) from exc

    password = _keyring_password()
    key = hashlib.pbkdf2_hmac(
        "sha1", password.encode("utf-8"), b"saltysalt", 1, dklen=16
    )
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError as exc:
        raise MachineIdError(
            "cryptography package required for v11 decrypt; set GROKBOT_MACHINE_ID"
        ) from exc

    iv = b" " * 16
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    plain = decryptor.update(ciphertext) + decryptor.finalize()
    pad = plain[-1]
    if pad < 1 or pad > 16:
        raise MachineIdError("invalid PKCS7 padding on decrypted machine id")
    plain = plain[:-pad]
    text = plain.decode("utf-8").strip()
    if not text:
        raise MachineIdError("decrypted machine id empty")
    return text


def _keyring_password() -> str:
    import secretstorage

    connection = secretstorage.dbus_init()
    collection = secretstorage.get_default_collection(connection)
    for item in collection.search_items(
        {
            "application": "Grok Bot",
        }
    ):
        label = item.get_label()
        if label and "Safe Storage" in label:
            secret = item.get_secret()
            if isinstance(secret, bytes):
                return secret.decode("utf-8")
            return str(secret)
    raise MachineIdError(
        "No GNOME Keyring item for Grok Bot Safe Storage; unlock keyring or set "
        "GROKBOT_MACHINE_ID"
    )


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    masked_only = "--masked" in argv or "--status" in argv
    allow_bootstrap = "--no-bootstrap" not in argv
    try:
        mid = resolve_machine_id(allow_bootstrap=allow_bootstrap)
    except MachineIdError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1
    if masked_only:
        print(f"machine_id={mask_id(mid)}")
        print("source=resolved")
        return 0
    print("error=refusing to print raw machine id; use --masked", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
