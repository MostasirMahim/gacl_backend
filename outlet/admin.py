from django.contrib import admin
from django.apps import apps

app_name = "outlet"
for model in apps.get_app_config(app_name).get_models():
    class DynamicAdmin(admin.ModelAdmin):
        list_display = [f.name for f in model._meta.fields]
    try:
        admin.site.register(model, DynamicAdmin)
    except admin.sites.AlreadyRegistered:
        pass
