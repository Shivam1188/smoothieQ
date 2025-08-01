from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import viewsets
from .models import BusinessHour, Menu, RestaurantLink, SMSFallbackSettings
from django.core.mail import send_mail
from .serializers import BusinessHourSerializer,MenuSerializer, SubAdminProfileSerializer, PhoneTriggerSerializer, RestaurantLinkSerializer, SMSFallbackSettingsSerializer
from rest_framework import permissions, status
from authentication.models import SubAdminProfile
from superadmin.permissions import IsSuperUserOrReadOnly
from superadmin.models import CallRecord
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
import requests
from rest_framework import generics, permissions
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Avg



class BusinessHourViewSet(viewsets.ModelViewSet):
    queryset = BusinessHour.objects.all()
    serializer_class = BusinessHourSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        subadmin_id = self.request.query_params.get('subadmin_id')
        if subadmin_id:
            return self.queryset.filter(subadmin_profile__id=subadmin_id)
        return self.queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": "Business hour deleted successfully."},
            status=status.HTTP_200_OK
        )


class MenuViewSet(viewsets.ModelViewSet):
    queryset = Menu.objects.all()
    serializer_class = MenuSerializer
    permission_classes = [permissions.IsAuthenticated]



class AllRestaurantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SubAdminProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Superadmin check (based on role)
        if user.role == 'admin':
            return SubAdminProfile.objects.all()

        # Subadmin check: has SubAdminProfile
        elif hasattr(user, 'subadmin_profile'):
            return SubAdminProfile.objects.filter(user=user)

        # All other roles (e.g. users) get nothing
        return SubAdminProfile.objects.none()
    

@api_view(['POST'])
def get_menu_by_twilio_number(request):
    print("Request data:", request.data)
    print("Request headers:", dict(request.headers))

    # Step 1: Extract Twilio number (callee number)
    twilio_number = (
        request.data.get('to') or
        request.POST.get('to') or
        request.data.get('callee', {}).get('phoneNumber') or
        request.headers.get('X-Vapi-Call-Phone-Number-To') or
        request.headers.get('To') or
        request.data.get('call', {}).get('phoneNumberTo')
    )

    # Step 2: Fallbacks for older/alternate keys
    if not twilio_number or str(twilio_number).startswith("{{"):
        twilio_number = (
            request.headers.get('X-Twilio-To') or
            request.data.get('phoneNumber') or
            request.data.get('restaurant_phone') or
            request.data.get('number') or
            request.data.get('from') or
            request.data.get('caller')
        )

    print("Final phone number extracted:", twilio_number)

    if not twilio_number:
        return Response({'error': 'Missing phone number in payload.'}, status=400)

    # Step 3: Normalize the phone number
    normalized_number = ''.join(filter(str.isdigit, twilio_number))

    phone_variations = [
        f"+{normalized_number}",
        normalized_number.lstrip('91'),  # Remove India code
        f"+91{normalized_number}" if not normalized_number.startswith('91') else f"+{normalized_number}",
        f"+1{normalized_number}" if not normalized_number.startswith('1') else f"+{normalized_number}"
    ]

    # Step 4: Match to SubAdmin by phone
    subadmin = None
    for phone in phone_variations:
        try:
            subadmin = SubAdminProfile.objects.get(phone_number=phone)
            break
        except SubAdminProfile.DoesNotExist:
            continue

    if not subadmin:
        return Response({
            'error': f'No restaurant found for phone number: {twilio_number}',
            'tried_variations': phone_variations
        }, status=404)

    # Step 5: Get active menu
    active_menus = Menu.objects.filter(subadmin_profile=subadmin, is_active=True)
    if not active_menus.exists():
        return Response({'error': 'No active menu found for this restaurant.'}, status=404)

    menu_list = [
        {
            "name": menu.name,
            "description": menu.description
        }
        for menu in active_menus
    ]

    return Response({
        "restaurant_name": subadmin.restaurant_name,
        "phone_number": twilio_number,
        "menus": menu_list
    })


@api_view(['POST'])
def handle_incoming_call(request):
    twilio_number = request.data.get('to') or request.data.get('callee', {}).get('phoneNumber')
    caller = request.data.get('from') or request.data.get('caller', {}).get('phoneNumber')
    print(caller, "======here is caller ================")

    if not twilio_number or not caller:
        return Response({"error": "Missing 'to' or 'from' number"}, status=400)

    # Step 1: Call local menu API
    menu_response = requests.post(
        "https://3e33db4654fa.ngrok-free.app/api/subadmin/get-menu-by-twilio/",
        json={"to": twilio_number},
        headers={"Content-Type": "application/json"}
    )

    if menu_response.status_code != 200:
        print(f"Menu API Error: {menu_response.status_code} - {menu_response.text}")
        return Response({
            "error": "Failed to get menu",
            "details": menu_response.text
        }, status=500)

    menu_data = menu_response.json()
    print(menu_data, "=====menu data ======")

    # Step 2: Trigger Vapi Assistant - Fixed endpoint and payload
    vapi_payload = {
        "assistant": {
            "model": {
                "provider": "openai",
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": f"You are a helpful restaurant assistant for {menu_data.get('restaurant_name', 'our restaurant')}. Here are our available menus: {menu_data.get('menus', [])}"
                    }
                ]
            },
            "voice": {
                "provider": "11labs",
                "voiceId": "21m00Tcm4TlvDq8ikWAM"  # Replace with your preferred voice ID
            }
        },
        "phoneNumberId": twilio_number,  # Your Vapi phone number ID
        "customer": {
            "number": caller
        }
    }

    # Alternative payload structure if you're using a pre-configured assistant
    # vapi_payload = {
    #     "assistantId": "your-assistant-id-here",  # Replace with your assistant ID
    #     "phoneNumberId": "your-phone-number-id",  # Replace with your Vapi phone number ID
    #     "customer": {
    #         "number": caller
    #     },
    #     "assistantOverrides": {
    #         "variableValues": {
    #             "all_restaurant": menu_data
    #         }
    #     }
    # }

    try:
        vapi_response = requests.post(
            "https://api.vapi.ai/call",  # Try this endpoint instead
            headers={
                "Authorization": f"Bearer {VAPI_API_KEY}",
                "Content-Type": "application/json"
            },
            json=vapi_payload,
            timeout=30  # Add timeout
        )
        
        print(f"Vapi Response Status: {vapi_response.status_code}")
        print(f"Vapi Response: {vapi_response.text}")
        
        if vapi_response.status_code not in [200, 201]:
            # If first endpoint fails, try the alternative
            vapi_response_alt = requests.post(
                "https://api.vapi.ai/v1/call",  # Alternative endpoint
                headers={
                    "Authorization": f"Bearer {VAPI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=vapi_payload,
                timeout=30
            )
            
            print(f"Alternative Vapi Response Status: {vapi_response_alt.status_code}")
            print(f"Alternative Vapi Response: {vapi_response_alt.text}")
            
            if vapi_response_alt.status_code in [200, 201]:
                vapi_response = vapi_response_alt
            else:
                raise requests.RequestException(f"Both endpoints failed: {vapi_response.status_code}, {vapi_response_alt.status_code}")

    except requests.RequestException as e:
        print(f"Vapi API Request Error: {str(e)}")
        return Response({
            "error": "Vapi call failed",
            "details": str(e)
        }, status=500)

    if vapi_response.status_code not in [200, 201]:
        print(f"Vapi API Error: {vapi_response.status_code} - {vapi_response.text}")
        return Response({
            "error": "Vapi call failed",
            "details": vapi_response.text,
            "status_code": vapi_response.status_code
        }, status=500)

    return Response({
        "status": "Vapi assistant started successfully",
        "data": vapi_response.json(),
        "menu_data": menu_data
    })


# @api_view(['POST'])
# def trigger_email_by_phone(request):
#     serializer = PhoneTriggerSerializer(data=request.data)
    
#     if serializer.is_valid():
#         phone_number = serializer.validated_data['phone_number']
#         print("Received phone number:", phone_number)

#         try:
#             subadmin = SubAdminProfile.objects.get(phone_number=phone_number)
#             print("Found SubAdmin:", subadmin.email_address)
#         except SubAdminProfile.DoesNotExist:
#             print("No subadmin found for phone:", phone_number)
#             return Response({'error': 'Phone number not found.'}, status=status.HTTP_404_NOT_FOUND)

#         try:
#             send_mail(
#                 subject='Trigger Notification',
#                 message='This is an automated email triggered by your phone number.',
#                 from_email='testampli2023@gmail.com',
#                 recipient_list=['sonu@yopmail.com'],
#                 fail_silently=False,
#             )
#             print("Email sent successfully.")
#         except Exception as e:
#             print("Error while sending email:", str(e))
#             return Response({"error": f"Email failed: {str(e)}"}, status=500)

#         return Response({'message': f'Email sent to {subadmin.email_address}'}, status=200)

#     print("Serializer invalid:", serializer.errors)
#     return Response(serializer.errors, status=400)


@api_view(['POST'])
def sending_email(request):
    phone_number = request.data.get('phone_number')
    order = request.data.get('order')

    try:
        subadmin = SubAdminProfile.objects.get(phone_number=phone_number)
        send_mail(
            subject='New Order Received',
            message=f"Order Details:\n\n{order}",
            from_email='testampli2023@gmail.com',
            recipient_list=['sonu@yopmail.com'],
            fail_silently=False,
        )
        return Response({'message': 'Order email sent successfully.'})
    except SubAdminProfile.DoesNotExist:
        return Response({'error': 'Subadmin not found for this phone.'}, status=404)
    except Exception as e:
        return Response({'error': f'Failed to send email: {str(e)}'}, status=500)







class RestaurantLinkListCreateView(generics.ListCreateAPIView):
    serializer_class = RestaurantLinkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return links for the authenticated user's restaurant
        return RestaurantLink.objects.filter(
            restaurant=self.request.user.subadmin_profile
        ).order_by('link_type', 'provider')

    def perform_create(self, serializer):
        # Automatically associate with the user's restaurant
        serializer.save(restaurant=self.request.user.subadmin_profile)

class RestaurantLinkRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RestaurantLinkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only allow operations on the authenticated user's restaurant links
        return RestaurantLink.objects.filter(
            restaurant=self.request.user.subadmin_profile
        )

    def get_object(self):
        queryset = self.get_queryset()
        obj = get_object_or_404(queryset, pk=self.kwargs['pk'])
        return obj
    

class SMSFallbackSettingsRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = SMSFallbackSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Get or create settings for the user's restaurant
        restaurant = self.request.user.subadmin_profile
        obj, created = SMSFallbackSettings.objects.get_or_create(
            restaurant=restaurant,
            defaults={
                'message': SMSFallbackSettings._meta.get_field('message').default
            }
        )
        return obj

class SMSFallbackPreviewView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SMSFallbackSettingsSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        restaurant = request.user.subadmin_profile
        preview_message = serializer.validated_data['message'].format(
            restaurant_name=restaurant.restaurant_name,
            phone_number=restaurant.phone_number,
            website_url=restaurant.website_url or "our website"
        )
        
        return Response({
            'preview': preview_message,
            'character_count': len(preview_message)
        })
    



####======================for Subadmin Dashboard========================####


class TodaysCallsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            subadmin = SubAdminProfile.objects.get(user=user)
        except SubAdminProfile.DoesNotExist:
            return Response({'error': 'SubAdmin profile not found.'}, status=404)

        today = now().date()
        yesterday = today - timedelta(days=1)

        # Today's and yesterday's call counts
        todays_calls = CallRecord.objects.filter(
            restaurant=subadmin,
            created_at__date=today
        ).count()

        yesterdays_calls = CallRecord.objects.filter(
            restaurant=subadmin,
            created_at__date=yesterday
        ).count()

        if yesterdays_calls > 0:
            percentage_change = ((todays_calls - yesterdays_calls) / yesterdays_calls) * 100
        else:
            percentage_change = 100 if todays_calls > 0 else 0

        return Response({
            "todays_calls": todays_calls,
            "percentage_change": round(percentage_change, 2)
        })
    


class MissedCallsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            subadmin = SubAdminProfile.objects.get(user=user)
        except SubAdminProfile.DoesNotExist:
            return Response({'error': 'SubAdmin profile not found.'}, status=404)

        today = now().date()
        yesterday = today - timedelta(days=1)

        # Missed = status='failed'
        todays_missed = CallRecord.objects.filter(
            restaurant=subadmin,
            created_at__date=today,
            status='failed'
        ).count()

        yesterdays_missed = CallRecord.objects.filter(
            restaurant=subadmin,
            created_at__date=yesterday,
            status='failed'
        ).count()

        if yesterdays_missed > 0:
            percentage_change = ((todays_missed - yesterdays_missed) / yesterdays_missed) * 100
        else:
            percentage_change = 100 if todays_missed > 0 else 0

        return Response({
            "missed_calls": todays_missed,
            "percentage_change": round(percentage_change, 2)
        })
    


class AverageCallDurationAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            subadmin = SubAdminProfile.objects.get(user=user)
        except SubAdminProfile.DoesNotExist:
            return Response({'error': 'SubAdmin profile not found.'}, status=404)

        today = now().date()
        yesterday = today - timedelta(days=1)

        # Get average durations in seconds
        today_avg = CallRecord.objects.filter(
            restaurant=subadmin,
            created_at__date=today,
            duration__isnull=False
        ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0

        yesterday_avg = CallRecord.objects.filter(
            restaurant=subadmin,
            created_at__date=yesterday,
            duration__isnull=False
        ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0

        # Percentage change
        if yesterday_avg > 0:
            percentage_change = ((today_avg - yesterday_avg) / yesterday_avg) * 100
        else:
            percentage_change = 0 if today_avg == 0 else 100

        # Format duration as mm:ss
        def format_duration(seconds):
            minutes = int(seconds) // 60
            sec = int(seconds) % 60
            return f"{minutes}:{sec:02}"

        return Response({
            "average_duration": format_duration(today_avg),
            "percentage_change": round(percentage_change, 2)
        })
    


class RecentCallsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            subadmin = SubAdminProfile.objects.get(user=user)
        except SubAdminProfile.DoesNotExist:
            return Response({'error': 'SubAdmin profile not found.'}, status=404)

        recent_calls = CallRecord.objects.filter(
            restaurant=subadmin
        ).order_by('-created_at')[:4]

        data = []
        for call in recent_calls:
            data.append({
                "call_sid": call.call_sid,
                "status": call.status,
                "duration": call.duration,
                "caller_number": call.caller_number,  # <-- included here
                "created_at": call.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        return Response({"recent_calls": data})