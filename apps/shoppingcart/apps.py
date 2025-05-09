from django.apps import AppConfig


class ShoppingcartConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.shoppingcart'

    def ready(self):
        import apps.shoppingcart.signals # Esto importa el archivo de señales para que se registren