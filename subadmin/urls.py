from django.urls import path
from .views import subadmin

urlpatterns = [
    path('subadmin/', subadmin, name='subadmin'),
]