from audit import contexte
from core.models import Role


class ActeurAuditeMixin:
    """Une fois la requête authentifiée, l'utilisateur est désigné comme acteur du journal d'audit : toute écriture
    faite par cette vue lui sera attribuée (voir le paquet `audit`). À utiliser sur toute vue qui écrit des objets
    tracés sans passer par `CompanyScopedQuerysetMixin`."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        contexte.definir(acteur=request.user)


class CompanyScopedQuerysetMixin(ActeurAuditeMixin):
    """Restricts a ViewSet's queryset to the requesting user's company.

    Superadmins (no company, platform operators) see everything.

    Désigne aussi l'acteur du journal d'audit (voir `ActeurAuditeMixin`).
    """

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.role == Role.SUPERADMIN:
            return queryset
        return queryset.filter(company_id=user.company_id)
