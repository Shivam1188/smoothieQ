from rest_framework import serializers
from .models import PlanPayment, SubscriptionPlan
from subadmin.models import SubAdminProfile


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'
    

class PlanPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPayment
        fields = '__all__'
        read_only_fields = ['payment_status', 'stripe_checkout_id', 'stripe_payment_intent']



