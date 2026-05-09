"""Content sanitization for agent responses — strips HTML/XML tags."""
import re

_TAG_RE = re.compile(r"<[^>]*>")

def sanitize_text(value: str | None) -> str:
    """Strip HTML/XML tags from *value*. Returns empty string for None."""
    if value is None:
        return ""
    return _TAG_RE.sub("", str(value)).strip()
