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
        return "image/{year}/{month}/{name}".format(year=now.year, month=now.month, name=filename)
    elif ext in ['mp4', 'avi', 'mov', 'mkv']:
        filename = "%s.%s" % (uuid.uuid4(), ext)
        now = datetime.datetime.now()
        now.year, now.month
        return "video/{year}/{month}/{name}".format(year=now.year, month=now.month, name=filename)
    elif ext in ['mp3', 'wav', 'wma', 'au', 'mid']:
        filename = "%s.%s" % (uuid.uuid4(), ext)
        now = datetime.datetime.now()
        now.year, now.month
        return "voice/{year}/{month}/{name}".format(year=now.year, month=now.month, name=filename)
    elif ext in ['pdf', 'word', 'csv', 'xlsx']:
        filename = "%s.%s" % (uuid.uuid4(), ext)
        now = datetime.datetime.now()
        now.year, now.month
        return "file/{year}/{month}/{name}".format(year=now.year, month=now.month, name=filename)
    else:
        raise ValidationError("فقط فرمت های  معتبر مالتی مدیا و فایل قابل قبول هستند !")

class MultiMedia(models.Model):
    class Meta:
        verbose_name = "فایل"
        verbose_name_plural = "فایل ها"

    file_addr = models.FileField(upload_to=get_file_path, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)

class UserMeta(models.Model):
    """User Meta To add extra details to user"""

    class Meta:
        verbose_name = "اطلاعات تکمیلی کاربر"
        verbose_name_plural = "اطلاعات تکمیلی کاربران"

    USER_STUFF = 0
    USER_EMPLOYER = 1
    USER_EMPLOYMENT = 2
    USER_IDEA = 3
    USER_TYPE = (
        (USER_STUFF, 'کاربر عادی'),
        (USER_EMPLOYER, 'کارفرما'),
        (USER_EMPLOYMENT, 'استخدامی'),
        (USER_IDEA, 'شتابدهی'),
    )

    nid = models.CharField(max_length=20, null=True, unique=True)
    phone = models.CharField(max_length=11, null=True, unique=True)
    email = models.CharField(max_length=11, null=True, unique=True)
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    profile_image = models.OneToOneField(MultiMedia, blank=True, null=True, on_delete=models.DO_NOTHING)
    # gender = models.SmallIntegerField(choices=GENDER_CHOICES, default=GENDER_UNKNOWN, null=True)
    type = models.IntegerField(choices=USER_TYPE, default=USER_STUFF, null=True)

    def __str__(self):
        return self.user.first_name +  " "  + self.user.last_name
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


# class Instructor(models.Model):
#     class Meta:
#         verbose_name = "سازنده"
#         verbose_name_plural = "سازنده ها"
#     title = models.CharField(max_length=20, null=True)

#     def __str__(self):
#         return self.title

# class Car(models.Model):
#     class Meta:
#         verbose_name = "ماشین"
#         verbose_name_plural = "ماشین ها"

#     name = models.CharField(max_length=20, null=True)
#     instructor = models.ManyToManyField(Instructor)

#     def __str__(self):
#         return self.name

class Company(models.Model):
    class Meta:
        verbose_name = "شرکت"
        verbose_name_plural = "شرکت ها"

    COMPANY_HOLDING = 0
    COMPANY_COMPANY = 1
    COMPANY_INSTITUE = 2
    COMPANY_STORE = 3
    COMPANY_OTHER = 4
    COMPANY_TYPE = (
        (COMPANY_HOLDING, 'هلدینگ'),
        (COMPANY_COMPANY, 'شرکت'),
        (COMPANY_INSTITUE, 'موسسه'),
        (COMPANY_STORE, 'فروشگاه'),
        (COMPANY_OTHER, 'دیگر'),
    )

    ACTIVITY_PRODUCTION = 0
    ACTIVITY_BUSINESS = 1
    ACTIVITY_SERVICE = 2
    ACTIVITY_INVESTMENT = 3
    ACTIVITY_OTHER = 4
    ACTIVITY_TYPE = (
        (ACTIVITY_PRODUCTION, 'تولیدی'),
        (ACTIVITY_BUSINESS, 'بازرگانی'),
        (ACTIVITY_SERVICE, 'خدماتی'),
        (ACTIVITY_INVESTMENT, 'سرمایه گذاری'),
        (ACTIVITY_OTHER, 'دیگر'),
    )

    name = models.CharField(max_length=50)
    brand_name = models.CharField(max_length=50,null=True)
    manager = models.CharField(max_length=50,null=True)
    phone = models.CharField(max_length=11,null=True)
    address = models.TextField(null=True)
    company_type = models.IntegerField(choices=COMPANY_TYPE, default=COMPANY_COMPANY, null=True)
    activity_type = models.IntegerField(choices=ACTIVITY_TYPE, default=COMPANY_COMPANY, null=True)
    mother_company = models.ForeignKey('Company', on_delete=models.DO_NOTHING, null=True)

    def __str__(self):
        return self.name

class Employer(models.Model):
    
    class Meta:
        verbose_name = "اطلاعات کارفرما"
        verbose_name_plural = "اطلاعات کارفرماها"

    company = models.ForeignKey(Company, blank=True, null=True, on_delete=models.DO_NOTHING)
    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name + " - " + self.company.name

class EmploymentPersonal(models.Model):
    class Meta:
        verbose_name = "اطلاعات استخدامی"
        verbose_name_plural = "اطلاعات استخدامی ها"

    GENDER_MALE = 0
    GENDER_FEMALE = 1
    GENDER_NOTHING = 2
    GENDER_TYPE = (
        (GENDER_MALE, 'مذکر'),
        (GENDER_FEMALE, 'مونث'),
        (GENDER_NOTHING, 'نامشخص'),
    )

    MARITAL_SINGLE = 0
    MARITAL_MARRIED = 1
    MARITAL_STATUS = (
        (MARITAL_SINGLE, 'مجرد'),
        (MARITAL_MARRIED, 'متاهل'),
    )  

    SOLDIER_INCLUDED = 0
    SOLDIER_EXEMPT = 1
    SOLDIER_FINISH = 2
    SOLDIER_STATUS = (
        (SOLDIER_INCLUDED, 'مشمول'),
        (SOLDIER_EXEMPT, 'معاف از خدمت'),
        (SOLDIER_FINISH, 'پایان خدمت'),
    )

    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    birthday = models.DateTimeField(null=True)
    place_of_birth = models.CharField(max_length=50,null=True)
    religion = models.CharField(max_length=50,null=True)
    gender = models.IntegerField(choices=GENDER_TYPE, default=GENDER_MALE, null=True)
    marital = models.IntegerField(choices=MARITAL_STATUS, default=MARITAL_SINGLE, null=True)
    soldier = models.IntegerField(choices=SOLDIER_STATUS, default=SOLDIER_INCLUDED, null=True)
    phone = models.CharField(max_length=11,null=True)
    address = models.TextField(null=True)

    def __str__(self):
            return self.user.first_name + " " + self.user.last_name

class EmploymentAcquaintances(models.Model):
    class Meta:
        verbose_name = "اطلاعات آشنایان استخدامی"
        verbose_name_plural = "اطلاعات آشنایان استخدامی ها"

    COMPANY_STATUS_NOT = 0
    COMPANY_STATUS_YES = 1
    COMPANY_STATUS = (
        (COMPANY_STATUS_NOT, 'خیر'),
        (COMPANY_STATUS_YES, 'بله'),
    )

    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    name = models.CharField(max_length=50,null=True)
    phone = models.CharField(max_length=50,null=True)
    family_relationship = models.CharField(max_length=50,null=True)
    gender = models.IntegerField(choices=COMPANY_STATUS, default=COMPANY_STATUS_NOT, null=True)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name + " - " + self.name

class EmploymentEducation(models.Model):
    class Meta:
        verbose_name = "اطلاعات تحصیلی استخدامی"
        verbose_name_plural = "اطلاعات تحصیلی استخدامی ها"

    EDUCATION_ADEPTNESS = 0
    EDUCATION_EXPERTISE = 1
    EDUCATION_MASTER_DEGREE = 2
    EDUCATION_PROFESSIONAL = 3
    EDUCATION_OTHER = 4
    EDUCATION_LEVEL = (
        (EDUCATION_ADEPTNESS, 'کاردانی'),
        (EDUCATION_EXPERTISE, 'کارشناسی'),
        (EDUCATION_MASTER_DEGREE, 'کارشناسی ارشد'),
        (EDUCATION_PROFESSIONAL, 'دکتری'),
        (EDUCATION_OTHER, 'سایر'),
    )

    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    study = models.CharField(max_length=50,null=True)
    propensity = models.CharField(max_length=50,null=True)
    university = models.CharField(max_length=50,null=True)
    uni_country = models.CharField(max_length=50,null=True)
    uni_city = models.CharField(max_length=50,null=True)
    grade = models.FloatField(null=True)
    proof = models.IntegerField(choices=EDUCATION_LEVEL, default=EDUCATION_ADEPTNESS, null=True)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name + " - " + self.get_proof_display()

class EmploymentJob(models.Model):
    class Meta:
        verbose_name = "اطلاعات کاری استخدامی"
        verbose_name_plural = "اطلاعات کاری استخدامی ها"

    ASSIST_FULLTIME = 0
    ASSIST_PARTTIME = 1
    ASSIST_PROJECT = 2
    ASSIST_TELEWORKING = 3
    ASSIST_INTERNSHIP = 4
    ASSIST_TYPE = (
        (ASSIST_FULLTIME, 'تمام وقت'),
        (ASSIST_PARTTIME, 'پاره وقت'),
        (ASSIST_PROJECT, 'پروژه‌ای'),
        (ASSIST_TELEWORKING, 'دور کاری'),
        (ASSIST_INTERNSHIP, 'کارآموزی'),
    )

    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    company = models.CharField(max_length=50,null=True)
    organization_level = models.CharField(max_length=50,null=True)
    start_date = models.DateTimeField(null=True)
    end_date = models.DateTimeField(null=True)
    last_salary = models.SmallIntegerField(null=True)
    job_description = models.TextField(null=True)
    leave_reason = models.TextField(null=True)
    resume = models.OneToOneField(MultiMedia, blank=True, null=True, on_delete=models.DO_NOTHING)
    assist_type = models.IntegerField(choices=ASSIST_TYPE, default=ASSIST_FULLTIME, null=True)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name + " - " + self.company

class EmploymentProfessionalCourse(models.Model):
    class Meta:
        verbose_name = "دوره‌های تخصصی استخدامی"
        verbose_name_plural = "دوره های تخصصی استخدامی ها"

    PROOF_NOT = 0
    PROOF_YES = 1
    PROOF_STATUS = (
        (PROOF_NOT, 'ندارد'),
        (PROOF_YES, 'دارد'),
    )

    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    title = models.CharField(max_length=50,null=True)
    duration = models.CharField(max_length=50,null=True)
    description = models.TextField(null=True)
    proof = models.IntegerField(choices=PROOF_STATUS, default=PROOF_NOT, null=True)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name + " - " + self.title

class EmploymentJobCondition(models.Model):
    class Meta:
        verbose_name = "شرایط کاری استخدامی"
        verbose_name_plural = "شرایط کاری استخدامی ها"

    ASSIST_FULLTIME = 0
    ASSIST_PARTTIME = 1
    ASSIST_PROJECT = 2
    ASSIST_TELEWORKING = 3
    ASSIST_INTERNSHIP = 4
    ASSIST_TYPE = (
        (ASSIST_FULLTIME, 'تمام وقت'),
        (ASSIST_PARTTIME, 'پاره وقت'),
        (ASSIST_PROJECT, 'پروژه‌ای'),
        (ASSIST_TELEWORKING, 'دور کاری'),
        (ASSIST_INTERNSHIP, 'کارآموزی'),
    )

    LONG_COOPERATION_NOT = 0
    LONG_COOPERATION_YES = 1
    LONG_COOPERATION_STATUS = (
        (LONG_COOPERATION_NOT, 'خیر'),
        (LONG_COOPERATION_YES, 'بله'),
    )

    FAST_LINK_MOBILE = 0
    FAST_LINK_PHONE = 1
    FAST_LINK_EMAIL = 2
    FAST_LINK_TYPE = (
        (FAST_LINK_MOBILE, 'شماره موبایل'),
        (FAST_LINK_PHONE, 'تلفن ثابت'),
        (FAST_LINK_EMAIL, 'ایمیل'),
    )

    CONFIRM_NOT = 0
    CONFIRM_YES = 1
    CONFIRM_STATUS = (
        (CONFIRM_NOT, 'خیر'),
        (CONFIRM_YES, 'بله'),
    )

    WAY_WEBSITE = 0
    WAY_ADVERTISE = 1
    WAY_FRIEND = 2
    WAY_ORIENTED_WITH_US = (
        (WAY_WEBSITE, 'وبسایت'),
        (WAY_ADVERTISE, 'تبلیغات'),
        (WAY_FRIEND, 'دوستان'),
    )

    JOB_PROMOTION = 0
    CHANGE_JOB = 1
    CREATE_BUSSINESS = 2
    CONTINUE_EDUCATION = 3
    JOB_STOP = 4
    GOING_ABOARD = 5
    LONG_TIME_PLAN = (
        (JOB_PROMOTION, 'ارتقای شغل'),
        (CHANGE_JOB, 'تغییر شغل'),
        (CREATE_BUSSINESS, 'راه اندازی بیزینس'),
        (CONTINUE_EDUCATION, 'ادامه تحصیل'),
        (JOB_STOP, 'ترک کار'),
        (GOING_ABOARD, 'رفتن به خارج از کشور'),
    )

    user = models.OneToOneField(User, on_delete=models.DO_NOTHING)
    salary = models.SmallIntegerField(null=True)
    start_date = models.DateTimeField(null=True)
    reason_change_job = models.TextField(null=True)
    reason_select_job = models.TextField(null=True)
    reason_choice_you = models.TextField(null=True)
    description = models.TextField(null=True)
    assist_type = models.IntegerField(choices=ASSIST_TYPE, default=ASSIST_FULLTIME, null=True)
    long_cooperation = models.IntegerField(choices=LONG_COOPERATION_STATUS, default=LONG_COOPERATION_NOT, null=True)
    fast_link = models.IntegerField(choices=FAST_LINK_TYPE, default=FAST_LINK_MOBILE, null=True)
    confirm = models.IntegerField(choices=CONFIRM_STATUS, default=CONFIRM_NOT, null=True)
    way_oriented = models.IntegerField(choices=WAY_ORIENTED_WITH_US, default=WAY_WEBSITE, null=True)
    long_time_plan = models.IntegerField(choices=LONG_TIME_PLAN, default=JOB_PROMOTION, null=True)

    def __str__(self):
        return self.user.first_name + " " + self.user.last_name + " - " + self.salary

class Recruitment(models.Model):
    class Meta:
        verbose_name = "آگهی استخدام"
        verbose_name_plural = "آگهی های استخدام"

    TECHNICAL = 0
    OFFICIAL = 1
    SERVICE = 2
    MANAGER = 3
    DEPARTMENT = (
        (TECHNICAL, 'فنی'),
        (OFFICIAL, 'اداری'),
        (SERVICE, 'خدماتی'),
        (MANAGER, 'مدیریتی'),
    )

    ASSIST_FULLTIME = 0
    ASSIST_PARTTIME = 1
    ASSIST_PROJECT = 2
    ASSIST_TELEWORKING = 3
    ASSIST_INTERNSHIP = 4
    ASSIST_TYPE = (
        (ASSIST_FULLTIME, 'تمام وقت'),
        (ASSIST_PARTTIME, 'پاره وقت'),
        (ASSIST_PROJECT, 'پروژه‌ای'),
        (ASSIST_TELEWORKING, 'دور کاری'),
        (ASSIST_INTERNSHIP, 'کارآموزی'),
    )

    title = models.CharField(max_length=50,null=True)
    description = models.TextField(null=True)
    salary = models.SmallIntegerField(null=True)
    address = models.TextField(null=True)
    department = models.IntegerField(choices=DEPARTMENT, default=TECHNICAL, null=True)
    assist_type = models.IntegerField(choices=ASSIST_TYPE, default=ASSIST_FULLTIME, null=True)

    def __str__(self):
        return self.title

class RecruitmentSkills(models.Model):
    class Meta:
        verbose_name = "مهارت آگهی استخدام"
        verbose_name_plural = "مهارت های آگهی استخدام"

    PUBLIC = 0
    PRIVATE_REQUIRE = 1
    PRIVATE_OPTIONAL = 2
    SKILL_TYPE = (
        (PUBLIC, 'اجتماعی'),
        (PRIVATE_REQUIRE, 'اختصاصی (الزامی)'),
        (PRIVATE_OPTIONAL, 'اختصاصی (اختیاری)'),
    )

    title = models.CharField(max_length=50,null=True)
    skill = models.IntegerField(choices=SKILL_TYPE, default=PUBLIC, null=True)
    recruitment = models.ForeignKey(Recruitment, on_delete=models.DO_NOTHING)

    def __str__(self):
        return self.recruitment.title + " - " + self.title
class Project(models.Model):
    class Meta:
        verbose_name = "پروژه"
        verbose_name_plural = "پروژه ها"

    title = models.CharField(max_length=50,null=True)

    def __str__(self):
        return self.title

class FidarDetail(models.Model):

    LOCAL = 0
    REGIONAL = 1
    NATIONAL = 2
    INTERNATIONAL = 3
    MARKET_RANGE = (
        (LOCAL, 'محلی'),
        (REGIONAL, 'منطقه ای'),
        (NATIONAL, 'ملی'),
        (INTERNATIONAL, 'بین المللی'),
    )

    WEBSITE_NOT = 0
    WEBSITE_YES = 1
    WEBSITE_STATUS = (
        (WEBSITE_NOT, 'خیر'),
        (WEBSITE_YES, 'بله'),
    )

    SOFTWARE_NOT = 0
    SOFTWARE_YES = 1
    SOFTWARE_STATUS = (
        (SOFTWARE_NOT, 'خیر'),
        (SOFTWARE_YES, 'بله'),
    )

    PROBLEM_1 = 0
    PROBLEM_2 = 1
    PROBLEM_3 = 2
    PROBLEM_4 = 3
    PROBLEM_5 = 4
    PROBLEM_6 = 5
    PROBLEM_7 = 6
    PROBLEM_8 = 7
    PROBLEM_9 = 8
    PROBLEM_10 = 9
    PROBLEM_11 = 10
    SOFTWARE_PROBLEM = (
        (PROBLEM_1, 'عدم یکپارچگی'),
        (PROBLEM_2, 'عدم پاسخگویی به دامنه وسیع نیازها'),
        (PROBLEM_3, 'قدیمی بودن تکنولوژی'),
        (PROBLEM_4, 'تحت وب نبودن'),
        (PROBLEM_5, 'تحلیل نرم افزاری ضعیف'),
        (PROBLEM_6, 'بروز رسانی کم'),
        (PROBLEM_7, 'رابط کاربری ضعیف'),
        (PROBLEM_8, 'ضعف پشتیبانی'),
        (PROBLEM_9, 'ضعف امنیتی'),
        (PROBLEM_10, 'پیچیدگی'),
        (PROBLEM_11, 'گرانی قیمت'),
    )

    WAY_WEBSITE = 0
    WAY_ADVERTISE = 1
    WAY_FRIEND = 2
    WAY_ORIENTED_WITH_US = (
        (WAY_WEBSITE, 'وبسایت'),
        (WAY_ADVERTISE, 'تبلیغات'),
        (WAY_FRIEND, 'آشنایان'),
    )

    CUSTOMER_1 = 0
    CUSTOMER_2 = 1
    CUSTOMER_3 = 2
    CUSTOMER_4 = 3
    CUSTOMER_5 = 4
    CUSTOMER_6 = 5
    CUSTOMER_TYPE = (
        (CUSTOMER_1, 'مشتریان بالقوه'),
        (CUSTOMER_2, 'مشتریان موجود'),
        (CUSTOMER_3, 'نمایندگی ها و عاملین فروش'),
        (CUSTOMER_4, 'تامین کنندگان'),
        (CUSTOMER_5, 'کارکنان'),
        (CUSTOMER_6, 'متقاضیان استخدام'),
    )

    REQUEST_1 = 0
    REQUEST_2 = 1
    REQUEST_3 = 2
    REQUEST_4 = 3
    REQUEST_5 = 4
    REQUEST_6 = 5
    REQUEST_7 = 6
    REQUEST_8 = 7
    REQUEST_9 = 8
    REQUEST_10 = 9
    REQUEST_11 = 10
    REQUEST_12 = 11
    EMPLOYER_REQUESTS = (
        (REQUEST_1, 'افزایش فروش'),
        (REQUEST_2, 'استانداردسازی فرآیندهای تجاری و سیستم‌سازی'),
        (REQUEST_3, 'کاهش هزینه‌ها'),
        (REQUEST_4, 'ایجاد یکپارچگی'),
        (REQUEST_5, 'تقویت توان رقابتی'),
        (REQUEST_6, 'تسلط اطلاعاتی بر کسب و کار'),
        (REQUEST_7, 'تقویت جایگاه برند'),
        (REQUEST_8, 'بهبود زنجیره تأمین'),
        (REQUEST_9, 'گسترش دامنه جغرافیایی فعالیت کسب و کار'),
        (REQUEST_10, 'ایجاد یکپارچگی'),
        (REQUEST_11, 'افزایش بهره‌وری'),
        (REQUEST_12, 'بهبود کیفیت خدمات پس از فروش '),
    )

    MODULE_1 = 0
    MODULE_2 = 1
    MODULE_3 = 2
    MODULE_4 = 3
    MODULE_5 = 4
    MODULE_6 = 5
    MODULE_7 = 6
    MODULE_8 = 7
    MODULE_9 = 8
    MODULE_10 = 9
    MODULE_11 = 10
    MODULE_12 = 11
    MODULE_13 = 12
    MODULE_14 = 13
    MODULE_15 = 14
    MODULE_16 = 15
    MODULE_17 = 16
    MODULE_18 = 17
    MODULE_LIST = (
        (MODULE_1, 'بازاریابی و فروش'),
        (MODULE_2, 'مالی و حسابداری'),
        (MODULE_3, 'پایانه‌های فروش'),
        (MODULE_4, 'منابع انسانی'),
        (MODULE_5, 'توسعه و مدیریت شبکه فروش'),
        (MODULE_6, 'مدیریت پروژه، برنامه‌ریزی و گزارش عملکرد'),
        (MODULE_7, 'مدیریت انبار'),
        (MODULE_8, 'امور قراردادها و مستندات'),
        (MODULE_9, 'مدیریت وب سایت'),
        (MODULE_10, 'تعاملات بین‌المللی'),
        (MODULE_11, 'تجارت الکترونیکی و فروش آنلاین'),
        (MODULE_12, 'پشتیبانی و خدمات پس از فروش'),
        (MODULE_13, 'تولید'),
        (MODULE_14, 'وویپ و تلفن'),
        (MODULE_15, 'تعمیر و نگهداری'),
        (MODULE_16, 'آموزش'),
        (MODULE_17, 'کنترل کیفیت'),
        (MODULE_18, 'حمل و نقل'),
    )

    class Meta:
        verbose_name = "درخواست پروژه فیدار"
        verbose_name_plural = "درخواست های پروژه فیدار"

    project = models.ForeignKey(Project,default=1, on_delete=models.DO_NOTHING)
    product_type = models.CharField(max_length=50,null=True)
    hr_number = models.IntegerField(null=True)
    it_man_number = models.IntegerField(null=True)
    agency_number = models.IntegerField(null=True)
    website_url = models.CharField(max_length=50,null=True)
    software_name = models.CharField(max_length=50,null=True)
    death_line = models.CharField(max_length=50,null=True)
    website = models.IntegerField(choices=WEBSITE_STATUS, default=WEBSITE_NOT, null=True)
    software = models.IntegerField(choices=SOFTWARE_STATUS, default=SOFTWARE_NOT, null=True)
    market_range = models.IntegerField(choices=MARKET_RANGE, default=LOCAL, null=True)
    software_problem = models.CharField(max_length=10, null=True) 
    employer_request = models.CharField(max_length=10, null=True) 
    module = models.CharField(max_length=10, null=True) 
    way_oriented = models.IntegerField(choices=WAY_ORIENTED_WITH_US, default=WAY_WEBSITE, null=True)



    
    