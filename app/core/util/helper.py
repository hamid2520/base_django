import re
import logging

from django.db.models import Q

from rest_framework.fields import CharField
from rest_framework.serializers import ValidationError

from . import lang

logger = logging.getLogger('script')


class CellphoneField(CharField):
    def to_internal_value(self, value):
        value = super(CellphoneField, self).to_internal_value(value)
        value = lang.to_english(value)
        if re.match('^09\d{9}?$', value) is None:
            raise ValidationError("شماره موبایل نامعتبر است. مانند این وارد کنید : 09102260226")
        return value


class NationalIdField(CharField):
    def to_internal_value(self, value):
        value = super(NationalIdField, self).to_internal_value(value)
        value = lang.to_english(value)
        if not is_valid_iran_national_id(value):
            raise ValidationError("کد ملی نامعتبر است.")
        return value


def is_valid_iran_national_id(input):
    if not re.search(r'^\d{10}$', input):
        return False

    check = int(input[9])
    s = sum([int(input[x]) * (10 - x) for x in range(9)]) % 11
    return (s < 2 and check == s) or (s >= 2 and check + s == 11)


def play_filtering_form(queryset, query_params):
    kwargs_and = {}
    kwargs_exclude = {}
    for param in query_params:
        value = query_params.get(param)

        if not value:
            continue
        if value == 'None':
            value = None
        _param = re.sub('\[\d+\]', '', param)

        if param[:7] == 'filter_':

            if value in ('0', '1'):
                value = int(value)
            # print(param, value, "\n")
            pattern = ''
            if ('pattern_' + param) in query_params:
                pattern = query_params.get('pattern_' + param)
            key = _param[7:] + pattern
            try:
                value = lang.fix_chars(value)
            except:
                pass
            if param.endswith('__in'):
                value = value.split(',')
            kwargs_and[key] = value
        elif param[:9] == 'orfilter_':
            pattern = ''
            if ('pattern_' + param) in query_params:
                pattern = query_params.get('pattern_' + param)
            key_string = param[9:]
            keys = key_string.split('OR')
            value_split = value.split('OR')
            QBuff = None
            counter = -1
            for key in keys:
                counter += 1
                if len(value_split) > 1:
                    value = value_split[counter]
                    if not value:
                        continue
                if not QBuff:
                    QBuff = Q(**{str(key + pattern): value})
                else:
                    QBuff |= Q(**{str(key + pattern): value})
            if QBuff:
                queryset = queryset.filter(QBuff)
        elif param[:8] == 'order_by':
            # queryset = queryset.order_by()
            args = value.split(',')
            queryset = queryset.order_by(*args)
        elif param[:8] == 'distinct':
            # queryset = queryset.order_by()
            args = value.split(',')
            queryset = queryset.distinct(*args)
        elif param[:8] == 'exclude_':
            if value in ('0', '1'):
                value = int(value)
            pattern = ''
            if ('pattern_' + param) in query_params:
                pattern = query_params.get('pattern_' + param)
            key = _param[8:] + pattern
            try:
                value = lang.fix_chars(value)
            except:
                pass
            if param.endswith('__in'):
                value = value.split(',')
            kwargs_exclude[key] = value
    logger.debug('kwargs_and to filter: %s. kwargs_exclude to filter: %s%s' % (kwargs_and, kwargs_exclude, "\n"))
    if kwargs_and:
        queryset = queryset.filter(**kwargs_and)
    if kwargs_exclude:
        queryset = queryset.exclude(**kwargs_exclude)
    return queryset


def get_ip(request):
    """Returns the IP of the request, accounting for the possibility of being
    behind a proxy.
    """
    ip = request.META.get("HTTP_X_FORWARDED_FOR", None)
    if ip:
        # X_FORWARDED_FOR returns client1, proxy1, proxy2,...
        ip = ip.split(", ")[0]
    else:
        ip = request.META.get("REMOTE_ADDR", "")
    return ip
