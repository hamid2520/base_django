import logging
import requests
import json
# import mandrill
from zeep import Client
from django.template.loader import render_to_string
from django.core.mail import send_mail
from core.models import Campaign
from django.conf import settings
from kavenegar import *

parsa_client = None


def get_parsa_client():
    global parsa_client
    if not parsa_client:
        try:
            parsa_client = Client("http://parsasms.com/webservice/v2.asmx?WSDL")
        except:
            pass
    return parsa_client


# app_name = 'pakand'
logger = logging.getLogger()

sms = {
    "from": "30007227001821",
    "username": "emami",
    "password": "emami",
    "url": "http://tsms.ir/url/tsmshttp.php?from=%(from)s&"
           "to=%(to)s&username=%(username)s&"
           "password=%(password)s&message=%(message)s"
}

ERROR_REASONS_PARSA = {
    '1': 'نام کاربری یا رمز عبور معتبر نمی‌باشد.',
    '2': 'آرایه‌ها خالی می‌باشد.',
    '3': 'طول آرایه بیشتر از ۱۰۰ می‌باشد.',
    '4': 'طول آرایه‌ی فرستنده و گیرنده و متن پیام با یکدیگر تطابق ندارد.',
    '5': 'امکان گرفتن پیام جدید وجود ندارد.',
    '6': 'حساب کاربری غیر فعال می‌باشد. '
         + 'نام کاربری و یا رمز عبور خو را به درستی وارد نمی‌کنید.'
         + 'در صورتی که به تازگی وب سرویس را فعال کرده‌اید از منوی تنظیمات رمز عبور رمز عبور وب سرویس خود را مجدد ست کنید.',
    '7': 'امکان دسترسی به خط مورد نظر وجود ندارد.',
    '8': 'شماره گیرنده نامعتبر است.',
    '9': 'حساب اعتبار ریالی مورد نیاز را دارا نمی‌باشد.',
    '10': 'خطایی در سیستم رخ داده است. دوباره سعی کنید.',
    '11': 'ip نامعتبر است',
    '20': 'شماره مخاطب فیلتر شده می‌باشد.',
    '21': 'ارتباط با سرویس‌دهنده قطع می‌باشد.',
}

ERROR_REASONS_KAVENEGAR = {
    # '200': 'درخواست تایید شد',
    '400': 'پارامترها ناقص هستند',
    '401': 'حساب کاربری غیرفعال شده است',
    '402': 'عملیات ناموفق بود',
    '403': 'کد شناسائی API-Key معتبر نمی‌باشد',
    '404': 'متد نامشخص است',
    '405': 'متد Get/Post اشتباه است',
    '406': 'پارامترهای اجباری خالی ارسال شده اند',
    '407': 'دسترسی به اطلاعات مورد نظر برای شما امکان پذیر نیست',
    '409': 'سرور قادر به پاسخگوئی نیست بعدا تلاش کنید',
    '411': 'دریافت کننده نامعتبر است',
    '412': 'ارسال کننده نامعتبر است',
    '413': 'پیام خالی است و یا طول پیام بیش از حد مجاز می‌باشد. لاتین  ﻛﺎراﻛﺘﺮ و ﻓﺎرﺳﻲ 268 ﻛﺎراﻛﺘﺮ',
    '414': 'حجم درخواست بیشتر از حد مجاز است ،ارسال پیامک :هر فراخوانی حداکثر 200 رکوردو کنترل وضعیت :هر فراخوانی 500 رکورد',
    '415': 'اندیس شروع بزرگ تر از کل تعداد شماره های مورد نظر است',
    '416': 'IP سرویس مبدا با تنظیمات مطابقت ندارد',
    '417': 'تاریخ ارسال اشتباه است و فرمت آن صحیح نمی باشد.',
    '418': 'اعتبار شما کافی نمی‌باشد',
    '419': 'طول آرایه متن و گیرنده و فرستنده هم اندازه نیست',
    '420': 'استفاده از لینک در متن پیام برای شما محدود شده است',
    '422': 'داده ها به دلیل وجود کاراکتر نامناسب قابل پردازش نیست',
    '424': 'الگوی مورد نظر پیدا نشد',
    '426': 'استفاده از این متد نیازمند سرویس پیشرفته می‌باشد',
    '427': 'استفاده از این خط نیازمند ایجاد سطح دسترسی می باشد',
    '428': 'ارسال کد از طریق تماس تلفنی امکان پذیر نیست',
    '429': 'IP محدود شده است',
    '431': 'ساختار کد صحیح نمی‌باشد',
    '432': 'پارامتر کد در متن پیام پیدا نشد',
    '451': 'فراخوانی بیش از حد در بازه زمانی مشخص IP محدود شده',
    '501': 'فقط امکان ارسال پیام تست به شماره صاحب حساب کاربری وجود دارد',
}


def send_sms(to, message, gateway=Campaign.GTW_PARSA_SMS, logger=logger):
    result = dict(
        status=False,
        body=None
    )

    try:
        if gateway == Campaign.GTW_KAVENEGAR_SMS:
            params = {}
            if 'message' in message:
                body = message['message']
                params = {
                    'receptor': to,
                    'message': body,
                }
                if 'sender' in message and message['sender']:
                    params['sender'] = message['sender']
            elif 'context' in message:
                params = {
                    **message['context'],
                    'template': message['template'],
                    'receptor': to,
                }
            try:
                api = KavenegarAPI(settings.KAVENEGAR_SMS_APIKEY)
                if 'message' in message:
                    response = api.sms_send(params)
                else:
                    response = api.verify_lookup(params)
            except APIException as e:
                code = str(e).split('APIException[')[1].split(']')[0]
                result['status'] = False
                result['error'] = ERROR_REASONS_KAVENEGAR.get(code, 'خطای نامشخص')
            except HTTPException as e:
                result['status'] = False
                result['error'] = 'خطا در برقراری ارتباط با کاوه‌نگار'
            else:
                result['status'] = True
                result['error'] = ''
                result['body'] = response

        elif gateway == Campaign.GTW_PARSA_SMS:
            body = None
            if 'message' in message:
                body = message['message']
            elif 'tpl' in message:
                try:
                    body = render_to_string(message['tpl'], message['context'])
                except:
                    pass
            if not body:
                raise Exception('body is null for GTW_PARSA_SMS!')
            if get_parsa_client():
                r = get_parsa_client().service.SendSMS(
                    '****',
                    '*****',
                    {'string': ['30006708537537']},
                    {'string': [to]},
                    {'string': [body]}
                )

                result['status'] = r and hasattr(r, 'long') and r.long[0] > 1000
                result['body'] = r.long if r and hasattr(r, 'long') else None
                if not result['status']:
                    error_code = str(result.get('body')[0]) if result.get('body', []) else '-1'
                    result['error'] = ERROR_REASONS_PARSA.get(error_code, '')

            else:
                result['status'] = False
                result['body'] = None
                result['error'] = 'parsa sms connection failed!'
        elif gateway == Campaign.GTW_PARSA_TEMPLATE_SMS:
            if 'tpl' in message:
                tpl = message['tpl']
                payload = {'receptor': to, 'template': tpl}
                payload.update(message.get('context', {}))
                if 'type' not in payload:
                    payload['type'] = 1
                headers = {'apikey': settings.PARSA_TEMPLATE_SMS_APIKEY,
                           'content-type': "application/x-www-form-urlencoded"
                           }
                r = requests.post("http://api.smsapp.ir/v2/send/verify", data=payload, headers=headers)

                resp = json.loads(r.text)
                result['body'] = resp
                if 'result' not in resp:
                    raise Exception('result is not in parsa sms response!')
                result['status'] = resp['result'] == 'success'
            else:
                raise Exception('tpl does not exist!')
        else:
            raise Exception('gateway is wrong')
            sms_data = sms.copy()
            url_template = sms_data['url']
            del sms_data['url']
            sms_data['message'] = message
            sms_data['to'] = to
            url = url_template % sms_data

            # call api
            logger.debug('calling url %s' % url)
            r = requests.get(url)
            result['status'] = (r.status_code == 200)
            # @todo result body should be returned and saved
            result['body'] = None
    except BaseException as e:
        result['status'] = False
        result['error'] = str(e)

    return result
