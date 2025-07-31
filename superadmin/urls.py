from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionPlanViewSet, RestaurantCountView, CallStatisticsView, CallDurationStatisticsView, ActiveUserStatisticsView, CreateStripeCheckoutSession, stripe_webhook

router = DefaultRouter()
router.register(r'admin-plans', SubscriptionPlanViewSet, basename='adminplan')


urlpatterns = [
    path('', include(router.urls)),
    path('restaurant-count/', RestaurantCountView.as_view(), name='restaurant-count'),
    path('call-statistics/', CallStatisticsView.as_view(), name='call-statistics'),
    path('call-duration-statistics/', CallDurationStatisticsView.as_view(), name='call-duration-statistics'),
    path('active-user-statistics/', ActiveUserStatisticsView.as_view(), name='active-user-statistics'),
    path('create-stripe-session/', CreateStripeCheckoutSession.as_view()),
    path('stripe-webhook/', stripe_webhook),

]