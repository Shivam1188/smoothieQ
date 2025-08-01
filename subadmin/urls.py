from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessHourViewSet,MenuViewSet, AllRestaurantViewSet, get_menu_by_twilio_number, handle_incoming_call,sending_email,RestaurantLinkListCreateView,RestaurantLinkRetrieveUpdateDestroyView,   SMSFallbackSettingsRetrieveUpdateView, SMSFallbackPreviewView, TodaysCallsAPIView, MissedCallsAPIView, AverageCallDurationAPIView, RecentCallsAPIView


router = DefaultRouter()
router.register(r'business-hours', BusinessHourViewSet, basename='business-hour')
router.register(r'menu', MenuViewSet, basename='menu')
router.register(r'restaurants', AllRestaurantViewSet, basename='restaurant')



urlpatterns = [
     path('', include(router.urls)),
     path('get-menu-by-twilio/', get_menu_by_twilio_number, name='get_menu_by_twilio'),
     path('start-vapi-call/', handle_incoming_call, name='start_vapi_call'),
     path('trigger-email/', sending_email),
     path('links/', RestaurantLinkListCreateView.as_view(), name='restaurant-link-list-create'),
     path('links/<int:pk>/', RestaurantLinkRetrieveUpdateDestroyView.as_view(), name='restaurant-link-detail'),
     path('sms-fallback/', SMSFallbackSettingsRetrieveUpdateView.as_view(), name='sms-fallback-settings'),
     path('sms-fallback/preview/', SMSFallbackPreviewView.as_view(), name='sms-fallback-preview'),
     path('todays-calls/', TodaysCallsAPIView.as_view(), name='todays-calls'),
     path('missed-calls/', MissedCallsAPIView.as_view(), name='missed-calls'),
     path('average-duration/', AverageCallDurationAPIView.as_view(), name='average-call-duration'),
     path('recent-calls/', RecentCallsAPIView.as_view(), name='recent-calls'),
]

