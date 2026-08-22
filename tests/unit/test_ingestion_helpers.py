from app.ingestion.checksum import sha256_bytes
from app.ingestion.filenames import sanitize_filename


def test_checksum_is_deterministic() -> None:
    assert sha256_bytes(b"aari") == sha256_bytes(b"aari")
    assert len(sha256_bytes(b"aari")) == 64


def test_filename_is_sanitized() -> None:
    assert sanitize_filename("../../private résumé.pdf") == "private r_sum_.pdf"

