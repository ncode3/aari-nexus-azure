import re
import unicodedata
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    name = unicodedata.normalize("NFKC", Path(filename).name)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = re.sub(r"[^A-Za-z0-9._() -]", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name or name in {".", ".."}:
        raise ValueError("Filename is empty after sanitization")
    return name[:240]

