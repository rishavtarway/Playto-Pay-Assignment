"""KYC API URL conf — everything namespaced under /api/v1/."""

from django.urls import path

from .views import (
    MerchantDocumentDeleteView,
    MerchantDocumentUploadView,
    MerchantSubmissionView,
    MerchantSubmitView,
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
]
