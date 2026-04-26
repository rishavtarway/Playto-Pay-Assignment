"""File-upload validation for KYC documents.

Three independent checks, run cheapest-first:

    size  ->  extension  ->  magic-bytes

We never trust ``file.content_type`` from the client (trivially spoofable).
Each helper does one thing and raises ``ValidationError`` with a message that
makes sense to the merchant.
"""

import os

from django.core.exceptions import ValidationError

# Limits and accept-lists. Single source of truth — used by both the upload
# endpoint and the documentation in EXPLAINER.md.
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})
ALLOWED_MIME_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png"})

# Header bytes we read for the magic-byte sniff. 2 KB is enough for libmagic
# to identify any of our accepted formats reliably.
_HEADER_READ_BYTES = 2048

# Fallback magic-byte signatures used when python-magic isn't installed.
# Order doesn't matter — we look for an exact prefix match.
_FALLBACK_SIGNATURES = (
    (b"%PDF-",                  "application/pdf"),
    (b"\xff\xd8\xff",            "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n",       "image/png"),
)


def validate_document_file(file) -> None:
    """Raise ``ValidationError`` if the file fails any of the three checks."""
    _check_size(file)
    _check_extension(file)
    _check_magic_bytes(file)


def _check_size(file) -> None:
    if file.size > MAX_SIZE_BYTES:
        size_mb = file.size / (1024 * 1024)
        raise ValidationError(f"File too large ({size_mb:.1f} MB). Maximum is 5 MB.")


def _check_extension(file) -> None:
    extension = os.path.splitext(file.name or "")[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"File type '{extension or 'unknown'}' not allowed. Accepted: PDF, JPG, PNG."
        )


def _check_magic_bytes(file) -> None:
    """Sniff the actual file content. The real security check."""
    file.seek(0)
    header = file.read(_HEADER_READ_BYTES)
    file.seek(0)  # CRITICAL: reset so the storage backend writes the full file.

    detected = _sniff_mime(header)
    if detected not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"File content does not match a supported type (detected: {detected or 'unknown'})."
        )


def _sniff_mime(header: bytes) -> str:
    """Return the detected MIME type for ``header``, or ``""`` if unknown."""
    try:
        import magic  # python-magic, optional dependency

        return magic.from_buffer(header, mime=True) or ""
    except Exception:
        return _sniff_with_fallback_signatures(header)


def _sniff_with_fallback_signatures(header: bytes) -> str:
    for prefix, mime in _FALLBACK_SIGNATURES:
        if header.startswith(prefix):
            return mime
    return ""
