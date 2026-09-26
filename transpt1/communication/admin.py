from django.contrib import admin

from communication.models import DocumentArchive, EvenementAgenda, MessageDirect, NoteService


class _LectureSeule(admin.ModelAdmin):
    """Lecture seule : ces objets se créent par l'API (avec leurs alertes et leur trace), jamais à la main."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NoteService)
class NoteServiceAdmin(_LectureSeule):
    list_display = ["id", "titre", "auteur", "company", "cree_le"]


@admin.register(MessageDirect)
class MessageDirectAdmin(_LectureSeule):
    list_display = ["id", "gare", "portee", "auteur", "cree_le"]


@admin.register(EvenementAgenda)
class EvenementAgendaAdmin(_LectureSeule):
    list_display = ["id", "titre", "debut", "company"]


@admin.register(DocumentArchive)
class DocumentArchiveAdmin(_LectureSeule):
    list_display = ["id", "titre", "categorie", "reference", "archive", "company"]
