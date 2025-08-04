from rest_framework import viewsets, status
from .models import SubscriptionPlan
from rest_framework.response import Response
from .serializers import PlanPaymentSerializer,SubscriptionPlanSerializer,RecentlyOnboardedSerializer, RestaurantTableSerializer
from .permissions import IsSuperUserOrReadOnly
from rest_framework.permissions import IsAuthenticated
from datetime import datetime, timedelta
from .models import MonthlyRestaurantCount, CallRecord, UserActivity, PlanPayment
from subadmin.models import SubAdminProfile
from rest_framework.views import APIView
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Avg
from django.contrib.auth import get_user_model
import uuid
import requests
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view
import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.db.models import Count, Sum, F
from rest_framework.pagination import PageNumberPagination
from django.utils.timezone import now
from django.db.models import Count
from datetime import timedelta
from collections import defaultdict
from django.db.models.functions import TruncDate

User = get_user_model()



class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated, IsSuperUserOrReadOnly]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Successfully deleted"}, status=status.HTTP_200_OK)
    


class RestaurantCountView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUserOrReadOnly]
    def get(self, request, format=None):
        current_count = SubAdminProfile.objects.count()
        
        # Get current month and previous month
        today = datetime.now().date()
        first_day_current_month = today.replace(day=1)
        first_day_last_month = (first_day_current_month - timedelta(days=1)).replace(day=1)
        
        # Get or create current month record
        current_month_record, _ = MonthlyRestaurantCount.objects.get_or_create(
            month=first_day_current_month,
            defaults={'count': current_count}
        )
        
        # Update if count has changed
        if current_month_record.count != current_count:
            current_month_record.count = current_count
            current_month_record.save()
        
        # Get last month's record
        try:
            last_month_record = MonthlyRestaurantCount.objects.get(month=first_day_last_month)
            last_month_count = last_month_record.count
        except MonthlyRestaurantCount.DoesNotExist:
            last_month_count = current_count  # or 0 if you prefer
        
        # Calculate percentage change
        if last_month_count > 0:
            percentage_change = ((current_count - last_month_count) / last_month_count) * 100
        else:
            percentage_change = 0
        
        data = {
            'total_restaurants': current_count,
            'percentage_change': round(percentage_change, 1),
            'trend': 'up' if percentage_change >= 0 else 'down',
            'last_month_count': last_month_count
        }
        
        return Response(data, status=status.HTTP_200_OK)
    


class CallStatisticsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUserOrReadOnly]
    def get(self, request, format=None):
        today = timezone.now().date()
        first_day_current_month = today.replace(day=1)
        first_day_last_month = (first_day_current_month - timedelta(days=1)).replace(day=1)

        # Use 'created_at' instead of 'timestamp'
        current_month_calls = CallRecord.objects.filter(
            created_at__year=first_day_current_month.year,
            created_at__month=first_day_current_month.month
        ).count()

        last_month_calls = CallRecord.objects.filter(
            created_at__year=first_day_last_month.year,
            created_at__month=first_day_last_month.month
        ).count()

        if last_month_calls > 0:
            percentage_change = ((current_month_calls - last_month_calls) / last_month_calls) * 100
        else:
            percentage_change = 0

        total_calls = CallRecord.objects.count()

        data = {
            'total_calls_handled': total_calls,
            'current_month_calls': current_month_calls,
            'last_month_calls': last_month_calls,
            'percentage_change': round(percentage_change, 1),
            'trend': 'up' if percentage_change >= 0 else 'down'
        }

        return Response(data, status=status.HTTP_200_OK)

    
from django.db.models import F, ExpressionWrapper, DurationField

class CallDurationStatisticsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUserOrReadOnly]
    def get(self, request, format=None):
        today = timezone.now().date()
        first_day_current_month = today.replace(day=1)
        first_day_last_month = (first_day_current_month - timedelta(days=1)).replace(day=1)

        # Current month average duration
        current_month_avg = CallRecord.objects.filter(
            created_at__year=first_day_current_month.year,
            created_at__month=first_day_current_month.month
        ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0

        # Last month average duration
        last_month_avg = CallRecord.objects.filter(
            created_at__year=first_day_last_month.year,
            created_at__month=first_day_last_month.month
        ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0

        # Convert seconds to minutes:seconds format
        def format_duration(seconds):
            if not seconds:
                return "0:00"
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}:{remaining_seconds:02d}"

        # Calculate percentage change
        if last_month_avg > 0:
            percentage_change = ((current_month_avg - last_month_avg) / last_month_avg) * 100
        else:
            percentage_change = 0

        data = {
            'average_duration': format_duration(current_month_avg),
            'average_duration_seconds': round(current_month_avg),
            'last_month_average': format_duration(last_month_avg),
            'last_month_average_seconds': round(last_month_avg),
            'percentage_change': round(percentage_change, 1),
            'trend': 'up' if percentage_change >= 0 else 'down'
        }

        return Response(data, status=status.HTTP_200_OK)

    


class ActiveUserStatisticsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUserOrReadOnly]
    def get(self, request, format=None):
        # Define what "active" means (e.g., logged in within last 30 days)
        active_threshold = timezone.now() - timedelta(days=30)
        
        # Count current active users
        # Option 1 (using last_login):
        current_active_count = User.objects.filter(last_login__gte=active_threshold).count()
        
        # Option 2 (using UserActivity model):
        # current_active_count = UserActivity.objects.filter(
        #     last_activity__gte=active_threshold,
        #     is_active=True
        # ).count()
        
        # Count active users from last month (same period last month)
        last_month_threshold = active_threshold - timedelta(days=30)
        last_month_active_count = User.objects.filter(
            last_login__gte=last_month_threshold,
            last_login__lt=active_threshold
        ).count()
        
        # Calculate percentage change
        if last_month_active_count > 0:
            percentage_change = ((current_active_count - last_month_active_count) / last_month_active_count) * 100
        else:
            percentage_change = 0
        
        data = {
            'active_users': current_active_count,
            'last_month_active_users': last_month_active_count,
            'percentage_change': round(percentage_change, 1),
            'trend': 'up' if percentage_change >= 0 else 'down',
            'threshold_days': 30  # Indicates what "active" means
        }
        
        return Response(data, status=status.HTTP_200_OK)
    


class RestaurantPlanStatsAPIView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUserOrReadOnly]
    def get(self, request):
        # Fetch all paid plan payments
        payments = PlanPayment.objects.filter(payment_status='PAID')

        # Aggregate data
        plan_stats = (
            payments
            .values(plan_type=F('plan__plan_name'))
            .annotate(
                restaurants=Count('subadmin', distinct=True),
                monthly_revenue=Sum('plan__price'),
            )
        )

        # Example: mock growth values manually for now
        growth_mapping = {
            'Entry Level': 8.4,
            'Standard': [12.7, -2.1],  # You may need to combine these
            'Premium': 23.5
        }

        # Build response
        response = []
        for stat in plan_stats:
            growth = growth_mapping.get(stat['plan_type'])
            if isinstance(growth, list):
                # split Standard into two (if needed)
                for g in growth:
                    response.append({
                        "plan_type": stat['plan_type'],
                        "restaurants": stat['restaurants'],
                        "monthly_revenue": float(stat['monthly_revenue']),
                        "growth": g
                    })
            else:
                response.append({
                    "plan_type": stat['plan_type'],
                    "restaurants": stat['restaurants'],
                    "monthly_revenue": float(stat['monthly_revenue']),
                    "growth": growth
                })

        return Response(response)



class RecentlyOnboardedAPIView(APIView):
    def get(self, request):
        # Last 4 onboarded restaurants (you can change the limit)
        profiles = SubAdminProfile.objects.all().order_by('-id')[:4]
        serializer = RecentlyOnboardedSerializer(profiles, many=True)
        return Response(serializer.data)



class RestaurantTableAPIView(APIView):
    def get(self, request):
        queryset = SubAdminProfile.objects.all().order_by('restaurant_name')
        
        paginator = PageNumberPagination()
        paginator.page_size = request.GET.get('page_size', 10)  # optional dynamic size
        page = paginator.paginate_queryset(queryset, request)
        
        serializer = RestaurantTableSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
    

class RestaurantStatsAPIView(APIView):
    def get(self, request):
        today = now().date()
        range_type = request.GET.get('range', 'monthly')  # default: monthly

        if range_type == 'weekly':
            days = 7
        elif range_type == 'yearly':
            days = 365
        else:  # monthly
            days = 30

        start_date = today - timedelta(days=days)

        total = SubAdminProfile.objects.count()
        
        # Count SubAdminProfiles with recent user logins (temporary solution)
        new_this_period = SubAdminProfile.objects.filter(
            user__last_login__gte=start_date
        ).count()

        active_ids = UserActivity.objects.filter(is_active=True).values_list('user_id', flat=True)
        inactive_ids = UserActivity.objects.filter(is_active=False).values_list('user_id', flat=True)

        active = SubAdminProfile.objects.filter(user__id__in=active_ids).count()
        inactive = SubAdminProfile.objects.filter(user__id__in=inactive_ids).count()

        active_percent = round((active / total) * 100, 1) if total else 0
        inactive_percent = round((inactive / total) * 100, 1) if total else 0

        # Chart data
        activities = UserActivity.objects.filter(
            last_activity__date__gte=start_date
        ).annotate(date=TruncDate('last_activity')).values('date', 'is_active').annotate(
            count=Count('id')
        )

        chart_dict = defaultdict(lambda: {"active": 0, "inactive": 0})
        for item in activities:
            key = item["date"].strftime("%Y-%m-%d")
            if item["is_active"]:
                chart_dict[key]["active"] = item["count"]
            else:
                chart_dict[key]["inactive"] = item["count"]

        chart_data = []
        for i in range(days):
            day = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            data = chart_dict.get(day, {"active": 0, "inactive": 0})
            chart_data.append({
                "date": day,
                "active": data["active"],
                "inactive": data["inactive"]
            })

        chart_data.reverse()

        return Response({
            "total_restaurants": total,
            "new_this_period": new_this_period,
            "active_restaurants": active,
            "inactive_restaurants": inactive,
            "active_percent": active_percent,
            "inactive_percent": inactive_percent,
            "chart_data": chart_data
        })


#######---------------------Payment Integration with Stripe---------------------#######

stripe.api_key = settings.STRIPE_SECRET_KEY

class CreateStripeCheckoutSession(APIView):
    def post(self, request):
        serializer = PlanPaymentSerializer(data=request.data)
        if serializer.is_valid():
            plan_payment = serializer.save()  # this may link to SubscriptionPlan through FK like `plan_payment.plan`

            subscription_plan = plan_payment.plan  # assuming a FK from PlanPayment to SubscriptionPlan

            try:
                checkout_session = stripe.checkout.Session.create(
                    payment_method_types=['card'],
                    line_items=[{
                        'price_data': {
                            'currency': 'inr',
                            'unit_amount': int(subscription_plan.price * 100),  # convert to paise
                            'product_data': {
                                'name': subscription_plan.plan_name,
                                'description': subscription_plan.description,
                            },
                        },
                        'quantity': 1,
                    }],
                    mode='payment',
                    metadata={
                        'plan_payment_id': str(plan_payment.id),
                        'plan_name': subscription_plan.plan_name,
                    },
                    success_url=settings.DOMAIN_URL + '/payment-success?session_id={CHECKOUT_SESSION_ID}',
                    cancel_url=settings.DOMAIN_URL + '/payment-cancelled/',
                )

                plan_payment.stripe_checkout_id = checkout_session['id']
                plan_payment.save()

                return Response({'checkout_url': checkout_session.url}, status=200)

            except Exception as e:
                return Response({'error': str(e)}, status=400)

        return Response(serializer.errors, status=400)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    event_type = event['type']
    data = event['data']['object']

    print(f"⚡ Event received: {event_type}")
    print(f"📋 Event data: {data}")

    # Handle checkout.session.completed - This is the primary event for successful payments
    if event_type == 'checkout.session.completed':
        checkout_session_id = data.get('id')
        plan_payment_id = data.get('metadata', {}).get('plan_payment_id')
        payment_intent_id = data.get('payment_intent')
        
        print(f"✅ Checkout completed. Session ID: {checkout_session_id}")
        print(f"📝 Plan Payment ID from metadata: {plan_payment_id}")
        print(f"💳 Payment Intent ID: {payment_intent_id}")
        
        try:
            # Try to find by plan_payment_id from metadata first
            if plan_payment_id:
                payment = PlanPayment.objects.get(id=plan_payment_id)
                print(f"✅ Found payment by plan_payment_id: {plan_payment_id}")
            else:
                # Fallback: try to find by stripe_checkout_id
                payment = PlanPayment.objects.get(stripe_checkout_id=checkout_session_id)
                print(f"✅ Found payment by checkout_session_id: {checkout_session_id}")
            
            # Update payment status
            payment.payment_status = 'PAID'
            payment.stripe_checkout_id = checkout_session_id
            payment.stripe_payment_intent = payment_intent_id
            payment.save()
            
            print(f"✅ Payment {payment.id} marked as PAID")
            
        except PlanPayment.DoesNotExist:
            print(f"❌ No matching PlanPayment found for session {checkout_session_id} or plan_payment_id {plan_payment_id}")
        except Exception as e:
            print(f"❌ Error updating payment: {str(e)}")

    # Handle payment_intent.succeeded as backup
    elif event_type == 'payment_intent.succeeded':
        payment_intent_id = data.get('id')
        print(f"💳 Payment intent succeeded: {payment_intent_id}")
        
        try:
            # Find payment by stripe_payment_intent
            payment = PlanPayment.objects.get(stripe_payment_intent=payment_intent_id)
            payment.payment_status = 'PAID'
            payment.save()
            print(f"✅ Payment {payment.id} marked as PAID via payment_intent")
            
        except PlanPayment.DoesNotExist:
            print(f"❌ No matching PlanPayment found for payment_intent: {payment_intent_id}")
        except Exception as e:
            print(f"❌ Error updating payment via payment_intent: {str(e)}")

    # Handle failed/expired sessions
    elif event_type in ['checkout.session.expired', 'checkout.session.async_payment_failed']:
        checkout_session_id = data.get('id')
        plan_payment_id = data.get('metadata', {}).get('plan_payment_id')
        
        print(f"❌ Checkout failed/expired. Session ID: {checkout_session_id}")
        
        try:
            if plan_payment_id:
                payment = PlanPayment.objects.get(id=plan_payment_id)
            else:
                payment = PlanPayment.objects.get(stripe_checkout_id=checkout_session_id)
            
            payment.payment_status = 'FAILED'
            payment.save()
            print(f"❌ Payment {payment.id} marked as FAILED")
            
        except PlanPayment.DoesNotExist:
            print(f"❌ No matching PlanPayment found to mark as FAILED")
        except Exception as e:
            print(f"❌ Error marking payment as failed: {str(e)}")

    else:
        print(f"🔄 Unhandled event type: {event_type}")

    return HttpResponse(status=200)