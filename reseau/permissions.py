from rest_framework.permissions import SAFE_METHODS, BasePermission

from core.models import Role


class CanManageOwnGare(BasePermission):
    """A chef_gare may only modify (or delete) the Gare they lead.

    Read access and every other role are unaffected — this only tightens
    write access for the chef_gare role specifically.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        if user.role != Role.CHEF_GARE:
            return True
        return obj.chef_id == user.id
