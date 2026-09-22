from django.apps import AppConfig


class TutelleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tutelle"
    verbose_name = "Échanges avec la tutelle (Ministère des Transports)"

    def ready(self):
        from tutelle import signals  # noqa: F401 — connecte le signal (incident grave -> flux tutelle)
