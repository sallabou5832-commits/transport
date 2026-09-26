from django.contrib import admin

from configuration.models import ConfigurationAgent, ConfigurationCompagnie, ConfigurationPoste


@admin.register(ConfigurationCompagnie)
class ConfigurationCompagnieAdmin(admin.ModelAdmin):
    list_display = ["company", "automatisation_max", "gamification_max", "modifie_le"]


@admin.register(ConfigurationPoste)
class ConfigurationPosteAdmin(admin.ModelAdmin):
    list_display = ["company", "role", "niveau_automatisation", "niveau_gamification", "modifie_le"]
    list_filter = ["company", "role"]


@admin.register(ConfigurationAgent)
class ConfigurationAgentAdmin(admin.ModelAdmin):
    list_display = ["agent", "company", "niveau_automatisation", "niveau_gamification", "aisance_numerique"]
    list_filter = ["company"]
