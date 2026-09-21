from audit import contexte
from core.models import Role


class CompanyScopedQuerysetMixin:
    """Restricts a ViewSet's queryset to the requesting user's company.

    Superadmins (no company, platform operators) see everything.

    Une fois la requête authentifiée, l'utilisateur est aussi désigné comme acteur du journal d'audit :
    toute écriture faite par ce ViewSet lui sera attribuée (voir le paquet `audit`).
    """

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        contexte.definir(acteur=request.user)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == Role.SUPERADMIN:
            return queryset
        return queryset.filter(company_id=user.company_id)
