from django.contrib import admin
from . import models
# Register your models here.


from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered

from nested_inline.admin import NestedStackedInline, NestedModelAdmin


app_models = apps.get_app_config('core').get_models()
for model in app_models:
    try:
        if model not in []:
            admin.site.register(model)
    except AlreadyRegistered:
        pass
