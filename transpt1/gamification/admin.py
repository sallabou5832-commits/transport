from django.contrib import admin

from gamification.models import BadgeObtenu, MissionAccomplie


@admin.register(MissionAccomplie)
class MissionAccomplieAdmin(admin.ModelAdmin):
    list_display = ["agent", "code", "date", "accomplie_le"]
    list_filter = ["code", "date"]


@admin.register(BadgeObtenu)
class BadgeObtenuAdmin(admin.ModelAdmin):
    list_display = ["agent", "code", "periode", "obtenu_le"]
    list_filter = ["code"]
