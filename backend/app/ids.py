import secrets
import string

_ALPHABET = string.ascii_lowercase + string.digits


def join_code() -> str:
    """Class join code like 'K7Q-3MP' (no 0/O/1/I so it's easy to read aloud)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    raw = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"{raw[:3]}-{raw[3:]}"


def new_id(prefix: str, length: int = 8) -> str:
    """Random, non-sequential id like `as_k3j9x0qa`."""
    return f"{prefix}_" + "".join(secrets.choice(_ALPHABET) for _ in range(length))
