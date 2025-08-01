from rest_framework import serializers
from .models import PlanPayment, SubscriptionPlan, CallRecord
from subadmin.models import SubAdminProfile
from datetime import datetime, timedelta
from django.db.models import Count



class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
    

class PlanPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPayment
        fields = '__all__'
        read_only_fields = ['payment_status', 'stripe_checkout_id', 'stripe_payment_intent']



class RecentlyOnboardedSerializer(serializers.ModelSerializer):
    plan_name = serializers.SerializerMethodField()
    onboarded_date = serializers.SerializerMethodField()

    class Meta:
        model = SubAdminProfile
        fields = [
            'restaurant_name', 'profile_image', 'restaurant_description',
            'city', 'state', 'plan_name', 'onboarded_date'
        ]

    def get_plan_name(self, obj):
        payment = PlanPayment.objects.filter(subadmin=obj, payment_status='PAID').order_by('-created_at').first()
        return payment.plan.plan_name if payment else None

    def get_onboarded_date(self, obj):
        payment = PlanPayment.objects.filter(subadmin=obj, payment_status='PAID').order_by('created_at').first()
        return payment.created_at.date() if payment else None
    


class RestaurantTableSerializer(serializers.ModelSerializer):
    restaurant_id = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    owner_role = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    calls_this_month = serializers.SerializerMethodField()
    growth_percent = serializers.SerializerMethodField()

    class Meta:
        model = SubAdminProfile
        fields = [
            'restaurant_name', 'restaurant_id', 'owner_name', 'owner_role',
            'email_address', 'phone_number', 'plan_name', 'status',
            'calls_this_month', 'growth_percent', 'profile_image'
        ]

    def get_restaurant_id(self, obj):
        return f"RES-{obj.created_at.year}-{obj.id:03d}" if hasattr(obj, 'created_at') else f"RES-XXXX-{obj.id:03d}"

    def get_owner_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    def get_owner_role(self, obj):
        return obj.user.role if hasattr(obj.user, 'role') else "Owner"

    def get_plan_name(self, obj):
        payment = PlanPayment.objects.filter(subadmin=obj, payment_status='PAID').order_by('-created_at').first()
        return payment.plan.plan_name if payment else "No Plan"

    def get_status(self, obj):
        payment = PlanPayment.objects.filter(subadmin=obj).order_by('-created_at').first()
        return "Active" if payment and payment.payment_status == "PAID" else "Inactive"

    def get_calls_this_month(self, obj):
        now = datetime.now()
        return CallRecord.objects.filter(
            restaurant=obj,
            created_at__year=now.year,
            created_at__month=now.month
        ).count()

    def get_growth_percent(self, obj):
        now = datetime.now()
        current_month_calls = CallRecord.objects.filter(
            restaurant=obj,
            created_at__year=now.year,
            created_at__month=now.month
        ).count()
        last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        last_month_calls = CallRecord.objects.filter(
            restaurant=obj,
            created_at__year=last_month.year,
            created_at__month=last_month.month
        ).count()

        if last_month_calls == 0:
            return 100 if current_month_calls > 0 else -100 if current_month_calls == 0 else 0

        growth = ((current_month_calls - last_month_calls) / last_month_calls) * 100
        return round(growth, 2)
    


class RestaurantStatsSerializer(serializers.Serializer):
    total_restaurants = serializers.IntegerField()
    new_this_period = serializers.IntegerField()
    active_restaurants = serializers.IntegerField()
    inactive_restaurants = serializers.IntegerField()
    active_percent = serializers.FloatField()
    inactive_percent = serializers.FloatField()
    chart_data = serializers.ListField(
        child=serializers.DictField(child=serializers.IntegerField())
    )