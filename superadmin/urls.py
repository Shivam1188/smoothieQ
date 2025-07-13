from django.urls import path
from .views import superadmin

urlpatterns = [
    path('superadmin/', superadmin, name='superadmin'),
]