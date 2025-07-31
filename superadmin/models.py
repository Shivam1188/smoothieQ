from django.db import models
from subadmin.models import SubAdminProfile
from django.conf import settings

# Create your models here.


class AdminPlan(models.Model):
    plan_type = models.CharField(max_length=100)
    resturent = models.CharField(max_length=100)
    monthly_revenue = models.CharField(max_length=100)
    growth = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.plan_type} - {self.resturent}"




class SubscriptionPlan(models.Model):
    plan_name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.CharField(max_length=50)  # e.g., 'monthly', 'yearly'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.plan_name



class PlanPayment(models.Model):
    subadmin = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE, related_name='payments')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='payments')
    stripe_checkout_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_payment_intent = models.CharField(max_length=255, null=True, blank=True)
    payment_status = models.CharField(max_length=100, default='PENDING')  # PENDING / PAID / FAILED
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subadmin} - {self.plan} - {self.payment_status}"



class MonthlyRestaurantCount(models.Model):
    month = models.DateField()
    count = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['-month']
        unique_together = ['month']

 

class CallRecord(models.Model):
    STATUS_CHOICES = [
        ('in-progress', 'In Progress'),
        ('completed', 'Completed'),
        ('transferred', 'Transferred'),
        ('failed', 'Failed'),
    ]
    
    restaurant = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE, related_name='call_records')
    call_sid = models.CharField(max_length=34, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in-progress')
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.restaurant.restaurant_name} - {self.call_sid} ({self.status})"


class UserActivity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name_plural = "User Activities"
        indexes = [
            models.Index(fields=['last_activity']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.last_activity}"