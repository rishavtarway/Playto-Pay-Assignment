"""KYC API URL conf — everything namespaced under /api/v1/."""

from django.urls import path

from .views import (
    MerchantDocumentDeleteView,
    MerchantDocumentUploadView,
    MerchantSubmissionView,
    MerchantSubmitView,
    ReviewerApproveView,
    ReviewerMetricsView,
    ReviewerQueueView,
    ReviewerRejectView,
    ReviewerRequestInfoView,
    ReviewerStartView,
    ReviewerSubmissionDetailView,
)

urlpatterns = [
    # Merchant
    path("submissions/me/", MerchantSubmissionView.as_view(), name="merchant-submission"),
    path(
        "submissions/me/documents/",
        MerchantDocumentUploadView.as_view(),
        name="merchant-document-upload",
    ),
    path(
        "submissions/me/documents/<uuid:doc_id>/",
        MerchantDocumentDeleteView.as_view(),
        name="merchant-document-delete",
    ),
    path("submissions/me/submit/", MerchantSubmitView.as_view(), name="merchant-submit"),

    # Reviewer
    path("reviews/queue/", ReviewerQueueView.as_view(), name="reviewer-queue"),
    path("reviews/metrics/", ReviewerMetricsView.as_view(), name="reviewer-metrics"),
    path("reviews/<uuid:submission_id>/", ReviewerSubmissionDetailView.as_view(), name="reviewer-detail"),
    path("reviews/<uuid:submission_id>/start/", ReviewerStartView.as_view(), name="reviewer-start"),
    path("reviews/<uuid:submission_id>/approve/", ReviewerApproveView.as_view(), name="reviewer-approve"),
    path("reviews/<uuid:submission_id>/reject/", ReviewerRejectView.as_view(), name="reviewer-reject"),
    path(
        "reviews/<uuid:submission_id>/request-info/",
        ReviewerRequestInfoView.as_view(),
        name="reviewer-request-info",
    ),
]
