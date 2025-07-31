from django.db import models
from django.contrib.auth.models import User
from authentication.models import SubAdminProfile


class Menu(models.Model):
    subadmin_profile = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE, related_name='menus')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subadmin_profile.restaurant_name} - {self.name}"


class BusinessHour(models.Model):
    DAYS_OF_WEEK = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    subadmin_profile = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE, related_name='business_hours')
    day = models.CharField(max_length=10, choices=DAYS_OF_WEEK)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    closed_all_day = models.BooleanField(default=False)
    menu = models.ForeignKey(Menu, on_delete=models.SET_NULL, null=True, blank=True, related_name='business_hours')

    class Meta:
        unique_together = ('subadmin_profile', 'day')
        ordering = ['id']

    def __str__(self):
        return f"{self.subadmin_profile.restaurant_name} - {self.day}"



class RestaurantLink(models.Model):
    LINK_TYPE_CHOICES = [
        ('ordering', 'Online Ordering'),
        ('reservation', 'Reservation System'),
        ('catering', 'Catering Form'),
    ]
    
    PROVIDER_CHOICES = [
        ('direct', 'Direct Link'),
        ('doordash', 'DoorDash'),
        ('ubereats', 'UberEats'),
        ('grubhub', 'GrubHub'),
        ('opentable', 'OpenTable'),
        ('resy', 'Resy'),
        ('other', 'Other'),
    ]
    
    restaurant = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE, related_name='links')
    link_type = models.CharField(max_length=20, choices=LINK_TYPE_CHOICES)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    url = models.URLField(max_length=500)
    is_verified = models.BooleanField(default=False)
    last_verified = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('restaurant', 'link_type', 'provider')
        ordering = ['link_type', 'provider']

    def __str__(self):
        return f"{self.get_link_type_display()} - {self.get_provider_display()}"
    


class SMSFallbackSettings(models.Model):
    restaurant = models.OneToOneField(
        SubAdminProfile,
        on_delete=models.CASCADE,
        related_name='sms_fallback_settings'
    )
    message = models.TextField(
        default="Thank you for calling {restaurant_name}. Our team couldn't process your request through our automated system. A staff member will call you back shortly. For immediate assistance, please call {phone_number} or visit our website at {website_url}."
    )
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SMS Fallback for {self.restaurant.restaurant_name}"

    def get_processed_message(self):
        """Replace template variables with actual values"""
        return self.message.format(
            restaurant_name=self.restaurant.restaurant_name,
            phone_number=self.restaurant.phone_number,
            website_url=self.restaurant.website_url or "our website"
        )