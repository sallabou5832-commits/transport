from audit import contexte 


class ContexteAuditMiddleware:
    """Pose l'adresse du client et, pour l'administration (session), l'utilisateur connecté.

    Pour l'API, l'acteur est posé une fois la requête authentifiée (voir `CompanyScopedQuerysetMixin.initial`).
    Le contexte est remis à zéro à chaque requête : rien ne fuit d'un utilisateur au suivant.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, requete):
        contexte.reinitialiser()
        contexte.definir(adresse_ip=contexte.adresse_ip_de(requete))
        utilisateur = getattr(requete, "user", None)
        if utilisateur is not None and utilisateur.is_authenticated:
            contexte.definir(acteur=utilisateur)
        try:
            return self.get_response(requete)
        finally:
            contexte.reinitialiser()
