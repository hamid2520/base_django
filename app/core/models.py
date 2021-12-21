from django.db import models
from django.contrib.auth.models import User, AbstractBaseUser, BaseUserManager, \
    PermissionsMixin, AnonymousUser
from django.db.models import JSONField
from django.utils import timezone
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from core.util.helper import get_ip
from core.util.requestMiddleware import RequestMiddleware
from django.apps import apps
from . import model_choices
import uuid
import os
import datetime
from rest_framework.serializers import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver
import binascii


class TrackModel(models.Model):
    created_by = models.ForeignKey(User, blank=True, null=True, related_name="%(app_label)s_%(class)s_created_by",
                                   editable=False, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    created_ip = models.GenericIPAddressField(verbose_name='آی‌پی سازنده', default='', blank=True, null=True,
                                              editable=False)

    class Meta:
        abstract = True

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        request = RequestMiddleware.get_request_data()[1]
        if request and self.pk is None:
            self.created_ip = get_ip(request)
            if request.user and request.user != AnonymousUser():
                self.created_by = request.user
        return super(TrackModel, self).save(force_insert=force_insert, force_update=force_update, using=using,
                                            update_fields=update_fields)


class ChangeLog(models.Model):
    class Meta:
        verbose_name = "فهرست تغییرات"
        verbose_name_plural = "فهرست تغییرات"

    ACTION_ADD = 0
    ACTION_EDIT = 1
    ACTION_DELETE = 2
    ACTION_CHOICES = (
        (ACTION_ADD, 'add'),
        (ACTION_EDIT, 'edit'),
        (ACTION_DELETE, 'delete')
    )

    PRIORITY_LOW = 1
    PRIORITY_MEDIUM = 2
    PRIORITY_HIGH = 3
    PRIORITY_EMERGENCY = 4
    PRIORITY_CHOICES = (
        (PRIORITY_LOW, 'کم'),
        (PRIORITY_MEDIUM, 'متوسط'),
        (PRIORITY_HIGH, 'بالا'),
        (PRIORITY_EMERGENCY, 'خیلی بالا'),
    )

    created_at = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    ip = models.GenericIPAddressField(default='', blank=True, null=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, editable=False)
    # is_staff = models.BooleanField(default=True)
    # user_username = models.CharField(max_length=100, default='')
    # user_fullname = models.CharField(max_length=150, default='')
    changed_fields = JSONField(default=dict, verbose_name='تغییرات')
    content_type = models.ForeignKey(
        ContentType,
        models.SET_NULL,
        verbose_name='نوع محتوا',
        blank=True, null=True,
    )
    object_id = models.BigIntegerField(blank=True, null=True, db_index=True)
    action = models.SmallIntegerField(default=ACTION_EDIT, editable=False, choices=ACTION_CHOICES)
    priority = models.SmallIntegerField(default=PRIORITY_LOW)

    def __str__(self):
        return '{} {} at: {}'.format(dict(self.ACTION_CHOICES)[self.action], self.content_type.model, self.created_at)

    @staticmethod
    def diff_models(old, new):
        if not new:
            return {}
        changes = {}
        fields = list(new._meta.fields)
        empty = ['', 'None', '{}', 'False', '0.0']
        for f in fields:
            name = f.name
            if name in ['history', 'updated_at', 'updated_by', 'updated_ip', 'created_at', 'created_by', 'created_ip']:
                continue
            oldone = ''
            _old = None
            _new = getattr(new, name, None)
            newone = str(_new)
            if old:
                _old = getattr(old, name, None)
                oldone = str(_old)

            if oldone in empty and newone in empty:
                continue

            if _new != _old:
                changes[name] = [oldone, newone]
        return changes

    @staticmethod
    def add_log(old, new, priority=PRIORITY_LOW):
        cl = ChangeLog()
        cl.priority = priority
        request = RequestMiddleware.get_request_data()[1]
        if request:
            cl.ip = get_ip(request)
            if request.user and request.user != AnonymousUser():
                cl.user = request.user
        if (not old or not old.pk) and new:
            cl.action = ChangeLog.ACTION_ADD
            model = new
        elif new and old:
            cl.action = ChangeLog.ACTION_EDIT
            model = new
        elif old and old.pk and not new:
            cl.action = ChangeLog.ACTION_DELETE
            model = old
        else:
            return None
        cl.object_id = model.id
        cl.content_type = ContentType.objects.get_for_model(model)
        model_diff = ChangeLog.diff_models(old, new)
        if model_diff:
            cl.changed_fields = model_diff
            cl.save()
            return cl
        elif cl.action == ChangeLog.ACTION_DELETE:
            cl.changed_fields = model_diff
            cl.save()
            return cl
        else:
            return None

    @staticmethod
    def get_by_model_and_object_id(model, object_id):
        return ChangeLog.objects.filter(content_type=ContentType.objects.get_for_model(model), object_id=object_id)

    @staticmethod
    def get_by_model(model):
        return ChangeLog.get_by_model_and_object_id(model, model.id)

    @staticmethod
    def get_content_type_by_model(model):
        return ContentType.objects.get_for_model(model)

    @staticmethod
    def get_model_choices_by_content_type_id(ct_id):
        model = ContentType.objects.get_for_id(ct_id).model_class()
        return ChangeLog.get_model_choices_by_model(model)

    @staticmethod
    def get_model_choices_by_model(model):
        buff = {}
        for field in model._meta.fields:
            if field.name not in buff:
                buff[field.name] = {}
            if hasattr(field, 'choices') and field.choices:
                for choice in field.choices:
                    buff[field.name][str(choice[0])] = choice[1]
        return buff

    @staticmethod
    def get_all_content_types():
        return [dict(content_type_id=ct.id, content_type_model=ct.model) for ct in ContentType.objects.all()]


class ChangeLogWithTrackModel(models.Model):
    created_by = models.ForeignKey(User, blank=True, null=True,
                                   related_name="%(app_label)s_%(class)s_created_by",
                                   editable=False, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, editable=False, db_index=True)
    created_ip = models.GenericIPAddressField(verbose_name='آی‌پی سازنده', default='', blank=True, null=True,
                                              editable=False)

    class Meta:
        abstract = True

    CHANGELOG_PRIORITY = ChangeLog.PRIORITY_MEDIUM

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        model = self.__class__
        old_model = model.objects.get(pk=self.pk) if self.pk is not None else None
        request = RequestMiddleware.get_request_data()[1]
        if request and self.pk is None:
            self.created_ip = get_ip(request)
            self.created_by = request.user
        instance = super(ChangeLogWithTrackModel, self).save(force_insert=force_insert, force_update=force_update,
                                                             using=using, update_fields=update_fields)
        priority = getattr(model, 'CHANGELOG_PRIORITY', None) or ChangeLogWithTrackModel.CHANGELOG_PRIORITY
        ChangeLog.add_log(old_model, self, priority)
        return instance

    def delete(self, using=None, keep_parents=False):
        model = self.__class__
        priority = getattr(model, 'CHANGELOG_PRIORITY', None) or ChangeLogWithTrackModel.CHANGELOG_PRIORITY
        ChangeLog.add_log(self, None, priority)
        return super(ChangeLogWithTrackModel, self).delete()


def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    ext = ext.lower()
    if ext in ['jpg', 'png', 'jpeg']:
        filename = "%s.%s" % (uuid.uuid4(), ext)
        now = datetime.datetime.now()
        now.year, now.month
        return "sim/{year}/{month}/{name}".format(year=now.year, month=now.month, name=filename)
    else:
        raise ValidationError("فقط فرمت های  jpeg, png , jpg قابل قبول هستند !")


class UserMeta(models.Model):
    """User Meta To add extra details to user"""

    class Meta:
        verbose_name = "ویژگی کاربر"
        verbose_name_plural = "ویژگی کاربران"

    GENDER_MALE = 0
    GENDER_FEMALE = 1
    GENDER_UNKNOWN = 2
    GENDER_CHOICES = (
        (GENDER_MALE, 'پسر'),
        (GENDER_FEMALE, 'دختر'),
        (GENDER_UNKNOWN, 'نامعلوم'),
    )

    TYPE_STUFF = 0
    TYPE_STUDENT = 1
    TYPE_TEACHER = 2
    TYPE_CHOICES = (
        (TYPE_STUFF, 'نامعلوم'),
        (TYPE_STUDENT, 'دانش آموز'),
        (TYPE_TEACHER, 'معلم'),
    )

    nid = models.CharField(max_length=20, null=True, unique=True)
    phone = models.CharField(max_length=11, null=True, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    img_addr = models.FileField(upload_to=get_file_path, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    gender = models.SmallIntegerField(choices=GENDER_CHOICES, default=GENDER_UNKNOWN, null=True)
    type = models.IntegerField(choices=TYPE_CHOICES, default=TYPE_STUFF, null=True)

    def __str__(self):
        return self.phone


class Campaign(models.Model):
    TYPE_SMS = 1
    TYPE_EMAIL = 2
    CHOICES_TYPE = (
        (TYPE_SMS, 'SMS'),
        (TYPE_EMAIL, 'Email')
    )

    STATUS_NEW = 0
    STATUS_INPROGRESS = 1
    STATUS_RETRY = 2
    STATUS_FAILED = 9
    STATUS_DONE = 10
    CHOICES_STATUS = (
        (STATUS_NEW, 'New'),
        (STATUS_INPROGRESS, 'Inprogress'),
        (STATUS_RETRY, 'Retry'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_DONE, 'Done')
    )

    GTW_UNKNOWN = 0
    GTW_DJANGO_SEND_MAIL = 1
    GTW_PARSA_SMS = 11
    GTW_PARSA_TEMPLATE_SMS = 12
    GTW_KAVENEGAR_SMS = 13
    CHOICES_GTW = (
        (GTW_UNKNOWN, 'unknown gateway'),
        (GTW_DJANGO_SEND_MAIL, 'django send mail'),
        (GTW_PARSA_SMS, 'parsa sms'),
        (GTW_PARSA_TEMPLATE_SMS, 'parsa template sms'),
        (GTW_KAVENEGAR_SMS, 'kavenegar sms'),
    )

    title = models.CharField(max_length=100, blank=True, default='')
    body = JSONField(default=dict)
    ctype = models.IntegerField(choices=CHOICES_TYPE, default=TYPE_SMS)
    status = models.IntegerField(choices=CHOICES_STATUS, default=STATUS_NEW)

    # email address, cellphone number or ...
    target = models.CharField(max_length=50)

    # if you are sending to certain user set below attribute
    # NOTE still you must set target based of the cellphone number of the user
    target_user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL)
    # request = models.ForeignKey('sales.Request', blank=True, null=True, on_delete=models.SET_NULL)

    # this can be a foreign key, but it's possible to have two different models for
    # emails and smses
    target_group = models.IntegerField(blank=True, null=True)

    start_at = models.DateTimeField(blank=True, null=True)
    stop_at = models.DateTimeField(blank=True, null=True)
    index = models.CharField(max_length=20, default='')
    data = JSONField(default=dict)
    # error = models.CharField(max_length=256, default='')

    # gateway to parse results correctly!
    gtw = models.IntegerField(choices=CHOICES_GTW, default=GTW_UNKNOWN)

    @staticmethod
    def send_sms(to='', group='', message=None, target_user=None, sender_number=None):
        if not to and not group:
            raise Exception("arguments are not valid.")
        if not message:
            raise Exception("arguments are not valid.")
        gtw = Campaign.GTW_KAVENEGAR_SMS
        campaign = Campaign()
        body = {"message": str(message)}
        if sender_number is None:
            body['sender'] = settings.KAVENEGAR_DEFAULT_SENDER_NUMBER
        else:
            body['sender'] = sender_number
        campaign.body = body
        campaign.target = to
        if target_user:
            campaign.target_user = target_user
        campaign.gtw = gtw
        campaign.save()
        return campaign

    @staticmethod
    def send_template_sms(to='', group='', target_user=None, tpl=None, context=None, gtw=GTW_KAVENEGAR_SMS):
        if not to and not group:
            raise Exception("arguments are not valid.")
        if not context or not tpl:
            raise Exception("arguments are not valid.")

        campaign = Campaign()
        if gtw == Campaign.GTW_KAVENEGAR_SMS:
            campaign.body = {
                'template': tpl,
                'context': context,
            }
        else:
            campaign.body = {
                'tpl': tpl,
                'context': context,
            }
        campaign.target = to
        if target_user:
            campaign.target_user = target_user
        campaign.gtw = gtw
        campaign.save()
        return campaign

    @staticmethod
    def send_email(to='', group='', message=None, target_user=None, tpl=None, context=None, title='', request=None,
                   gtw=GTW_DJANGO_SEND_MAIL):

        if (not message and not tpl) or (not to and not group):
            raise Exception("arguments are not valid.")

        campaign = Campaign()
        if message:
            campaign.body = {"message": str(message)}
        else:
            campaign.body = {
                'tpl': tpl,
                'context': context,
            }
            #     {
            # "email":"emamirazavi@yahoo.com",
            # "code":"kokab",
            # "tpl":"core/activation-email-test.html"}
        campaign.target = to
        campaign.ctype = Campaign.TYPE_EMAIL
        if target_user:
            campaign.target_user = target_user
        if request:
            campaign.request = request
        campaign.title = title
        campaign.gtw = gtw
        campaign.save()
        return campaign


class VerificationSms(models.Model):
    # class Meta:
    #     unique_together = ('user', 'usage')

    USAGE_REGISTERATION = 1
    USAGE_RESET_PASSWORD = 2
    USAGE_LOGIN = 3
    USAGE_CHOICES = (
        (USAGE_REGISTERATION, 'Register'),
        (USAGE_RESET_PASSWORD, 'Reset Password'),
        (USAGE_LOGIN, 'Login with sms'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, default=None,
                             verbose_name='کاربر')
    mobile = models.CharField(max_length=15, default='', blank=True, null=True, verbose_name='موبایل')
    code = models.CharField(max_length=10, verbose_name='کد')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    update_count = models.SmallIntegerField(default=0)
    lifetime = models.SmallIntegerField(default=settings.SMS_VERIFICATION['SMS_CODE_LIFETIME'])
    usage = models.SmallIntegerField(choices=USAGE_CHOICES, default=USAGE_REGISTERATION)

    @staticmethod
    def send_code(mobile=None, usage=None):
        if not mobile or not usage:
            raise Exception('bad arguments')
        res = {
            'status': False,
            'message': '',
            'new_code_request_seconds': settings.SMS_VERIFICATION['SMS_NEW_CODE_REQUEST_LIMIT'] * 60,
        }
        from random import randrange
        from math import ceil
        old_sms = None

        VerificationSms.objects.filter(
            mobile=mobile,
            usage=usage,
            created_at__lt=(timezone.now() - timezone.timedelta(hours=1))
        ).delete()

        old_sms = VerificationSms.objects.filter(mobile=mobile, usage=usage)

        if old_sms:
            old_sms = old_sms[0]
            if old_sms.update_count >= settings.SMS_VERIFICATION['MAX_SMS_COUNT_PER_HOUR']:
                timedelta = (old_sms.created_at + timezone.timedelta(hours=1)) - timezone.now()
                minutes = ceil(timedelta.seconds / 60)
                res['message'] = '{} دقیقه دیگر امتحان کنید.'.format(minutes)
                res['new_code_request_seconds'] = minutes * 60
                return res
            if old_sms.updated_at + timezone.timedelta(
                    minutes=settings.SMS_VERIFICATION['SMS_NEW_CODE_REQUEST_LIMIT']) > timezone.now():
                timedelta = (old_sms.updated_at + timezone.timedelta(
                    minutes=settings.SMS_VERIFICATION['SMS_NEW_CODE_REQUEST_LIMIT'])) - timezone.now()
                res['message'] = '{} ثانیه دیگر امتحان کنید.'.format(timedelta.seconds)
                res['new_code_request_seconds'] = timedelta.seconds
                return res

        code = str(randrange(12222, 99999))

        # message = 'Code: {}\nتوجه نمایید که این کد {} دقیقه اعتبار دارد.'.format(code, settings.SMS_VERIFICATION[
        #     'SMS_CODE_LIFETIME'])
        # Campaign.send_sms(gtw=Campaign.GTW_KAVENEGAR_SMS,
        #                   to=mobile,
        #                   target_user=None,
        #                   message=message)

        Campaign.send_template_sms(
            to=mobile,
            tpl='registerCode',
            context={
                'token': code,
                'token2': settings.SMS_VERIFICATION['SMS_CODE_LIFETIME']
            }
        )
        mobile_text = '*******' + mobile[-4:]

        if old_sms:
            old_sms.code = code
            old_sms.update_count += 1
            old_sms.save()
        else:
            VerificationSms.objects.create(user=None, mobile=mobile, code=code, usage=usage)

        res['status'] = True
        res['message'] = 'کد احراز به شماره {} ارسال شد.'.format(mobile_text)
        return res

    @staticmethod
    def check_code(code, usage, user=None, mobile=None):
        result = {'status': True, 'message': '', 'sms': None}
        if not mobile or not usage:
            raise Exception('bad arguments')
        sms = VerificationSms.objects.filter(mobile=mobile, usage=usage)
        if not sms:
            result['status'] = False
            result['message'] = 'نتیجه‌ای یافت نشد. مجددا درخواست کد کنید.'
            return result
        else:
            sms = sms[0]
            result['sms'] = sms
        if sms.code != code:
            result['status'] = False
            result['message'] = 'کد وارد شده صحیح نیست.'
        if sms.updated_at + timezone.timedelta(minutes=sms.lifetime) < timezone.now():
            result['status'] = False
            result['message'] = 'کد وارد شده منقضی شده است.'
        return result


class MyAccountManager(BaseUserManager):
    def create_user(self, username, password=None):
        if not username:
            raise ValueError('Users must have a username')

        user = self.model(
            username=username,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password):
        user = self.create_user(
            password=password,
            username=username,
        )
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


@receiver(post_save, sender=User)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)