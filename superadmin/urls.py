from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SubscriptionPlanViewSet, RestaurantCountView, CallStatisticsView, CallDurationStatisticsView, ActiveUserStatisticsView, CreateStripeCheckoutSession, stripe_webhook, RestaurantPlanStatsAPIView, RecentlyOnboardedAPIView, RestaurantTableAPIView,RestaurantStatisticsView, EarningsView, PlanDistributionView, PlanStatsAPIView, SubAdminCallRecordFilterView

router = DefaultRouter()
router.register(r'admin-plans', SubscriptionPlanViewSet, basename='adminplan')


urlpatterns = [
    path('', include(router.urls)),
    path('restaurant-count/', RestaurantCountView.as_view(), name='restaurant-count'),
    path('call-statistics/', CallStatisticsView.as_view(), name='call-statistics'),
    path('call-duration-statistics/', CallDurationStatisticsView.as_view(), name='call-duration-statistics'),
    path('active-user-statistics/', ActiveUserStatisticsView.as_view(), name='active-user-statistics'),
    path('restaurant-plan-stats/', RestaurantPlanStatsAPIView.as_view(), name='restaurant-plan-stats'),
    path('recently-onboarded/', RecentlyOnboardedAPIView.as_view(), name='recently-onboarded'),
    path('restaurant-table/', RestaurantTableAPIView.as_view(), name='restaurant-table'),
    path('restaurant-statistics/', RestaurantStatisticsView.as_view(), name='restaurant-statistics'),
    path('create-stripe-session/', CreateStripeCheckoutSession.as_view()),
    path('stripe-webhook/', stripe_webhook),
    path('earnings/<str:period_type>/', EarningsView.as_view(), name='earnings'),
    path('plan-distribution/', PlanDistributionView.as_view(), name='plan-distribution'),
    path('plan-stats/', PlanStatsAPIView.as_view(), name='plan-stats'),
    path('<int:subadmin_id>/call-records/', SubAdminCallRecordFilterView.as_view(), name='subadmin-call-records'),
]