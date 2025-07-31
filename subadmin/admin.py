from django.contrib import admin
from .models import  BusinessHour, Menu, RestaurantLink, SMSFallbackSettings





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
    list_display = ('id', 'link_type', 'provider', 'url', 'is_verified', 'last_verified', 'created_at')
    list_filter = ('link_type', 'provider', 'is_verified')
    search_fields = ('url', 'provider')
    readonly_fields = ('is_verified', 'last_verified', 'created_at')

admin.site.register(RestaurantLink, RestaurantLinkAdmin)




class SMSFallbackSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'is_active', 'last_updated')
    search_fields = ('message',)


admin.site.register(SMSFallbackSettings, SMSFallbackSettingsAdmin)