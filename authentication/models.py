# accounts/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

# Role Constants
ROLE_ADMIN = 'admin'
ROLE_SUBADMIN = 'subdir'
ROLE_USER = 'user'

ROLE_CHOICES = [
    (ROLE_ADMIN, 'Admin'),
    (ROLE_SUBADMIN, 'SubAdmin'),
    (ROLE_USER, 'User'),
]

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, role=ROLE_USER, **extra_fields):
        if not email:
            raise ValueError('Users must have an email address')
        email = self.normalize_email(email)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('role', ROLE_ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_USER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return f"{self.email} ({self.role})"



class SubAdminProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='subadmin_profile')
    profile_image = models.ImageField(upload_to='profile_images/subadmins/', blank=True, null=True)
    restaurant_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email_address = models.EmailField()
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    website_url = models.URLField(blank=True, null=True)
    restaurant_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return str(self.user.email) 
    

class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='user_profile')
    profile_image = models.ImageField(upload_to='profile_images/users/', blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    email_address = models.EmailField()
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    zip_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
  
    def __str__(self):
        return self.user.email