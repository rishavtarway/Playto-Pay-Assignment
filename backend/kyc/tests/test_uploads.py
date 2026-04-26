"""File upload validation tests."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from kyc.models import Submission

# A minimal but valid PDF for the magic-byte sniff.
_VALID_PDF = b"%PDF-1.4\n1 0 obj<</Type /Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


# Helper: create a SimpleUploadedFile from bytes + filename + mime.
def _f(name: str, data: bytes, content_type: str) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, data, content_type=content_type)


@pytest.fixture
def auth(api_client, merchant_a_token):
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {merchant_a_token}")
    return api_client


# 6 MB upload is rejected by the serializer-level size validator.
def test_file_too_large_rejected(auth, merchant_a):
    Submission.objects.create(merchant=merchant_a)
    big = _f("big.pdf", b"%PDF-" + b"x" * (5 * 1024 * 1024 + 100), "application/pdf")
    response = auth.post(
        "/api/v1/submissions/me/documents/",
        {"kind": "pan", "file": big},
        format="multipart",
    )
    assert response.status_code == 400
    assert "too large" in str(response.data).lower()


# A renamed .exe is rejected because the extension is not in the allowlist.
def test_wrong_extension_rejected(auth, merchant_a):
    Submission.objects.create(merchant=merchant_a)
    exe = _f("virus.exe", b"MZ\x90\x00fakebytes", "application/octet-stream")
    response = auth.post(
        "/api/v1/submissions/me/documents/",
        {"kind": "pan", "file": exe},
        format="multipart",
    )
    assert response.status_code == 400


# A .pdf-named file with non-PDF content is rejected by the magic-byte check.
def test_spoofed_extension_rejected_by_magic_bytes(auth, merchant_a):
    Submission.objects.create(merchant=merchant_a)
    bad = _f("evil.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")
    response = auth.post(
        "/api/v1/submissions/me/documents/",
        {"kind": "pan", "file": bad},
        format="multipart",
    )
    assert response.status_code == 400


# Happy path: a valid PDF is accepted and a Document row is created.
def test_valid_pdf_accepted(auth, merchant_a):
    submission = Submission.objects.create(merchant=merchant_a)
    response = auth.post(
        "/api/v1/submissions/me/documents/",
        {"kind": "pan", "file": _f("pan.pdf", _VALID_PDF, "application/pdf")},
        format="multipart",
    )
    assert response.status_code == 201, response.data
    assert submission.documents.count() == 1
    assert submission.documents.first().kind == "pan"
