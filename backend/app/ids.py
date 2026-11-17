import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def new_id(prefix: str, length: int = 8) -> str:
    """Random, non-sequential id like `as_k3j9x0qa`."""
    return f"{prefix}_" + "".join(secrets.choice(_ALPHABET) for _ in range(length))
