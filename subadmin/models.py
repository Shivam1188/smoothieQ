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



class MenuItem(models.Model):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_available = models.BooleanField(default=True)
    display_order = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return f"{self.menu.name} - {self.name}"


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
    restaurant_name = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE, related_name="restaurant_links", null=True, blank=True)
    direct_ordering_link = models.URLField(blank=True, null=True)
    doordash_link = models.URLField(blank=True, null=True)
    ubereats_link = models.URLField(blank=True, null=True)
    grubhub_link = models.URLField(blank=True, null=True)
    direct_reservation_link = models.URLField(blank=True, null=True)
    opentable_link = models.URLField(blank=True, null=True)
    resy_link = models.URLField(blank=True, null=True)
    catering_request_form = models.URLField(blank=True, null=True)
    special_events_form = models.URLField(blank=True, null=True)

    def __str__(self):
        return str(self.restaurant_name.restaurant_name) if self.restaurant_name else f"Restaurant Link #{self.id}"

    


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
    


class UserSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    current_step = models.CharField(max_length=50, default='welcome')
    restaurant = models.ForeignKey(SubAdminProfile, null=True, blank=True, on_delete=models.SET_NULL)
    selected_menu = models.ForeignKey(Menu, null=True, blank=True, on_delete=models.SET_NULL)
    selected_items = models.JSONField(default=list)  # Store selected menu items
    customer_info = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)




class OrderItem(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    
    def __str__(self):
        return f"{self.menu_item.name} x{self.quantity}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('delivered', 'Delivered'),
    ]
    
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=15)
    restaurant = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE, related_name='admin_orders')
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"