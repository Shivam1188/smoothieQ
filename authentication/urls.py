from django.urls import path
from .views import (
    RegisterAPIView, LoginAPIView, LogoutAPIView, ForgotPasswordAPIView, ResetPasswordAPIView,
    SubAdminProfileAPIView, UserProfileAPIView, CustomTokenRefreshAPIView
)

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('logout/', LogoutAPIView.as_view(), name='logout'),
    path('refresh-token/', CustomTokenRefreshAPIView.as_view(), name='custom_token_refresh'),
    path('forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),
    path('reset-password/<uidb64>/<token>/', ResetPasswordAPIView.as_view(), name='reset-password'),
    path('profile/subadmin/', SubAdminProfileAPIView.as_view(), name='subadmin-profile'),
    path('profile/user/', UserProfileAPIView.as_view(), name='user-profile'),
]