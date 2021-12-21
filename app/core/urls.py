from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework import routers
from rest_framework.routers import DefaultRouter
from core import views
from django.conf import settings
from django.conf.urls.static import static

router = routers.DefaultRouter()
# router.register('subject', views.SubjectViewSet, basename='subject')

urlpatterns = [
    path('', include(router.urls)),
    path('register/', views.RegistrationView.as_view(), name='register'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('register-request-code/', views.RegisterRequestCodeView.as_view(), name='register-request-code'),
    path('login/', obtain_auth_token, name="login"),
    path('toggle-sim-bookmark/<int:sim_id>/', views.ToggleSimBookmarkView.as_view(), name="toggle-sim-bookmark"),
    path('register-request-code-verification/', views.RegisterRequestCodeVerificationView.as_view(),
         name='register-request-code-verification'),
    path('reset-password-request/', views.ResetPasswordRequestView.as_view(), name='reset-password-request'),
    path('reset-password-check-code/', views.ResetPasswordCheckCodeView.as_view(), name='reset-password-check-code'),
    path('reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),
    path('constants/', views.ConstantsView.as_view(), name='constants'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('login-request-code/', views.LoginRequestCodeView.as_view(), name='login-request-code'),
    path('login-request-code-verification/', views.LoginRequestCodeVerificationView.as_view(),
         name='login-request-code-verification'),
    path('check-user-exist/', views.checkUserExistView.as_view(), name='check-user-exist'),
]
