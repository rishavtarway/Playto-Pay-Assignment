"""Submission, Document, and Notification models.

Submission carries the personal + business data and the state field. Document
holds the uploaded files (one per kind per submission). Notification records
every state change so we can prove what *should* have been emailed.
"""

import uuid

from django.conf import settings
from django.db import models


# All KYC states. Transitions between them are enforced in kyc/state_machine.py.
class SubmissionState(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    UNDER_REVIEW = "under_review", "Under Review"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    MORE_INFO_REQUESTED = "more_info_requested", "More Info Requested"


class Submission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # OneToOne — every merchant owns exactly one Submission. The DB-level
    # uniqueness keeps get_or_create(merchant=user) safe under concurrent
    # requests (no MultipleObjectsReturned later).
    merchant = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submission",
    )
    assigned_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_submissions",
    )

    # Personal details — collected in step 1 of the wizard.
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Business details — step 2 of the wizard.
    business_name = models.CharField(max_length=255, blank=True)
    business_type = models.CharField(max_length=100, blank=True)
    expected_monthly_volume_usd = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )

    # State + reviewer feedback fields.
    state = models.CharField(
        max_length=30,
        choices=SubmissionState.choices,
        default=SubmissionState.DRAFT,
    )
    rejection_reason = models.TextField(blank=True)
    info_request_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Set the first time the submission moves to "submitted".
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Index supports the queue's "oldest first" ordering.
        indexes = [models.Index(fields=["state", "submitted_at"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.merchant.email} — {self.state}"


# Where uploaded documents live on disk: media/submissions/<sub_id>/<kind>/<file>.
def document_upload_path(instance, filename):
    return f"submissions/{instance.submission_id}/{instance.kind}/{filename}"


class DocumentKind(models.TextChoices):
    PAN = "pan", "PAN"
    AADHAAR = "aadhaar", "Aadhaar"
    BANK_STATEMENT = "bank_statement", "Bank Statement"


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="documents",
    )
    kind = models.CharField(max_length=30, choices=DocumentKind.choices)
    file = models.FileField(upload_to=document_upload_path)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Re-uploading the same kind replaces the old document.
        unique_together = [("submission", "kind")]
        ordering = ["kind"]

    def __str__(self) -> str:
        return f"{self.kind} for {self.submission_id}"


class Notification(models.Model):
    """Log of state-change events. Source of truth for "what should have been sent"."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications",
    )
    submission = models.ForeignKey(
        Submission, on_delete=models.CASCADE, related_name="notifications",
    )
    event_type = models.CharField(max_length=50)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.created_at:%Y-%m-%d %H:%M:%S}"
