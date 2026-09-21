from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm

from core.models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "headquarters_city", "created_at"]
    search_fields = ["name", "headquarters_city"]


class CoreUserCreationForm(AdminUserCreationForm):
    """Création d'un utilisateur par l'administration : le rôle est un choix explicite.

    Le rôle par défaut du modèle est « superadmin » (pour que `createsuperuser` fonctionne sans
    question). Sans ce formulaire, un compte créé à la hâte dans l'administration deviendrait donc un
    superadmin, avec accès à toutes les compagnies. Ici le rôle est vide et obligatoire ; la cohérence
    rôle / compagnie est ensuite vérifiée par `User.clean()`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        role = self.fields["role"]
        role.choices = [("", "— Choisir un rôle —")] + [choix for choix in role.choices if choix[0]]
        role.initial = ""
        role.required = True


@admin.register(User)
class CoreUserAdmin(UserAdmin):
    list_display = ["username", "email", "role", "company", "is_staff"]
    list_filter = ["role", "company", "is_staff", "is_superuser"]
    add_form = CoreUserCreationForm
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "usable_password", "password1", "password2")}),
        ("Transport Coord", {"classes": ("wide",), "fields": ("role", "company")}),
    )
    fieldsets = UserAdmin.fieldsets + (
        ("Transport Coord", {"fields": ("role", "company")}),
    )
