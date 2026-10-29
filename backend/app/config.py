import os
from urllib.parse import urlsplit

PUBLIC_ORIGIN_ERROR = "APP_BASE_URL must be an absolute HTTP(S) origin"


def load_app_base_url() -> str:
    """Validate the browser-facing origin before the API starts serving requests."""
    value = os.environ.get("APP_BASE_URL", "").strip()
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError:
        raise RuntimeError(PUBLIC_ORIGIN_ERROR) from None

    if (
        parts.scheme not in {"http", "https"}
        or not host
        or parts.username is not None
        or parts.password is not None
        or parts.path not in {"", "/"}
        or "?" in value
        or "#" in value
        or "\\" in value
        or any(character.isspace() or ord(character) < 32 for character in value)
        or parts.netloc.endswith(":")
    ):
        # Never echo the supplied value: a mistaken URL can contain credentials.
        raise RuntimeError(PUBLIC_ORIGIN_ERROR)

    authority = f"[{host}]" if ":" in host else host
    if port is not None and port != {"http": 80, "https": 443}[parts.scheme]:
        authority += f":{port}"
    return f"{parts.scheme}://{authority}"
