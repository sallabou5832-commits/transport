"""Pagination facultative de l'API : sans `?limit=`, la liste est renvoyée entière, exactement comme avant ; avec `?limit=50`
(et `?offset=`), la réponse devient `{count, next, previous, results}`.

Pourquoi facultative : le site et le mobile lisent des listes brutes partout, y compris pour des calculs sur la liste
entière. Les paginer d'office les casserait tous d'un coup ; ainsi chaque écran s'y met quand il en a besoin, et un appelant
qui ne veut qu'une page peut la demander sans télécharger toute la table. `max_limit` borne ce qu'une seule demande peut
réclamer. Le journal d'audit garde sa propre pagination, obligatoire (`audit.views.PaginationJournal`)."""

from rest_framework.pagination import LimitOffsetPagination


class PaginationFacultative(LimitOffsetPagination):
    default_limit = None
    max_limit = 500
