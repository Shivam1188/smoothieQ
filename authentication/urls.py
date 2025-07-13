from django.urls import path
from .views import (
    RegisterAPIView, LoginAPIView,
    SubAdminProfileAPIView, UserProfileAPIView
)

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('profile/subadmin/', SubAdminProfileAPIView.as_view(), name='subadmin-profile'),
    path('profile/user/', UserProfileAPIView.as_view(), name='user-profile'),
]