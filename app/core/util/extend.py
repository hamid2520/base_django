import re

from django.utils.translation import ugettext_lazy as _
from rest_framework.fields import DateTimeField, DateField, CharField

from rest_framework import serializers, viewsets, pagination
from rest_framework.settings import api_settings

from .date import greDatetime, datetime as jldatetime, date as jldate
from . import lang
from .helper import is_valid_iran_national_id


class StandardResultsSetPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class UnlimitedResultsSetPagination(pagination.PageNumberPagination):
    page_size = None
    # page_size_query_param = 'page_size'
    # max_page_size = 100


class BigResultsSetPagination(pagination.PageNumberPagination):
    page_size = 20000
    # page_size_query_param = 'page_size'
    # max_page_size = 100


class MediumResultsSetPagination(pagination.PageNumberPagination):
    page_size = 400


class ListViewSet(viewsets.mixins.ListModelMixin,
                  viewsets.GenericViewSet):
    pass


class RetrieveListViewSet(viewsets.mixins.RetrieveModelMixin,
                          viewsets.mixins.ListModelMixin,
                          viewsets.GenericViewSet):
    pass


class RetrieveUpdateViewSet(viewsets.mixins.RetrieveModelMixin,
                            viewsets.mixins.UpdateModelMixin,
                            viewsets.GenericViewSet):
    pass


class RetrieveListUpdateViewSet(viewsets.mixins.RetrieveModelMixin,
                                viewsets.mixins.UpdateModelMixin,
                                viewsets.mixins.ListModelMixin,
                                viewsets.GenericViewSet):
    pass


class RetrieveListUpdateDeleteViewSet(viewsets.mixins.RetrieveModelMixin,
                                      viewsets.mixins.UpdateModelMixin,
                                      viewsets.mixins.ListModelMixin,
                                      viewsets.mixins.DestroyModelMixin,
                                      viewsets.GenericViewSet):
    pass

class RetrieveListDeleteViewSet(viewsets.mixins.DestroyModelMixin,
                                viewsets.GenericViewSet):
    pass

class RetrieveUpdateDeleteViewSet(viewsets.mixins.RetrieveModelMixin,
                                  viewsets.mixins.UpdateModelMixin,
                                  viewsets.mixins.DestroyModelMixin,
                                  viewsets.GenericViewSet):
    pass


class CreateRetrieveUpdateDeleteViewSet(
    viewsets.mixins.CreateModelMixin,
    viewsets.mixins.RetrieveModelMixin,
    viewsets.mixins.UpdateModelMixin,
    viewsets.mixins.DestroyModelMixin,
    viewsets.GenericViewSet):
    pass


class CreateRetrieveListUpdateViewSet(viewsets.mixins.RetrieveModelMixin,
                                      viewsets.mixins.UpdateModelMixin,
                                      viewsets.mixins.CreateModelMixin,
                                      viewsets.mixins.ListModelMixin,
                                      viewsets.GenericViewSet):
    pass


class CreateRetrieveListUpdateDeleteViewSet(viewsets.mixins.RetrieveModelMixin,
                                            viewsets.mixins.UpdateModelMixin,
                                            viewsets.mixins.CreateModelMixin,
                                            viewsets.mixins.ListModelMixin,
                                            viewsets.mixins.DestroyModelMixin,
                                            viewsets.GenericViewSet):
    pass


class CreateRetrieveListViewSet(
    viewsets.mixins.CreateModelMixin,
    viewsets.mixins.RetrieveModelMixin,
    viewsets.mixins.ListModelMixin,
    viewsets.GenericViewSet):
    pass


class ModelViewSetNoDelete(viewsets.mixins.CreateModelMixin,
                           viewsets.mixins.RetrieveModelMixin,
                           viewsets.mixins.UpdateModelMixin,
                           viewsets.mixins.ListModelMixin,
                           viewsets.GenericViewSet):
    pass


def raise_not_field_error(msg):
    raise serializers.ValidationError({api_settings.NON_FIELD_ERRORS_KEY: [_(msg)]})


def to_bool(s):
    if type(s) is bool:
        return s
    if type(s) is not str:
        return bool(s)
    if s.lower() in ('true', '1'):
        return True
    elif s.lower() in ('false', '0'):
        return False
    else:
        raise ValueError(
            '%s can not be converted to bool.' % s)  # evil ValueError that doesn't tell you what the wrong value was


class JalaliDateField(DateField):
    def to_internal_value(self, value):
        if not value:
            return None

        if value:
            value = lang.to_english(value)
            value = greDatetime(value, time=False)
        # convert jalali to gregorian
        return super(JalaliDateField, self).to_internal_value(value)

    def to_representation(self, value):
        formatted = super(JalaliDateField, self).to_representation(value)
        return jldate(formatted)


class JalaliDateTimeField(DateTimeField):
    def to_internal_value(self, value):
        if not value:
            return None

        if value:
            value = lang.to_english(value)
            value = greDatetime(value)
        # print(value)
        # convert jalali to gregorian
        return super(JalaliDateTimeField, self).to_internal_value(value)

    def to_representation(self, value):
        request = self.context['request'] if 'request' in self.context else None
        formatted = super(JalaliDateTimeField, self).to_representation(value)
        if request and to_bool(request.query_params.get('__gregorian', False)):
            return formatted
        if request and request.query_params.get('__microsecond'):
            return jldatetime(formatted, True)
        else:
            return jldatetime(formatted)


class JalaliDateFieldV2(DateField):
    def to_internal_value(self, value):
        if value:
            value = lang.to_english(value)
            value = greDatetime(value, time=False)
        # convert jalali to gregorian
        return super(JalaliDateFieldV2, self).to_internal_value(value)

    def to_representation(self, value):
        formatted = super(JalaliDateFieldV2, self).to_representation(value)
        return jldate(formatted)


class CellphoneField(CharField):

    def __init__(self, **kwargs):
        kwargs.update({'min_length': 11, 'max_length': 11})
        super().__init__(**kwargs)

    def to_internal_value(self, value):
        value = super(CellphoneField, self).to_internal_value(value)
        value = lang.to_english(value)
        if re.match('^09\d{9}?$', value) is None:
            raise serializers.ValidationError("شماره موبایل نامعتبر است. مانند این وارد کنید : 09102260226")
        return value


class PhoneField(CharField):
    def __init__(self, **kwargs):
        kwargs.update({'min_length': 7})
        super().__init__(**kwargs)

    def to_internal_value(self, value):
        value = super(PhoneField, self).to_internal_value(value)
        value = lang.to_english(value)

        if re.match('(0\d{10}(p\d{1,4})?|[^0]\d{7})(p\d{1,4})?$', value) is None:
            raise serializers.ValidationError(
                "شماره تماس نامعتبر است . مانند این وارد کنید : 09102260226 یا 02188302728")
        return value


class NationalIdField(CharField):

    def __init__(self, **kwargs):
        kwargs.update({'min_length': 10, 'max_length': 10})
        super().__init__(**kwargs)

    def to_internal_value(self, value):
        value = super(NationalIdField, self).to_internal_value(value)
        value = lang.to_english(value)
        if is_valid_iran_national_id(value):
            raise serializers.ValidationError("کد ملی نامعتبر است.")
        return value


class LandLineField(CharField):
    def to_internal_value(self, value):
        value = super(LandLineField, self).to_internal_value(value)
        value = lang.to_english(value)

        # if value[0:2] != '09' or len(value) != 11:
        if re.match('^[^0]\d{7}$', value) is None:
            raise serializers.ValidationError(_("Landline number not valid! e.g. 88302728"))
        return value


class PersianCharField(CharField):
    def to_internal_value(self, value):
        value = super(PersianCharField, self).to_internal_value(value)
        try:
            value = lang.fix_chars(value)
        except:
            pass
        return value


def map_iran_fields(serializers, models):
    # dont import these lines! just know type of serializers and models
    # call this method in each models.py
    # from rest_framework import serializers
    # from django.db import models
    serializers.ModelSerializer.serializer_field_mapping[models.DateTimeField] = JalaliDateTimeField
    serializers.ModelSerializer.serializer_field_mapping[models.DateField] = JalaliDateField
    # serializers.ModelSerializer.serializer_field_mapping[models.DecimalField] = LocalDecimalField
    serializers.ModelSerializer.serializer_field_mapping[models.CharField] = PersianCharField
