"""Top-level URL conf.

API endpoints live under /api/v1/. In production we also serve the built
React SPA from this same Django process — every non-API path returns the
SPA's index.html so React Router can take over.
"""

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import TemplateView
from django.views.static import serve as static_serve


def _healthcheck(_request):
    return HttpResponse("ok")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", _healthcheck),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/", include("kyc.urls")),
]

# Serve uploaded files. WhiteNoise handles static; media goes through Django.
# We register the route unconditionally because django.conf.urls.static.static()
# is a no-op when DEBUG=False — that would 404 every uploaded document in prod.
# Single-process deployment, so this is fine.
urlpatterns += [
    re_path(
        rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
        static_serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]

# SPA catch-all: anything that didn't match an API route serves index.html.
# Excludes paths that start with /api/, /admin/, /static/, /media/.
urlpatterns += [
    re_path(
        r"^(?!api/|admin/|static/|media/|healthz).*$",
        TemplateView.as_view(template_name="index.html"),
        name="spa",
    ),
]
