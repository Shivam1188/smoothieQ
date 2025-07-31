from django.db import models
from subadmin.models import SubAdminProfile
# Create your models here.


class Reservation(models.Model):
    restaurant = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE)
    date = models.CharField(max_length=50)
    time = models.CharField(max_length=50)
    party_size = models.IntegerField()
    customer_phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

class Order(models.Model):
    restaurant = models.ForeignKey(SubAdminProfile, on_delete=models.CASCADE)
    item_name = models.CharField(max_length=100)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    customer_phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)