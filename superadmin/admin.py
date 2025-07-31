from django.contrib import admin
from .models import MonthlyRestaurantCount, CallRecord, UserActivity, PlanPayment, SubscriptionPlan


class MonthlyRestaurantCountAdmin(admin.ModelAdmin):
    list_display = ('month', 'count')
    search_fields = ('month',)
    list_filter = ('month',)

admin.site.register(MonthlyRestaurantCount, MonthlyRestaurantCountAdmin)




class CallRecordAdmin(admin.ModelAdmin):
    list_display = ('restaurant', 'call_sid', 'status', 'created_at', 'updated_at')
    search_fields = ('restaurant__restaurant_name', 'call_sid')
    list_filter = ('status', 'created_at')  

admin.site.register(CallRecord, CallRecordAdmin)


class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_activity', 'is_active')
    search_fields = ('user__email',)
    list_filter = ('is_active', 'last_activity')

admin.site.register(UserActivity, UserActivityAdmin)



class PlanPaymentAdmin(admin.ModelAdmin):
    list_display = ('subadmin', 'plan', 'payment_status', 'created_at')
    search_fields = ('subadmin__restaurant_name', 'plan__plan_type')
    list_filter = ('payment_status', 'created_at')  

admin.site.register(PlanPayment, PlanPaymentAdmin)




class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('plan_name', 'price', 'duration', 'created_at')
    search_fields = ('plan_name',)
    list_filter = ('duration', 'created_at')    

admin.site.register(SubscriptionPlan, SubscriptionPlanAdmin)