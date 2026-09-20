from django.contrib import admin

from formation.models import EtapeFormation, ParcoursFormation, ProgressionFormation


class EtapeFormationInline(admin.StackedInline):
    model = EtapeFormation
    extra = 0


@admin.register(ParcoursFormation)
class ParcoursFormationAdmin(admin.ModelAdmin):
    list_display = ["titre", "role"]
    inlines = [EtapeFormationInline]


@admin.register(ProgressionFormation)
class ProgressionFormationAdmin(admin.ModelAdmin):
    list_display = ["user", "parcours", "etape_courante", "termine", "date_debut", "date_fin"]
    list_filter = ["termine", "parcours"]
    search_fields = ["user__username"]
