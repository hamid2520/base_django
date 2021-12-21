from django.contrib import admin
from . import models
# Register your models here.


from django.apps import apps
from django.contrib.admin.sites import AlreadyRegistered

from nested_inline.admin import NestedStackedInline, NestedModelAdmin


class AnswerInline(admin.TabularInline):
    model = models.Answer

class QustionAdmin(admin.ModelAdmin):
    list_filter = ("sim", )
    inlines = [
        AnswerInline,
    ]


class ExerciseAdmin(admin.ModelAdmin):
    list_filter = ("sim", )


class ResultAdmin(admin.ModelAdmin):
    list_filter = ("exercise__sim", )


class ParameterAdmin(admin.ModelAdmin):
    list_filter = ("exercise__sim", )


class OptionAdmin(admin.ModelAdmin):
    list_filter = ("parameter__exercise__sim", )


class ExerciseDataAdmin(admin.ModelAdmin):
    list_filter = ("result__exercise__sim", )


class SimReportAdmin(admin.ModelAdmin):
    list_display = ("user", "sim")
    list_filter = ("sim", )


class ExerciseReportAdmin(admin.ModelAdmin):
    list_display = ("user", "exercise","is_submit")
    list_filter = ("exercise__sim", )


class QuizReportAdmin(admin.ModelAdmin):
    list_display = ("user", "sim","is_submit")
    list_filter = ("sim", )


class QuizReportDetailAdmin(admin.ModelAdmin):
    list_filter = ("quiz_report__sim", "is_true")


class SimAccessListAdmin(admin.ModelAdmin):
    list_filter = ("token_sim", "user")
# class ExerciseAdmin(admin.ModelAdmin):
#     list_filter = ("sim", )

# class ExerciseAdmin(admin.ModelAdmin):
#     list_filter = ("sim", )

# class ResultInline(NestedStackedInline):
#     model = models.Result

# class OptionInline(NestedStackedInline):
#     model = models.Option

# class ExerciseDataInline(NestedStackedInline):
#     model = models.ExerciseData

try: 
    admin.site.register(models.Question, QustionAdmin)
    admin.site.register(models.Exercise, ExerciseAdmin)
    admin.site.register(models.Result, ResultAdmin)
    admin.site.register(models.Parameter, ParameterAdmin)
    admin.site.register(models.Option, OptionAdmin)
    admin.site.register(models.ExerciseData, ExerciseDataAdmin)
    admin.site.register(models.SimReport, SimReportAdmin)
    admin.site.register(models.ExerciseReport, ExerciseReportAdmin)
    admin.site.register(models.QuizReport, QuizReportAdmin)
    admin.site.register(models.QuizReportDetail, QuizReportDetailAdmin)
    admin.site.register(models.SimAccessList, SimAccessListAdmin)

    # admin.site.register(models.Exercise, ExerciseAdmin)
except AlreadyRegistered:
    pass

app_models = apps.get_app_config('core').get_models()
for model in app_models:
    try:
        if model not in [models.Question, models.Answer, models.Exercise, models.Result, models.Parameter,\
            models.Option, models.ExerciseData, models.SimReport, models.ExerciseReport, models.QuizReport,
                         models.QuizReportDetail, models.SimAccessList]:

            admin.site.register(model)
    except AlreadyRegistered:
        pass
