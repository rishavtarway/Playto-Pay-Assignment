"""Seed the database with one reviewer and two merchants for graders.

Idempotent: re-running the command does not create duplicates. Merchant 2 is
seeded with submitted_at 30 hours ago so it shows up as **at_risk** in the
reviewer dashboard immediately.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework.authtoken.models import Token

from kyc.models import Document, Submission

User = get_user_model()

# A tiny but valid PDF so the magic-byte sniff does not reject it.
_TINY_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type /Catalog /Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type /Pages /Count 0>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


class Command(BaseCommand):
    help = "Seed: 2 merchants + 1 reviewer with test data."

    def handle(self, *args, **kwargs):
        # Reviewer
        reviewer, _ = User.objects.get_or_create(
            email="reviewer@playto.test",
            defaults={"username": "reviewer", "role": User.ROLE_REVIEWER},
        )
        reviewer.role = User.ROLE_REVIEWER
        reviewer.set_password("reviewer123")
        reviewer.save()
        Token.objects.get_or_create(user=reviewer)

        # Merchant 1 — half-filled draft, no documents.
        m1, _ = User.objects.get_or_create(
            email="draft@playto.test",
            defaults={"username": "draft_merchant", "role": User.ROLE_MERCHANT},
        )
        m1.role = User.ROLE_MERCHANT
        m1.set_password("merchant123")
        m1.save()
        Token.objects.get_or_create(user=m1)
        Submission.objects.update_or_create(
            merchant=m1,
            defaults={
                "full_name": "Aryan Shah",
                "email": "draft@playto.test",
                "phone": "9999900001",
                "state": "draft",
            },
        )

        # Merchant 2 — fully filled, three documents, under_review, AT RISK (30h ago).
        m2, _ = User.objects.get_or_create(
            email="review@playto.test",
            defaults={"username": "review_merchant", "role": User.ROLE_MERCHANT},
        )
        m2.role = User.ROLE_MERCHANT
        m2.set_password("merchant123")
        m2.save()
        Token.objects.get_or_create(user=m2)
        sub2, _ = Submission.objects.update_or_create(
            merchant=m2,
            defaults={
                "full_name": "Priya Mehta",
                "email": "review@playto.test",
                "phone": "9876543210",
                "business_name": "Mehta Designs",
                "business_type": "freelance",
                "expected_monthly_volume_usd": 2000,
                "state": "under_review",
                "assigned_reviewer": reviewer,
                "submitted_at": timezone.now() - timedelta(hours=30),
            },
        )

        # Attach one document per kind if not already there.
        for kind in ("pan", "aadhaar", "bank_statement"):
            if not sub2.documents.filter(kind=kind).exists():
                doc = Document(
                    submission=sub2,
                    kind=kind,
                    original_name=f"{kind}.pdf",
                    content_type="application/pdf",
                    size_bytes=len(_TINY_PDF_BYTES),
                )
                doc.file.save(f"{kind}.pdf", ContentFile(_TINY_PDF_BYTES), save=True)

        self.stdout.write(self.style.SUCCESS(
            "\nSeeded!\n"
            "  Reviewer:   reviewer@playto.test / reviewer123\n"
            "  Merchant 1: draft@playto.test  / merchant123  (state=draft)\n"
            "  Merchant 2: review@playto.test / merchant123  (state=under_review, AT RISK)\n"
        ))
