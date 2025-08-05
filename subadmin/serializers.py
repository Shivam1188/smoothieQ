from rest_framework import serializers
from .models import BusinessHour, Menu, RestaurantLink, SMSFallbackSettings,MenuItem
from authentication.models import SubAdminProfile

class BusinessHourSerializer(serializers.ModelSerializer):
    menu_name = serializers.CharField(source='menu.name', read_only=True)

    class Meta:
        model = BusinessHour
        fields = [
            'id',
            'subadmin_profile',
            'day',
            'opening_time',
            'closing_time',
            'closed_all_day',
            'menu',        
            'menu_name',    
        ]
  

class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
        fields = '__all__'



class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = '__all__'



class SubAdminProfileSerializer(serializers.ModelSerializer):
    menus = MenuSerializer(many=True, read_only=True)
    business_hours = BusinessHourSerializer(many=True, read_only=True)

    class Meta:
        model = SubAdminProfile
        fields = [
            'id', 'restaurant_name', 'profile_image', 'phone_number', 'email_address',
            'address', 'city', 'state', 'zip_code', 'country', 'website_url',
            'restaurant_description', 'menus', 'business_hours'
        ]



class PhoneTriggerSerializer(serializers.Serializer):
    phone_number = serializers.CharField()


class RestaurantLinkSerializer(serializers.ModelSerializer):
    restaurant_name_display = serializers.CharField(source='restaurant_name.restaurant_name', read_only=True)

    class Meta:
        model = RestaurantLink
        fields = '__all__'
    


class SMSFallbackSettingsSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source='restaurant.restaurant_name', read_only=True)
    phone_number = serializers.CharField(source='restaurant.phone_number', read_only=True)
    website_url = serializers.CharField(source='restaurant.website_url', read_only=True)
    processed_message = serializers.SerializerMethodField()

    class Meta:
        model = SMSFallbackSettings
        fields = [
            'id',
            'restaurant',
            'restaurant_name',
            'phone_number',
            'website_url',
            'message',
            'processed_message',
            'is_active',
            'last_updated',
        ]

    def get_processed_message(self, obj):
        return obj.get_processed_message()