"""KYC API views.

Two halves:

* **Merchant views** — scoped to ``request.user``'s own submission via
  ``Submission.objects.filter(merchant=user)`` / ``get_or_create``. Cross-
  merchant access is impossible by construction.
* **Reviewer views** — see every submission and use the central state machine
  for every transition.

Anything that mutates ``submission.state`` goes through
:func:`kyc.state_machine.transition`. Validation errors return our standard
``{"error": ..., "detail": ...}`` shape via the custom exception handler.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Avg, DurationField, ExpressionWrapper, F
from django.db.models.functions import Now
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .assignment import assign_reviewer_if_needed
from .models import Document, DocumentKind, Submission, SubmissionState
from .permissions import IsMerchant, IsReviewer
from .serializers import DocumentSerializer, QueueItemSerializer, SubmissionSerializer
from .state_machine import transition

# ---------------------------------------------------------------------------
# Constants — single source of truth, used by both the merchant and reviewer
# halves of the API.
# ---------------------------------------------------------------------------

# Fields a merchant is allowed to write directly via PATCH.
_MERCHANT_WRITE_FIELDS = (
    "full_name",
    "email",
    "phone",
    "business_name",
    "business_type",
    "expected_monthly_volume_usd",
)

# States in which the merchant can still edit their submission. Anything
# outside this set means "locked, in flight" or "terminal".
_EDITABLE_STATES = (
    SubmissionState.DRAFT,
    SubmissionState.MORE_INFO_REQUESTED,
)

# Open submissions — what the reviewer queue + metrics show.
_OPEN_STATES = (
    SubmissionState.SUBMITTED,
    SubmissionState.UNDER_REVIEW,
    SubmissionState.MORE_INFO_REQUESTED,
)

# Terminal submissions, used by the approval-rate metric.
_TERMINAL_STATES = (SubmissionState.APPROVED, SubmissionState.REJECTED)

_APPROVAL_RATE_WINDOW = timedelta(days=7)


# ---------------------------------------------------------------------------
# Tiny helpers — kept private so callers stay readable.
# ---------------------------------------------------------------------------

def _bad_request(error: str, detail) -> Response:
    """Build a 400 with our standard error envelope."""
    return Response({"error": error, "detail": detail}, status=status.HTTP_400_BAD_REQUEST)


def _illegal_state_response(action: str, current_state: str) -> Response:
    return _bad_request(
        "illegal_transition",
        f"Cannot {action} in state '{current_state}'.",
    )


def _get_or_create_submission(user) -> Submission:
    submission, _ = Submission.objects.get_or_create(merchant=user)
    return submission


def _is_editable(submission: Submission) -> bool:
    return submission.state in _EDITABLE_STATES


# ---------------------------------------------------------------------------
# Merchant views
# ---------------------------------------------------------------------------

# GET / PATCH /api/v1/submissions/me/  — get-or-create the merchant's draft.
class MerchantSubmissionView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def get(self, request):
        submission = _get_or_create_submission(request.user)
        return Response(self._serialize(submission, request))

    def patch(self, request):
        submission = _get_or_create_submission(request.user)
        if not _is_editable(submission):
            return _illegal_state_response("edit submission", submission.state)

        # Whitelist what the merchant can write — never trust the wire shape.
        payload = {
            field: value
            for field, value in request.data.items()
            if field in _MERCHANT_WRITE_FIELDS
        }
        serializer = SubmissionSerializer(
            submission, data=payload, partial=True, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @staticmethod
    def _serialize(submission, request):
        return SubmissionSerializer(submission, context={"request": request}).data


# POST /api/v1/submissions/me/documents/  — upload one document.
class MerchantDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        submission = _get_or_create_submission(request.user)
        if not _is_editable(submission):
            return _illegal_state_response("upload documents", submission.state)

        file_obj = request.FILES.get("file")
        if not file_obj:
            return _bad_request("validation", {"file": ["This field is required."]})

        kind = request.data.get("kind")
        # Validate before touching the existing record on disk.
        serializer = DocumentSerializer(
            data={"kind": kind, "file": file_obj}, context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        _replace_existing_document(submission, kind)
        document = _create_document(submission, kind, file_obj)
        return Response(
            DocumentSerializer(document, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


def _replace_existing_document(submission: Submission, kind: str) -> None:
    """Delete any prior document of the same kind so the new one can take its place."""
    existing = submission.documents.filter(kind=kind).first()
    if existing is None:
        return
    existing.file.delete(save=False)
    existing.delete()


def _create_document(submission: Submission, kind: str, file_obj) -> Document:
    return Document.objects.create(
        submission=submission,
        kind=kind,
        file=file_obj,
        original_name=file_obj.name,
        content_type=getattr(file_obj, "content_type", "") or "",
        size_bytes=file_obj.size,
    )


# DELETE /api/v1/submissions/me/documents/<id>/  — remove a document.
class MerchantDocumentDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def delete(self, request, doc_id):
        submission = get_object_or_404(Submission, merchant=request.user)
        if not _is_editable(submission):
            return _illegal_state_response("delete documents", submission.state)

        document = get_object_or_404(Document, id=doc_id, submission=submission)
        document.file.delete(save=False)
        document.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# POST /api/v1/submissions/me/submit/  — move draft → submitted.
class MerchantSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsMerchant]

    def post(self, request):
        # get-or-create so a brand-new merchant who never PATCHed their draft
        # still gets a meaningful 400 ("required fields missing") instead of
        # a confusing 404.
        submission = _get_or_create_submission(request.user)

        missing_fields = _missing_required_fields(submission)
        if missing_fields:
            return _bad_request(
                "validation",
                {field: ["This field is required."] for field in missing_fields},
            )

        missing_docs = _missing_required_documents(submission)
        if missing_docs:
            return _bad_request(
                "validation",
                {"documents": [f"Missing: {', '.join(missing_docs)}"]},
            )

        # Hand off to the state machine. Illegal transitions raise → 400.
        transition(submission, SubmissionState.SUBMITTED, actor=request.user)
        submission.refresh_from_db()
        return Response(
            SubmissionSerializer(submission, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


def _missing_required_fields(submission: Submission) -> list[str]:
    """Return the names of any required-but-blank fields on ``submission``."""
    # is-None / empty-string only — Decimal(0) volume must NOT be flagged.
    return [
        field for field in _MERCHANT_WRITE_FIELDS
        if getattr(submission, field) in (None, "")
    ]


def _missing_required_documents(submission: Submission) -> list[str]:
    """Return the document kinds the merchant still has to upload."""
    uploaded = set(submission.documents.values_list("kind", flat=True))
    required = set(DocumentKind.values)
    return sorted(required - uploaded)


# ---------------------------------------------------------------------------
# Reviewer views
# ---------------------------------------------------------------------------

def _open_queue_qs():
    """Annotated queryset shared by queue + metrics endpoints."""
    return (
        Submission.objects
        .filter(state__in=_OPEN_STATES)
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
        queue = _open_queue_qs()
        return Response(
            QueueItemSerializer(queue, many=True, context={"request": request}).data
        )


# GET /api/v1/reviews/<id>/
class ReviewerSubmissionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsReviewer]

    def get(self, request, submission_id):
        submission = get_object_or_404(
            Submission.objects
                .select_related("merchant", "assigned_reviewer")
                .prefetch_related("documents"),
            id=submission_id,
        )
        return Response(
            SubmissionSerializer(submission, context={"request": request}).data
        )


# Shared base for the four reviewer action endpoints — keeps them DRY.
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
                return _bad_request("validation", {"reason": ["This field is required."]})

            assigned_reviewer = self._pick_reviewer(submission, request.user)
            transition(
                submission,
                self.target_state,
                actor=request.user,
                reason=reason,
                assigned_reviewer=assigned_reviewer,
            )
            submission.refresh_from_db()
            return Response(
                SubmissionSerializer(submission, context={"request": request}).data
            )

    def _pick_reviewer(self, submission, actor):
        """Round-robin only when starting a review; pass-through otherwise."""
        if self.target_state != SubmissionState.UNDER_REVIEW:
            return None
        return assign_reviewer_if_needed(submission) or actor


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
        in_queue, avg_seconds = _compute_queue_metrics()
        approval_rate, decided = _compute_approval_rate(window=_APPROVAL_RATE_WINDOW)
        return Response({
            "in_queue":                  in_queue,
            "avg_time_in_queue_seconds": avg_seconds,
            "approval_rate_7d":          approval_rate,
            "decided_last_7d":           decided,
        })


def _compute_queue_metrics() -> tuple[int, int]:
    """Return ``(in_queue, avg_time_in_queue_seconds)`` for the open queue."""
    queue = _open_queue_qs().filter(submitted_at__isnull=False)
    aggregate = queue.aggregate(avg=Avg("time_in_queue"))
    avg_duration = aggregate["avg"]
    avg_seconds = round(avg_duration.total_seconds()) if avg_duration else 0
    in_queue = _open_queue_qs().count()
    return in_queue, avg_seconds


def _compute_approval_rate(window: timedelta) -> tuple[float, int]:
    """Return ``(approval_rate, decided_count)`` over the given window."""
    cutoff = timezone.now() - window
    decided_qs = Submission.objects.filter(
        updated_at__gte=cutoff, state__in=_TERMINAL_STATES,
    )
    total = decided_qs.count()
    if total == 0:
        return 0.0, 0
    approved = decided_qs.filter(state=SubmissionState.APPROVED).count()
    return round(approved / total, 4), total
