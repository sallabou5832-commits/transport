from core.models import Role


class CompanyScopedQuerysetMixin:
    """Restricts a ViewSet's queryset to the requesting user's company.

    Superadmins (no company, platform operators) see everything.
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == Role.SUPERADMIN:
            return queryset
        return queryset.filter(company_id=user.company_id)
