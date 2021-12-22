from rest_framework import serializers
from django.contrib.auth.models import User
from django.db import models
from .util.extend import map_iran_fields
from .util.helper import CellphoneField, is_valid_iran_national_id, NationalIdField
from .models import UserMeta, VerificationSms
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from django.db.models import Q
from django.conf import settings
from django.templatetags.static import static
import math
from hashids import Hashids
from rest_framework.authtoken.models import Token

map_iran_fields(serializers, models)


class RegistrationSerializer(serializers.Serializer):
    phone = CellphoneField(label='موبایل', required=True, min_length=11)
    password = serializers.CharField(label='کلمه عبور', min_length=4, max_length=20, required=False)
    password_confirm = serializers.CharField(label='تکرار کلمه عبور', required=False)
    code = serializers.CharField(label='کد', required=False, max_length=5)
    first_name = serializers.CharField(label='نام', required=False, max_length=40)
    last_name = serializers.CharField(label='نام خانوادگی', required=False, max_length=40)
    nid = serializers.CharField(label='کد ملی', required=False, max_length=10)
    type = serializers.IntegerField(label='نوع کاربر')

    def save(self):
        user = User.objects.create(
            username=self.validated_data['phone'],
            first_name=self.validated_data['first_name'],
            last_name=self.validated_data['last_name'],
        )
        user.set_password(self.validated_data['password'])
        user.save()
        UserMeta.objects.create(
            user=user,
            phone=self.validated_data['phone'],
            nid=self.validated_data.get('nid', None),
            type=self.validated_data.get('type', 0),
        )
        return user

    def validate_phone(self, value):
        if UserMeta.objects.filter(phone=value).exists():
            raise serializers.ValidationError("این شماره موبایل قبلا ثبت شده است.")
        return value

    def validate_nid(self, value):
        if not is_valid_iran_national_id(value):
            raise serializers.ValidationError("کد ملی معتبر نیست.")
        if UserMeta.objects.filter(nid=value).exists():
            raise serializers.ValidationError("این کد ملی قبلا ثبت شده است.")
        return value

    def validate_password_confirm(self, value):
        data = self.initial_data
        if data['password'] != value:
            raise serializers.ValidationError("تکرار کلمه عبور اشتباه است.")
        return value

    def validate(self, attrs):
        code = attrs.get('code', None)
        if not code:
            res = VerificationSms.send_code(attrs['phone'], VerificationSms.USAGE_REGISTERATION)
            raise serializers.ValidationError(res['message'])
        else:
            if not attrs.get('first_name', None):
                raise serializers.ValidationError({"first_name": ['این مقدار لازم است.']})

            if not attrs.get('last_name', None):
                raise serializers.ValidationError({"last_name": ['این مقدار لازم است.']})

            if not attrs.get('type', None):
                raise serializers.ValidationError({"type": ['این مقدار لازم است.']})

            if not attrs.get('password', None):
                raise serializers.ValidationError({"password": ['این مقدار لازم است.']})

            if not attrs.get('password_confirm', None):
                raise serializers.ValidationError({"password_confirm": ['این مقدار لازم است.']})

            res = VerificationSms.check_code(code, VerificationSms.USAGE_REGISTERATION, None,
                                             attrs['phone'])
            if not res['status']:
                raise serializers.ValidationError({"code": [res['message']]})
            else:
                return attrs


class RegisterRequestCodeSerializer(serializers.Serializer):
    phone = CellphoneField(label='موبایل', required=True)

    def create(self, validated_data):
        res = VerificationSms.send_code(validated_data.get('phone'), VerificationSms.USAGE_REGISTERATION)
        if not res['status']:
            raise serializers.ValidationError({'results': res['message']}, code='authorization')
        return validated_data

    def validate(self, attrs):
        phone = attrs.get('phone')
        if UserMeta.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("login")
        return attrs


class MiniUserMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserMeta
        exclude = ['user', 'nid']
        extra_kwargs = {
            'phone': {'read_only': True},
        }


class PrivateUserMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']

    def to_representation(self, instance):
        request = self.context.get('request')
        data = super(PrivateUserMetaSerializer, self).to_representation(instance)
        nid = instance.usermeta.nid
        star_nid = list(str(nid))
        star_nid[4] = '*'
        star_nid[5] = '*'
        star_nid[6] = '*'
        str1 = ""
        for ele in star_nid:
            str1 += ele
        data['n_id'] = str1
        return data


class UserMetaSerializer(serializers.ModelSerializer):
    nid = NationalIdField(required=True, min_length=10, max_length=10, allow_blank=False, allow_null=False)

    class Meta:
        model = UserMeta
        exclude = ['user']
        extra_kwargs = {
            'phone': {'read_only': True},
        }

    def to_representation(self, instance):
        hashids = Hashids(min_length=settings.HASHIDS['MIN_LENGTH'], alphabet=settings.HASHIDS['ALPHABET'])
        request = self.context.get('request')
        data = super(UserMetaSerializer, self).to_representation(instance)
        data['point'] = instance.calculate_point(user=instance.user)
        data['count_unread_message'] = instance.calculate_unread_message(user=instance.user)
        data['defult_profile'] = settings.STATIC_URL + "core/img/" + str(instance.gender) + ".jpg"
        data['invitation_code'] = hashids.encode(instance.user.id)
        # data['gender'] = None
        # try:
        #     acc_list = instance.user.accesslist
        # except:
        #     return data
        # gender = None
        # if acc_list:
        #     for tk_sim in acc_list.token_sim.all():
        #         if tk_sim.contract.education:
        #             gender = tk_sim.contract.education.gender
        #             break
        # data['gender'] = gender
        return data

    def update(self, instance, validated_data):
        return super(UserMetaSerializer, self).update(instance, validated_data)

    # def validate_phone(self, value):
    #     if UserMeta.objects.filter(phone=value).exclude(id=self.context.get('request').user.usermeta.id).exists():
    #         raise serializers.ValidationError("شماره موبایل قبلا در سیستم ثبت شده است.")
    #     return value

    def validate_nid(self, value):
        if UserMeta.objects.filter(nid=value).exclude(user=self.context.get('request').user).exists():
            raise serializers.ValidationError("کد ملی قبلا در سیستم ثبت شده است.")
        return value


class UserSerializer(serializers.ModelSerializer):
    usermeta = UserMetaSerializer()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'username', 'usermeta', 'is_active']
        extra_kwargs = {
            'id': {'read_only': True},
            'first_name': {'required': True, 'allow_blank': False, 'min_length': 3},
            'last_name': {'required': True, 'allow_blank': False, 'min_length': 3},
            'username': {'read_only': True},
            'is_active': {'read_only': True}
        }

    def update(self, instance, validated_data):
        usermeta_serializer = self.fields['usermeta']
        usermeta_instance = instance.usermeta
        usermeta_data = validated_data.pop('usermeta', None)
        if usermeta_data:
            usermeta_serializer.update(usermeta_instance, usermeta_data)
        return super(UserSerializer, self).update(instance, validated_data)

    def validate_email(self, value):
        if User.objects.filter(email=value).exclude(id=self.context.get('request').user.id).exists():
            raise serializers.ValidationError("ایمیل قبلا در سیستم ثبت شده است.")
        return value


class ResetPasswordRequestSerializer(serializers.Serializer):
    username = serializers.CharField(label='Username', required=True, max_length=60)
    _user = None

    def create(self, validated_data):
        res = VerificationSms.send_code(validated_data.get('username'), usage=VerificationSms.USAGE_RESET_PASSWORD)
        # raise serializers.ValidationError({'results': res['message']}, code='authorization')
        return validated_data

    def validate_username(self, value):
        try:
            # search for number in user model
            user = User.objects.get(
                Q(usermeta__phone=value) | Q(usermeta__nid=value) | Q(username=value) | Q(
                    email=value))
            self._user = user
            # if not user.is_active:
            #     raise serializers.ValidationError(_("Username is not active!"))
        except User.DoesNotExist:
            raise serializers.ValidationError('کاربر یافت نشد.')
        return value


class ResetPasswordSerializer(serializers.Serializer):
    username = serializers.CharField(label='username', required=True, max_length=60)
    code = serializers.CharField(label='code', required=True, max_length=5)
    password = serializers.CharField(label='password', min_length=4, max_length=20, required=True)
    password_confirm = serializers.CharField(label='confirm password', required=True)
    # _sms = None
    _user = None

    def create(self, validated_data):
        self._user.set_password(validated_data['password'])
        # self._user.is_active = True
        try:
            usermeta = self._user.usermeta
            usermeta.mobile_verified = True
            usermeta.save()
        except UserMeta.DoesNotExist:
            pass
        self._user.save()

        # delete sms
        # self._sms.delete()

        return validated_data

    def validate_password_confirm(self, value):
        data = self.initial_data
        if data['password'] != value:
            raise serializers.ValidationError("تکرار کلمه عبور اشتباه است.")
        return value

    def validate_code(self, value):
        data = self.initial_data
        try:
            user = User.objects.get(
                Q(usermeta__phone=data['username']) | Q(usermeta__nid=data['username']) | Q(
                    username=data['username']) | Q(
                    email=data['username']))
        except User.DoesNotExist:
            raise serializers.ValidationError('کاربر یافت نشد.')
        res = VerificationSms.check_code(user=user, code=value, usage=VerificationSms.USAGE_RESET_PASSWORD,
                                         mobile=data['username'])
        # self._sms = sms
        self._user = user
        if res['status']:
            return value
        raise serializers.ValidationError(res['message'])


class ResetPasswordCheckCodeSerializer(serializers.Serializer):
    username = serializers.CharField(label='username', required=True, max_length=60)
    code = serializers.CharField(label='code', required=True, max_length=5)

    def create(self, validated_data):
        return validated_data

    def validate_code(self, value):
        data = self.initial_data
        try:
            user = User.objects.get(
                Q(usermeta__phone=data['username']) | Q(usermeta__nid=data['username']) | Q(
                    username=data['username']) | Q(
                    email=data['username']))
        except User.DoesNotExist:
            raise serializers.ValidationError("کاربر یافت نشد.")
        res = VerificationSms.check_code(user=user, code=value, usage=VerificationSms.USAGE_RESET_PASSWORD,
                                         mobile=data['username'])
        if res['status']:
            return value
        raise serializers.ValidationError(res['message'])


class RegisterRequestCodeVerificationSerializer(serializers.Serializer):
    code = serializers.CharField(label='کد', required=True, max_length=5)
    phone = CellphoneField(label='موبایل', required=True, min_length=11)

    def save(self):
        return self.validated_data['phone']

    def validate(self, attrs):
        code = attrs.get('code', None)
        res = VerificationSms.check_code(code, VerificationSms.USAGE_REGISTERATION, None,
                                         attrs['phone'])
        if not res['status']:
            raise serializers.ValidationError({"code": [res['message']]})
        else:
            sms = res['sms']
            sms.lifetime = 30  # minutes
            sms.save()
            return attrs


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(label='کلمه عبور قدیم', min_length=4, max_length=20, required=False)
    new_password = serializers.CharField(label='کلمه عبور جدید', min_length=4, max_length=20, required=False)
    password_confirm = serializers.CharField(label='تکرار کلمه عبور', required=False)

    def validate_password_confirm(self, value):
        data = self.initial_data
        if data['new_password'] != value:
            raise serializers.ValidationError("تکرار کلمه عبور اشتباه است.")
        return value

    def validate(self, attrs):
        if not attrs.get('old_password', None):
            raise serializers.ValidationError({"old_password": ['این مقدار لازم است.']})

        if not attrs.get('new_password', None):
            raise serializers.ValidationError({"new_password": ['این مقدار لازم است.']})
        else:
            return attrs


class LoginRequestCodeSerializer(serializers.Serializer):
    phone = CellphoneField(label='موبایل', required=True)

    def create(self, validated_data):
        res = VerificationSms.send_code(validated_data.get('phone'), VerificationSms.USAGE_LOGIN)
        if not res['status']:
            raise serializers.ValidationError({'results': res['message']}, code='authorization')
        return validated_data

    def validate(self, attrs):
        phone = attrs.get('phone')
        if not UserMeta.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("کاربری با این شماره تلفن همراه ثبت نشده است .")
        return attrs


class LoginRequestCodeVerificationSerializer(serializers.Serializer):
    code = serializers.CharField(label='کد', required=True, max_length=5)
    phone = CellphoneField(label='موبایل', required=True, min_length=11)
    token = serializers.CharField(label='توکن', required=False, min_length=1024)

    def save(self):
        user_meta = UserMeta.objects.filter(phone=self.validated_data['phone']).first()
        token = Token.objects.get(user=user_meta.user).key
        self.validated_data['token'] = token
        return self.validated_data

    def validate(self, attrs):
        code = attrs.get('code', None)
        res = VerificationSms.check_code(code, VerificationSms.USAGE_LOGIN, None,
                                         attrs['phone'])
        if not res['status']:
            raise serializers.ValidationError({"code": [res['message']]})
        else:
            sms = res['sms']
            sms.lifetime = 30  # minutes
            sms.save()
            return attrs


class checkUserSerializer(serializers.Serializer):
    phone = CellphoneField(label='موبایل', required=True)

    def create(self, validated_data):
        return validated_data

    def validate(self, attrs):
        phone = attrs.get('phone')
        if not UserMeta.objects.filter(phone=phone).exists():
            raise serializers.ValidationError("کاربری با این شماره تلفن همراه ثبت نشده است .")
        return attrs
