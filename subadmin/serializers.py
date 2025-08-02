from rest_framework import serializers
from .models import BusinessHour, Menu, RestaurantLink, SMSFallbackSettings
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
            'menu',         # accept menu id in POST/PUT
            'menu_name',    # show menu name in GET
        ]
  

class MenuSerializer(serializers.ModelSerializer):
    class Meta:
        model = Menu
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
    class Meta:
        model = RestaurantLink
        fields = ['id', 'link_type', 'provider', 'url', 'is_verified', 'last_verified', 'created_at']
        read_only_fields = ['is_verified', 'last_verified', 'created_at']

    def validate(self, data):
        # Ensure the restaurant exists and belongs to the requesting user
        request = self.context.get('request')
        if request and hasattr(request.user, 'subadmin_profile'):
            data['restaurant'] = request.user.subadmin_profile
        else:
            raise serializers.ValidationError("User is not associated with a restaurant")
        return data
    


class SMSFallbackSettingsSerializer(serializers.ModelSerializer):
    processed_message = serializers.SerializerMethodField()
    
    class Meta:
        model = SMSFallbackSettings
        fields = ['id', 'message', 'processed_message', 'is_active', 'last_updated']
        read_only_fields = ['id', 'processed_message', 'last_updated']

    def get_processed_message(self, obj):
        return obj.get_processed_message()

    def validate(self, data):
        # Ensure required variables are present
        required_vars = ['{restaurant_name}', '{phone_number}']
        message = data.get('message', self.instance.message if self.instance else '')
        
        for var in required_vars:
            if var not in message:
                raise serializers.ValidationError(
                    f"Message must include {var} variable"
                )
        return data
