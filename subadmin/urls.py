from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessHourViewSet,MenuViewSet, AllRestaurantViewSet, get_menu_by_twilio_number, handle_incoming_call,sending_email,RestaurantLinkViewSet, TodaysCallsAPIView, MissedCallsAPIView, AverageCallDurationAPIView, RecentCallsAPIView, MenuItemViewSet,SMSFallbackSettingsViewSet


router = DefaultRouter()
router.register(r'business-hours', BusinessHourViewSet, basename='business-hour')
router.register(r'menu', MenuViewSet, basename='menu')
router.register(r'menu-items', MenuItemViewSet, basename='menu-items')
router.register(r'restaurants', AllRestaurantViewSet, basename='restaurant')
router.register(r'restaurant-links', RestaurantLinkViewSet, basename='restaurantlink')
router.register(r'sms-fallback-settings', SMSFallbackSettingsViewSet, basename='sms-fallback-settings')



urlpatterns = [
     path('', include(router.urls)),
     path('get-menu-by-twilio/', get_menu_by_twilio_number, name='get_menu_by_twilio'),
     path('start-vapi-call/', handle_incoming_call, name='start_vapi_call'),
     path('trigger-email/', sending_email),
     path('todays-calls/', TodaysCallsAPIView.as_view(), name='todays-calls'),
     path('missed-calls/', MissedCallsAPIView.as_view(), name='missed-calls'),
     path('average-duration/', AverageCallDurationAPIView.as_view(), name='average-call-duration'),
     path('recent-calls/', RecentCallsAPIView.as_view(), name='recent-calls'),
]

