from django.contrib import admin

from .models import Document, Notification, Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "state", "submitted_at", "assigned_reviewer")
    list_filter = ("state",)
    search_fields = ("merchant__email", "business_name", "full_name")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("kind", "submission", "size_bytes", "uploaded_at")
    list_filter = ("kind",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("event_type", "merchant", "submission", "created_at")
    list_filter = ("event_type",)
