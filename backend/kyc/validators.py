"""File upload validation: size, extension, and magic-byte sniff.

We do NOT trust ``file.content_type`` from the client because that header is
trivially spoofable. We sniff the actual file bytes with python-magic.
"""

import os

from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# A few well-known magic-byte prefixes — used as fallback if libmagic is absent.
_MAGIC_SIGNATURES = (
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
)


# Sniff the first chunk of a file; return the detected MIME type or "".
def _sniff_mime(header: bytes) -> str:
    try:
        import magic  # python-magic, optional dependency

        return magic.from_buffer(header, mime=True) or ""
    except Exception:
        # Fallback: match against our known signatures.
        for prefix, mime in _MAGIC_SIGNATURES:
            if header.startswith(prefix):
                return mime
        return ""


# Run all three checks in cheapest-first order. Raises ValidationError on fail.
def validate_document_file(file) -> None:
    # 1. Size — cheapest check, no I/O needed.
    if file.size > MAX_SIZE_BYTES:
        mb = file.size / (1024 * 1024)
        raise ValidationError(f"File too large ({mb:.1f} MB). Maximum is 5 MB.")

    # 2. Extension — quick client-side hint check.
    ext = os.path.splitext(file.name or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"File type '{ext or 'unknown'}' not allowed. Accepted: PDF, JPG, PNG."
        )

    # 3. Magic bytes — the real security check.
    file.seek(0)
    header = file.read(2048)
    file.seek(0)  # CRITICAL: reset so the storage backend writes the full file.

    detected = _sniff_mime(header)
    if detected not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            f"File content does not match a supported type (detected: {detected or 'unknown'})."
        )
