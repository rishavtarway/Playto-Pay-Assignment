"""Serializers for the KYC API.

Two views exist on :class:`Submission`:

* :class:`SubmissionSerializer` — full detail (merchant + reviewer pages).
* :class:`QueueItemSerializer`  — slim list shape for the reviewer queue.

The queue-time and SLA logic is identical for both, so it lives in
:class:`_QueueTimingMixin` and is mixed in once per serializer.
"""

from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import Document, DocumentKind, Submission
from .validators import validate_document_file

# A submission waiting longer than this is flagged ``is_at_risk = True``.
# Computed dynamically — we never store the flag (would go stale).
SLA_THRESHOLD = timedelta(hours=24)


class DocumentSerializer(serializers.ModelSerializer):
    """Returned wherever we expose a document (uploads + submission detail)."""

    file = serializers.FileField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "kind", "file", "file_url",
            "original_name", "content_type", "size_bytes", "uploaded_at",
        ]
        read_only_fields = [
            "id", "original_name", "content_type", "size_bytes", "uploaded_at", "file_url",
        ]

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(obj.file.url) if request else obj.file.url

    def validate_kind(self, value):
        if value not in DocumentKind.values:
            raise serializers.ValidationError("kind must be pan, aadhaar, or bank_statement.")
        return value

    def validate_file(self, value):
        # Single source of truth for upload validation lives in validators.py.
        try:
            validate_document_file(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0] if exc.messages else str(exc))
        return value


class _QueueTimingMixin(serializers.Serializer):
    """Adds ``time_in_queue_seconds`` and ``is_at_risk`` to a Submission serializer."""

    time_in_queue_seconds = serializers.SerializerMethodField()
    is_at_risk = serializers.SerializerMethodField()

    def get_time_in_queue_seconds(self, obj):
        wait = _waiting_duration(obj)
        return int(wait.total_seconds()) if wait is not None else None

    def get_is_at_risk(self, obj):
        wait = _waiting_duration(obj)
        return wait is not None and wait > SLA_THRESHOLD


def _waiting_duration(submission) -> timedelta | None:
    """How long the submission has been waiting since it entered the queue."""
    if submission.submitted_at is None:
        return None
    return timezone.now() - submission.submitted_at


class SubmissionSerializer(_QueueTimingMixin, serializers.ModelSerializer):
    """Full submission detail for the merchant's own view + reviewer detail page."""

    documents = DocumentSerializer(many=True, read_only=True)
    merchant_email = serializers.EmailField(source="merchant.email", read_only=True)
    assigned_reviewer_email = serializers.EmailField(
        source="assigned_reviewer.email", read_only=True, default=None,
    )

    class Meta:
        model = Submission
        fields = [
            "id",
            "merchant_email",
            "assigned_reviewer_email",
            "full_name", "email", "phone",
            "business_name", "business_type", "expected_monthly_volume_usd",
            "state",
            "rejection_reason", "info_request_reason",
            "created_at", "updated_at", "submitted_at",
            "time_in_queue_seconds", "is_at_risk",
            "documents",
        ]
        read_only_fields = [
            "id",
            "merchant_email",
            "assigned_reviewer_email",
            "state",
            "rejection_reason", "info_request_reason",
            "created_at", "updated_at", "submitted_at",
            "time_in_queue_seconds", "is_at_risk",
            "documents",
        ]


class QueueItemSerializer(_QueueTimingMixin, serializers.ModelSerializer):
    """Slim row shape for the reviewer queue list — drops free-text reasons."""

    merchant_email = serializers.EmailField(source="merchant.email", read_only=True)
    assigned_reviewer_email = serializers.EmailField(
        source="assigned_reviewer.email", read_only=True, default=None,
    )

    class Meta:
        model = Submission
        fields = [
            "id",
            "merchant_email",
            "assigned_reviewer_email",
            "full_name",
            "business_name", "business_type", "expected_monthly_volume_usd",
            "state",
            "submitted_at",
            "time_in_queue_seconds", "is_at_risk",
        ]
