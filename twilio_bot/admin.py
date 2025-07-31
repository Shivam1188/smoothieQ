from django.contrib import admin
from .models import Reservation, Order
# Register your models here.


class ReservationAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'date', 'time', 'party_size', 'customer_phone', 'created_at')
    search_fields = ('restaurant__name', 'customer_phone')
    list_filter = ('restaurant', 'date')

    
admin.site.register(Reservation, ReservationAdmin)



class OrderAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'item_name', 'quantity', 'price', 'customer_phone', 'created_at')
    search_fields = ('restaurant__name', 'item_name', 'customer_phone')
    list_filter = ('restaurant', 'created_at')


admin.site.register(Order, OrderAdmin)