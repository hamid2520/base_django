from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework import generics
from drf_yasg.utils import swagger_auto_schema
from django.db.models import Q
from rest_framework.serializers import ValidationError
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector, TrigramSimilarity
from django.db.models import Value
from rest_framework.authtoken.models import Token

from .util.authentication import CustomTokenAuthentication
from .util.date import date, greDatetime, to_jalali_weekday

from functools import reduce
from operator import or_

from . import serializers
from . import models
from .util.extend import StandardResultsSetPagination, RetrieveListViewSet, raise_not_field_error, \
    CreateRetrieveListUpdateDeleteViewSet, RetrieveListDeleteViewSet
from .util.helper import play_filtering_form
from .util.mixin import IsAuthenticatedPermission
import math
from itertools import chain
import random
import datetime
import os
import json
from types import SimpleNamespace
from rest_framework.parsers import JSONParser
from dateutil.relativedelta import *
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.renderers import JSONRenderer
from wkhtmltopdf.views import PDFTemplateResponse
from rest_framework.parsers import MultiPartParser, FormParser
import uuid
from django.conf import settings
from django.apps import apps



class RegistrationView(APIView):

    @swagger_auto_schema(
        operation_description="Users : all",
        operation_summary="ثبت ‌نام کاربر",
        security=[],
        request_body=serializers.RegistrationSerializer,
        responses={200: ''}
    )
    def post(self, request, *args, **kwargs):
        serializer = serializers.RegistrationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid(raise_exception=True):
            user = serializer.save()
        return Response(status=200)


class RegisterRequestCodeView(generics.CreateAPIView):
    serializer_class = serializers.RegisterRequestCodeSerializer


class RegisterRequestCodeVerificationView(generics.CreateAPIView):
    serializer_class = serializers.RegisterRequestCodeVerificationSerializer


class ProfileView(IsAuthenticatedPermission, APIView):

    @swagger_auto_schema(
        operation_description="Users : authenticated users",
        operation_summary="ویرایش اطلاعات کاربر",
        request_body=serializers.UserSerializer,
        responses={200: ''})
    def patch(self, request, *args, **kwargs):
        instance = request.user
        serializer = serializers.UserSerializer(instance=instance, data=request.data, context={'request': request},
                                                partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status.HTTP_200_OK)

    @swagger_auto_schema(
        operation_description="Users : authenticated users",
        operation_summary="ویرایش اطلاعات کاربر",
        request_body=serializers.UserSerializer,
        responses={200: ''})
    def put(self, request, *args, **kwargs):
        instance = request.user
        serializer = serializers.UserSerializer(instance=instance, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status.HTTP_200_OK)

    @swagger_auto_schema(responses={200: serializers.UserSerializer()})
    def get(self, request, *args, **kwargs):
        serializer = serializers.UserSerializer()
        instance = request.user
        return Response(serializer.to_representation(instance=instance), status.HTTP_200_OK)


class ResetPasswordRequestView(generics.CreateAPIView):
    serializer_class = serializers.ResetPasswordRequestSerializer


class ResetPasswordCheckCodeView(generics.CreateAPIView):
    serializer_class = serializers.ResetPasswordCheckCodeSerializer


class ResetPasswordView(generics.CreateAPIView):
    serializer_class = serializers.ResetPasswordSerializer


def my_filter(queryset, selfs):
    query_params = selfs.request.query_params
    request = selfs.request
    user = request.user
    queryset_filtering = models.Sim()
    for param in query_params:
        value = query_params.get(param)

        if not value:
            continue
        if value == 'None':
            value = None
        if param == 'my_own_sim':
            aceess_query = models.SimAccessList.objects.filter(user=user)
            grade_query = models.Grade.objects.filter(pk__in=aceess_query)
            subject_query = models.Subject.objects.filter(pk__in=aceess_query)
            queryset = queryset.filter(grade__in=grade_query, subject__in=subject_query)
            # for query in queryset:
            # is_for_me = models.Sim.is_subscribed(query,user)
            # if not is_for_me:
            #     queryset_filtering.clea
            # aceess_query = models.AccessList(user=user)    
            # queryset = queryset.filter(models.Sim.pk.in(access))

    return queryset


class FileView(IsAuthenticatedPermission, APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        data = request.data
        max_d = settings.SITE_SETTINGS['MAX_UPLOADED_SIM_REPORT_IMG']
        sim_id = self.request.data.get('sim')
        sim = models.SimReportImg.objects.filter(sim=sim_id, user=self.request.user)
        if sim.count() >= max_d:
            return Response({
                "details": 'شما به حداکثر تعداد اپلود تصویر برای این ازمایش رسیده اید درصورت نیاز یک تصویر را حذف کنید !'},
                status=status.HTTP_400_BAD_REQUEST)
        if not request.FILES:
            return Response({"details": 'فایلی ارسال نشده'}, status=status.HTTP_400_BAD_REQUEST)
        for f in request.FILES.getlist('img_addr'):
            data['img_addr'] = f
            file_serializer = serializers.SimReportImgSerializer(data=data)
            if file_serializer.is_valid():
                file_serializer.save(user=self.request.user)
            else:
                return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        sim_img = models.SimReportImg.objects.filter(user=self.request.user, sim=self.request.data.get('sim'))
        sim_img_serializer = serializers.SimReportImgSerializer(sim_img, many=True)
        return Response(sim_img_serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        img_id = self.request.data.get('img')
        img = models.SimReportImg.objects.filter(id=img_id).first()
        if img:
            if img.user != request.user:
                raise_not_field_error('شما نمیتوانید این فایل را حذف کنید')
            if img.img_addr:
                img.img_addr.delete()
            img.delete()
            return Response(status=status.HTTP_200_OK)
        return Response({"details": 'فایلی ارسال نشده'}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, sim_id):
        sim = sim_id
        user = self.request.user
        img = models.SimReportImg.objects.filter(sim=sim, user=user).all()
        sim_img_serializer = serializers.SimReportImgSerializer(img, many=True)
        return Response(sim_img_serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(IsAuthenticatedPermission, APIView):

    def put(self, request, *args, **kwargs):
        user = self.request.user
        serializer = serializers.ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            # Check old password
            old_password = serializer.data.get("old_password")
            if not user.check_password(old_password):
                return Response({"old_password": ["رمز عبور قبلی نادرست است"]},
                                status=status.HTTP_400_BAD_REQUEST)
            # set_password also hashes the password that the user will get
            user.set_password(serializer.data.get("new_password"))
            user.save()
            return Response({"details": 'رمز عبور با موفقیت تغییر کرد .'}, status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginRequestCodeView(generics.CreateAPIView):
    serializer_class = serializers.LoginRequestCodeSerializer


class LoginRequestCodeVerificationView(generics.CreateAPIView):
    serializer_class = serializers.LoginRequestCodeVerificationSerializer


class checkUserExistView(generics.CreateAPIView):
    serializer_class = serializers.checkUserSerializer

