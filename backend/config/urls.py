"""Top-level URL conf.

Apps register their endpoints under /api/v1/. This file gets extended as we
add the accounts and kyc apps.
"""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path


def _healthcheck(_request):
    return HttpResponse("ok")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", _healthcheck),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("kyc.urls")),
]
