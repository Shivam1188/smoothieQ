from rest_framework import viewsets, status
from .models import SubscriptionPlan
from rest_framework.response import Response
from .serializers import PlanPaymentSerializer,SubscriptionPlanSerializer,RecentlyOnboardedSerializer, RestaurantTableSerializer, EarningSerializer, PlanDistributionSerializer,RestaurantStatisticsSerializer
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
import calendar
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from rest_framework.exceptions import PermissionDenied
from rest_framework import generics, filters
from .serializers import CallRecordSerializer
from django_filters.rest_framework import DjangoFilterBackend



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
    



class RestaurantStatisticsView(APIView):
    def get(self, request, format=None):
        # Get query parameters
        period = request.query_params.get('period', 'all')  # 'all', 'weekly', 'monthly', 'yearly'
        
        # Calculate time periods
        now = datetime.now()
        
        # Get base statistics
        total_restaurants = SubAdminProfile.objects.count()
        active_restaurants = SubAdminProfile.objects.filter(user__is_active=True).count()
        inactive_restaurants = total_restaurants - active_restaurants
        
        # Calculate percentages
        active_percentage = (active_restaurants / total_restaurants * 100) if total_restaurants else 0
        inactive_percentage = (inactive_restaurants / total_restaurants * 100) if total_restaurants else 0
        
        # Calculate change this month (new restaurants created this month)
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        change_this_month = SubAdminProfile.objects.filter(
            created_at__gte=this_month_start
        ).count()
        
        # Prepare base stats
        base_stats = {
            'total_restaurants': total_restaurants,
            'active_restaurants': active_restaurants,
            'inactive_restaurants': inactive_restaurants,
            'active_percentage': round(active_percentage, 1),
            'inactive_percentage': round(inactive_percentage, 1),
            'change_this_month': change_this_month,
        }
        
        # Initialize response data
        data = {}
        
        if period == 'all' or period == 'weekly':
            weekly_start = now - timedelta(days=7)
            data['weekly'] = {
                **base_stats,
                'period_start': weekly_start,
                'period_end': now,
            }
        
        if period == 'all' or period == 'monthly':
            monthly_start = now - timedelta(days=30)
            data['monthly'] = {
                **base_stats,
                'period_start': monthly_start,
                'period_end': now,
            }
        
        if period == 'all' or period == 'yearly':
            yearly_start = now - timedelta(days=365)
            data['yearly'] = {
                **base_stats,
                'period_start': yearly_start,
                'period_end': now,
            }
        
        # If a specific period was requested, return only that period
        if period in ['weekly', 'monthly', 'yearly']:
            data = data.get(period, {})
        
        serializer = RestaurantStatisticsSerializer(data, many=False)
        return Response(data, status=status.HTTP_200_OK)


class EarningsView(APIView):
    def get(self, request, period_type):
        # Get all successful payments
        payments = PlanPayment.objects.filter(payment_status='PAID')
        
        if period_type == 'daily':
            data = self._get_daily_earnings(payments)
        elif period_type == 'weekly':
            data = self._get_weekly_earnings(payments)
        elif period_type == 'monthly':
            data = self._get_monthly_earnings(payments)
        else:
            return Response({"error": "Invalid period type"}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = EarningSerializer(data, many=True)
        return Response(serializer.data)
    
    def _get_daily_earnings(self, payments):
        today = datetime.now().date()
        data = []
        
        for i in range(30):
            date = today - timedelta(days=i)
            day_payments = payments.filter(created_at__date=date)
            revenue = sum(payment.plan.price for payment in day_payments)
            
            expense = revenue * Decimal('0.2') if i % 3 != 0 else -revenue * Decimal('0.1')
            
            data.append({
                'period': date.strftime('%A'),
                'revenue': float(revenue),
                'expense': float(expense)
            })
        
        return data[::-1]
    
    def _get_weekly_earnings(self, payments):
        today = datetime.now().date()
        data = []
        
        for i in range(12):
            start_date = today - timedelta(weeks=i+1)
            end_date = today - timedelta(weeks=i)
            week_payments = payments.filter(created_at__date__range=(start_date, end_date))
            revenue = sum(payment.plan.price for payment in week_payments)
            
            expense = revenue * Decimal('0.3') if i % 2 == 0 else -revenue * Decimal('0.15')
            
            data.append({
                'period': f"Week {i+1}",
                'revenue': float(revenue),
                'expense': float(expense)
            })
        
        return data[::-1]
    
    def _get_monthly_earnings(self, payments):
        # Get last 12 months data
        today = datetime.now().date()
        data = []
        
        for i in range(12):
            month = today.month - i - 1
            year = today.year
            if month < 1:
                month += 12
                year -= 1
                
            month_payments = payments.filter(
                created_at__year=year,
                created_at__month=month
            )
            revenue = sum(payment.plan.price for payment in month_payments)
            
            # Convert to float at the end if needed, but keep calculations as Decimal
            expense = revenue * Decimal('0.25') if month % 2 == 0 else -revenue * Decimal('0.1')
            
            data.append({
                'period': calendar.month_name[month],
                'revenue': float(revenue),  # Convert to float for JSON serialization
                'expense': float(expense)  # Convert to float for JSON serialization
            })
        
        return data[::-1]

class PlanDistributionView(APIView):
    def get(self, request):
        # Get count of each plan in use
        active_payments = PlanPayment.objects.filter(payment_status='PAID')
        
        # Group by plan
        plan_counts = defaultdict(int)
        for payment in active_payments:
            plan_counts[payment.plan.plan_name] += 1
        
        data = [{'plan_name': name, 'count': count} for name, count in plan_counts.items()]
        serializer = PlanDistributionSerializer(data, many=True)
        return Response(serializer.data)

class PlanStatsAPIView(APIView):
    def get(self, request):
        data = []

        today = now().date()
        start_of_current_month = today.replace(day=1)
        start_of_last_month = start_of_current_month - relativedelta(months=1)

        plans = SubscriptionPlan.objects.all()

        for plan in plans:
            # Total unique paying restaurants (subadmins)
            restaurants = PlanPayment.objects.filter(
                plan=plan,
                payment_status='PAID'
            ).values('subadmin').distinct().count()

            # Revenue for current month
            current_month_revenue = PlanPayment.objects.filter(
                plan=plan,
                payment_status='PAID',
                created_at__gte=start_of_current_month
            ).aggregate(
                total=Sum(F('plan__price'))
            )['total'] or Decimal('0.0')

            # Revenue for last month
            last_month_revenue = PlanPayment.objects.filter(
                plan=plan,
                payment_status='PAID',
                created_at__gte=start_of_last_month,
                created_at__lt=start_of_current_month
            ).aggregate(
                total=Sum(F('plan__price'))
            )['total'] or Decimal('0.0')

            # Convert Decimal to float for arithmetic
            current = float(current_month_revenue)
            last = float(last_month_revenue)

            # Calculate growth
            if last > 0:
                growth = ((current - last) / last) * 100
            else:
                growth = 0.0 if current == 0 else 100.0

            data.append({
                "plan_type": plan.plan_name,
                "restaurants": restaurants,
                "monthly_revenue": round(current, 2),
                "growth": round(growth, 1)
            })

        return Response(data)
    
from rest_framework.exceptions import NotFound


class SubAdminCallRecordFilterView(generics.ListAPIView):
    serializer_class = CallRecordSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering_fields = ['created_at', 'duration']
    ordering = ['-created_at']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        subadmin_id = self.kwargs.get('subadmin_id')
        time_period = self.request.query_params.get('time_period', None)
        
        try:
            subadmin = SubAdminProfile.objects.get(id=subadmin_id)
        except SubAdminProfile.DoesNotExist:
            raise NotFound("SubAdmin not found")
        
        queryset = CallRecord.objects.filter(restaurant=subadmin)
        
        if time_period:
            now = timezone.now()
            
            if time_period == 'last_30_days':
                start_date = now - timedelta(days=30)
                queryset = queryset.filter(created_at__gte=start_date)
                
            elif time_period == 'last_quarter':
                current_month = now.month
                if current_month in [1, 2, 3]:
                    quarter_start = datetime(now.year - 1, 10, 1)
                elif current_month in [4, 5, 6]:
                    quarter_start = datetime(now.year, 1, 1)
                elif current_month in [7, 8, 9]:
                    quarter_start = datetime(now.year, 4, 1)
                else:
                    quarter_start = datetime(now.year, 7, 1)
                queryset = queryset.filter(created_at__gte=quarter_start)
                
            elif time_period == 'year_to_date':
                year_start = datetime(now.year, 1, 1)
                queryset = queryset.filter(created_at__gte=year_start)
                
        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        
        time_period = request.query_params.get('time_period', None)
        subadmin_id = self.kwargs.get('subadmin_id')
        
        response_data = {
            'subadmin_id': subadmin_id,
            'time_period': time_period or 'all_time',
            'data': serializer.data,
            'summary': self.get_summary_data(queryset, time_period)
        }
        
        return Response(response_data)

    def get_summary_data(self, queryset, time_period):
        total_calls = queryset.count()
        completed_calls = queryset.filter(status='completed').count()
        total_duration = sum(call.duration for call in queryset if call.duration) or 0
        
        return {
            'total_calls': total_calls,
            'completed_calls': completed_calls,
            'completion_rate': round((completed_calls / total_calls * 100), 2) if total_calls else 0,
            'average_duration': round((total_duration / total_calls), 2) if total_calls else 0,
            'total_duration': total_duration,
            'in_progress_calls': queryset.filter(status='in-progress').count(),
            'failed_calls': queryset.filter(status='failed').count(),
            'transferred_calls': queryset.filter(status='transferred').count(),
        }

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