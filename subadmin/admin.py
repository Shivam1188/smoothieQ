from django.contrib import admin
from .models import  BusinessHour, Menu, RestaurantLink, SMSFallbackSettings, UserSession, Order, OrderItem, MenuItem





@admin.register(BusinessHour)
class BusinessHourAdmin(admin.ModelAdmin):
    list_display = ('subadmin_profile', 'day', 'opening_time', 'closing_time', 'closed_all_day')
    list_filter = ('subadmin_profile', 'day', 'closed_all_day')



@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('id', 'subadmin_profile', 'name', 'is_active', 'created_at')
    list_filter = ('subadmin_profile', 'is_active')
    search_fields = ('name', 'subadmin_profile__restaurant_name')
    ordering = ('id',)



class RestaurantLinkAdmin(admin.ModelAdmin):
    list_display = ('id', 'restaurant_name', 'direct_ordering_link')
    search_fields = ('restaurant_name__restaurant_name',)
admin.site.register(RestaurantLink, RestaurantLinkAdmin)




class SMSFallbackSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'is_active', 'last_updated')
    search_fields = ('message',)


admin.site.register(SMSFallbackSettings, SMSFallbackSettingsAdmin)


class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('id','current_step', 'restaurant', 'created_at', 'updated_at')
    search_fields = ('user__username', 'restaurant__restaurant_name')
    list_filter = ('current_step', 'restaurant')
admin.site.register(UserSession, UserSessionAdmin)

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'restaurant', 'status', 'created_at')
    search_fields = ('user__username', 'restaurant__restaurant_name')
    list_filter = ('status', 'restaurant')
admin.site.register(Order, OrderAdmin)


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'menu_item', 'quantity')
    search_fields = ('order__id', 'menu_item__name')
    list_filter = ('order__restaurant',)    
admin.site.register(OrderItem, OrderItemAdmin)



class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'menu', 'name', 'price', 'is_available')
    search_fields = ('name', 'menu__name')
    list_filter = ('menu__subadmin_profile', 'is_available')   

admin.site.register(MenuItem, MenuItemAdmin)