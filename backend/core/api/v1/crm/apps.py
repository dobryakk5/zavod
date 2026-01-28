from django.apps import AppConfig


class CrmApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core.api.v1.crm'
    verbose_name = 'CRM API v1'
    
    def ready(self):
        # Импортируем сигналы, если они есть
        import core.api.v1.crm.signals