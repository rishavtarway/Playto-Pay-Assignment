"""KYC API views.

Merchant endpoints work on the caller's own submission only — scoping is
enforced by ``Submission.objects.filter(merchant=request.user)`` (or
``get_or_create``) so cross-merchant access is impossible by construction.
Reviewer endpoints can see every submission and use the central state machine
for every transition.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import DurationField, ExpressionWrapper, F
from django.db.models.functions import Now
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Document, DocumentKind, Submission, SubmissionState
from .permissions import IsMerchant, IsReviewer
from .serializers import DocumentSerializer, QueueItemSerializer, SubmissionSerializer
from .state_machine import transition

# Fields a merchant is allowed to write directly on their submission.
_MERCHANT_WRITE_FIELDS = (
    "full_name",
    "email",
    "phone",
    "business_name",
    "business_type",
    "expected_monthly_volume_usd",
)
# States in which the merchant can still edit their submission.
_EDITABLE_STATES = (SubmissionState.DRAFT, SubmissionState.MORE_INFO_REQUESTED)


# GET / PATCH /api/v1/submissions/me/  — get-or-create the merchant's draft.
class MerchantSubmissionView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def _get_or_create(self, user):
        submission, _ = Submission.objects.get_or_create(merchant=user)
        return submission

    def get(self, request):
        submission = self._get_or_create(request.user)
        return Response(SubmissionSerializer(submission, context={"request": request}).data)

    def patch(self, request):
        submission = self._get_or_create(request.user)
        if submission.state not in _EDITABLE_STATES:
            return Response(
                {
                    "error": "illegal_transition",
                    "detail": f"Cannot edit submission in state '{submission.state}'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Only let the merchant write a known whitelist of fields.
        payload = {k: v for k, v in request.data.items() if k in _MERCHANT_WRITE_FIELDS}
        serializer = SubmissionSerializer(
            submission, data=payload, partial=True, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# POST /api/v1/submissions/me/documents/  — upload one document.
class MerchantDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        submission, _ = Submission.objects.get_or_create(merchant=request.user)
        if submission.state not in _EDITABLE_STATES:
            return Response(
                {
                    "error": "illegal_transition",
                    "detail": f"Cannot upload documents in state '{submission.state}'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        kind = request.data.get("kind")
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response(
                {"error": "validation", "detail": {"file": ["This field is required."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate before touching the existing record on disk.
        serializer = DocumentSerializer(
            data={"kind": kind, "file": file_obj}, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        # Replace existing document of the same kind: delete the old file from disk first.
        existing = submission.documents.filter(kind=kind).first()
        if existing is not None:
            existing.file.delete(save=False)
            existing.delete()

        document = Document.objects.create(
            submission=submission,
            kind=kind,
            file=file_obj,
            original_name=file_obj.name,
            content_type=getattr(file_obj, "content_type", "") or "",
            size_bytes=file_obj.size,
        )
        return Response(
            DocumentSerializer(document, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# DELETE /api/v1/submissions/me/documents/<id>/  — remove a document.
class MerchantDocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def delete(self, request, doc_id):
        submission = get_object_or_404(Submission, merchant=request.user)
        if submission.state not in _EDITABLE_STATES:
            return Response(
                {
                    "error": "illegal_transition",
                    "detail": f"Cannot delete documents in state '{submission.state}'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        document = get_object_or_404(Document, id=doc_id, submission=submission)
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# POST /api/v1/submissions/me/submit/  — move draft → submitted.
class MerchantSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def post(self, request):
        submission = get_object_or_404(Submission, merchant=request.user)

        # Validate every required field is present.
        required = [
            "full_name", "email", "phone",
            "business_name", "business_type", "expected_monthly_volume_usd",
        ]
        missing = [f for f in required if not getattr(submission, f)]
        if missing:
            return Response(
                {"error": "validation", "detail": {f: ["This field is required."] for f in missing}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # All three documents must be uploaded.
        uploaded_kinds = set(submission.documents.values_list("kind", flat=True))
        required_kinds = set(DocumentKind.values)
        missing_docs = sorted(required_kinds - uploaded_kinds)
        if missing_docs:
            return Response(
                {"error": "validation", "detail": {"documents": [f"Missing: {', '.join(missing_docs)}"]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Hand off to the state machine — illegal transitions raise → 400.
        transition(submission, SubmissionState.SUBMITTED, actor=request.user)
        submission.refresh_from_db()
        return Response(
            SubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


# ---------- Reviewer ----------

# Annotated queryset shared by queue + metrics endpoints.
def _open_queue_qs():
    open_states = (
        SubmissionState.SUBMITTED,
        SubmissionState.UNDER_REVIEW,
        SubmissionState.MORE_INFO_REQUESTED,
    )
    return (
        Submission.objects
        .filter(state__in=open_states)
        .select_related("merchant", "assigned_reviewer")
        .prefetch_related("documents")
        .annotate(
            time_in_queue=ExpressionWrapper(
                Now() - F("submitted_at"), output_field=DurationField(),
            )
        )
        .order_by("submitted_at")
    )


# GET /api/v1/reviews/queue/
class ReviewerQueueView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        qs = _open_queue_qs()
        serializer = QueueItemSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


# GET /api/v1/reviews/<id>/
class ReviewerSubmissionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request, submission_id):
        submission = get_object_or_404(
            Submission.objects.select_related("merchant", "assigned_reviewer").prefetch_related("documents"),
            id=submission_id,
        )
        return Response(SubmissionSerializer(submission, context={"request": request}).data)


# Helper to keep the four action endpoints DRY.
class _ReviewerAction(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]
    target_state: str = ""
    require_reason: bool = False

    def post(self, request, submission_id):
        with transaction.atomic():
            submission = get_object_or_404(
                Submission.objects.select_for_update(),
                id=submission_id,
            )
            reason = (request.data.get("reason") or "").strip()
            if self.require_reason and not reason:
                return Response(
                    {"error": "validation", "detail": {"reason": ["This field is required."]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            assigned = None
            if self.target_state == SubmissionState.UNDER_REVIEW and submission.assigned_reviewer_id is None:
                assigned = request.user
            transition(
                submission,
                self.target_state,
                actor=request.user,
                reason=reason,
                assigned_reviewer=assigned,
            )
            submission.refresh_from_db()
            return Response(SubmissionSerializer(submission, context={"request": request}).data)


# POST /api/v1/reviews/<id>/start/
class ReviewerStartView(_ReviewerAction):
    target_state = SubmissionState.UNDER_REVIEW


# POST /api/v1/reviews/<id>/approve/
class ReviewerApproveView(_ReviewerAction):
    target_state = SubmissionState.APPROVED


# POST /api/v1/reviews/<id>/reject/  — reason required.
class ReviewerRejectView(_ReviewerAction):
    target_state = SubmissionState.REJECTED
    require_reason = True


# POST /api/v1/reviews/<id>/request-info/  — reason required.
class ReviewerRequestInfoView(_ReviewerAction):
    target_state = SubmissionState.MORE_INFO_REQUESTED
    require_reason = True


# GET /api/v1/reviews/metrics/
class ReviewerMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request):
        now = timezone.now()
        open_qs = _open_queue_qs()
        in_queue = open_qs.count()

        # Average time in queue across all currently-open submissions.
        total_seconds = 0.0
        considered = 0
        for sub in open_qs:
            if sub.submitted_at is None:
                continue
            total_seconds += (now - sub.submitted_at).total_seconds()
            considered += 1
        avg_seconds = round(total_seconds / considered) if considered else 0

        # Approval rate over the last 7 days (terminal states only).
        cutoff = now - timedelta(days=7)
        terminal = Submission.objects.filter(
            updated_at__gte=cutoff,
            state__in=(SubmissionState.APPROVED, SubmissionState.REJECTED),
        )
        total = terminal.count()
        approved = terminal.filter(state=SubmissionState.APPROVED).count()
        approval_rate = round(approved / total, 4) if total else 0.0

        return Response(
            {
                "in_queue": in_queue,
                "avg_time_in_queue_seconds": avg_seconds,
                "approval_rate_7d": approval_rate,
                "decided_last_7d": total,
            }
        )
