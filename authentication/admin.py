from django.contrib import admin
from .models import CustomUser, SubAdminProfile, UserProfile

admin.site.register(CustomUser)
admin.site.register(SubAdminProfile)
admin.site.register(UserProfile)
