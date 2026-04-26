"""Serializers for the KYC API."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import Document, DocumentKind, Submission
from .validators import validate_document_file


# Returned wherever we expose a document.
class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "kind",
            "file",
            "file_url",
            "original_name",
            "content_type",
            "size_bytes",
            "uploaded_at",
        ]
        read_only_fields = ["id", "original_name", "content_type", "size_bytes", "uploaded_at", "file_url"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request is not None:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url if obj.file else None

    def validate_kind(self, value):
        if value not in DocumentKind.values:
            raise serializers.ValidationError("kind must be pan, aadhaar, or bank_statement.")
        return value

    def validate_file(self, value):
        # Single source of truth for upload validation.
        from django.core.exceptions import ValidationError as DjangoValidationError

        try:
            validate_document_file(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages[0] if exc.messages else str(exc))
        return value


# Used for full submission detail (merchant's own + reviewer's view).
class SubmissionSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)
    merchant_email = serializers.EmailField(source="merchant.email", read_only=True)
    assigned_reviewer_email = serializers.EmailField(
        source="assigned_reviewer.email", read_only=True, default=None,
    )
    time_in_queue_seconds = serializers.SerializerMethodField()
    is_at_risk = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id",
            "merchant_email",
            "assigned_reviewer_email",
            "full_name",
            "email",
            "phone",
            "business_name",
            "business_type",
            "expected_monthly_volume_usd",
            "state",
            "rejection_reason",
            "info_request_reason",
            "created_at",
            "updated_at",
            "submitted_at",
            "time_in_queue_seconds",
            "is_at_risk",
            "documents",
        ]
        read_only_fields = [
            "id",
            "merchant_email",
            "assigned_reviewer_email",
            "state",
            "rejection_reason",
            "info_request_reason",
            "created_at",
            "updated_at",
            "submitted_at",
            "time_in_queue_seconds",
            "is_at_risk",
            "documents",
        ]

    # Total seconds the submission has been waiting in the queue (computed live).
    def get_time_in_queue_seconds(self, obj):
        if obj.submitted_at is None:
            return None
        delta = timezone.now() - obj.submitted_at
        return int(delta.total_seconds())

    # SLA flag: true if waiting > 24 hours. Computed dynamically — never stored.
    def get_is_at_risk(self, obj):
        if obj.submitted_at is None:
            return False
        return (timezone.now() - obj.submitted_at) > timedelta(hours=24)


# Slim version used for the queue list (drops free-text reasons, keeps SLA bits).
class QueueItemSerializer(serializers.ModelSerializer):
    merchant_email = serializers.EmailField(source="merchant.email", read_only=True)
    assigned_reviewer_email = serializers.EmailField(
        source="assigned_reviewer.email", read_only=True, default=None,
    )
    time_in_queue_seconds = serializers.SerializerMethodField()
    is_at_risk = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id",
            "merchant_email",
            "assigned_reviewer_email",
            "full_name",
            "business_name",
            "business_type",
            "expected_monthly_volume_usd",
            "state",
            "submitted_at",
            "time_in_queue_seconds",
            "is_at_risk",
        ]

    def get_time_in_queue_seconds(self, obj):
        if obj.submitted_at is None:
            return None
        delta = timezone.now() - obj.submitted_at
        return int(delta.total_seconds())

    def get_is_at_risk(self, obj):
        if obj.submitted_at is None:
            return False
        return (timezone.now() - obj.submitted_at) > timedelta(hours=24)
