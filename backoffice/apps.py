from django.apps import AppConfig
from django.contrib import admin


class BackofficeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backoffice'

    def ready(self):
        import backoffice.signals
        admin.site.site_header = "RideHub"
        admin.site.site_title = "RideHub"
        admin.site.index_title = "Site Administration"
