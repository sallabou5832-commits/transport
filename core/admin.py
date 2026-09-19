from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from core.models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "headquarters_city", "created_at"]
    search_fields = ["name", "headquarters_city"]


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "company", "is_staff"]
    list_filter = ["role", "company", "is_staff", "is_superuser"]
    fieldsets = UserAdmin.fieldsets + (
        ("Transport Coord", {"fields": ("role", "company")}),
    )
