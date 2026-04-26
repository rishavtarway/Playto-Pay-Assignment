"""DRF permissions for the merchant / reviewer split."""

from rest_framework.permissions import BasePermission


# Only authenticated users with role=merchant.
class IsMerchant(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_merchant())


# Only authenticated users with role=reviewer.
class IsReviewer(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_reviewer())


# Object-level: a merchant can only touch a submission they own.
# We mostly rely on queryset scoping (see views), but this is a backstop.
class IsMerchantOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.merchant_id == request.user.id
