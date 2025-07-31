from rest_framework import serializers
from .models import AdminPlan, PlanPayment, CallRecord
from subadmin.models import SubAdminProfile


class AdminPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminPlan
        fields = '__all__'
    

class PlanPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanPayment
        fields = '__all__'
        read_only_fields = ['payment_status', 'stripe_checkout_id', 'stripe_payment_intent']




class CallRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallRecord
        fields = ['id', 'call_sid', 'status', 'created_at']

class CallStatisticsSerializer(serializers.Serializer):
    today_calls = serializers.IntegerField()
    percentage_change = serializers.FloatField()
    trend_direction = serializers.CharField()