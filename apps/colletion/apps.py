from django.apps import AppConfig


class ColletionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.colletion'

    def ready(self):
        import apps.colletion.signals  
