import openai
from django.conf import settings
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from twilio.twiml.voice_response import VoiceResponse, Gather
from rest_framework.parsers import FormParser
from twilio.rest import Client
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
from fuzzywuzzy import fuzz
import urllib.parse
from datetime import datetime, timedelta
from authentication.models import SubAdminProfile
from subadmin.models import Menu, BusinessHour, UserSession, RestaurantLink, Order, OrderItem, MenuItem, SMSFallbackSettings
from rest_framework.decorators import api_view
from django.core.mail import send_mail
import re
from .utils import send_sms, format_business_hours, get_current_day, clean_phone_number, is_plan_active
from django.views import View
import json
import uuid
from django.http import JsonResponse



# Set up logging
logger = logging.getLogger(__name__)

# Set your OpenAI key
openai.api_key = settings.OPENAI_API_KEY
SESSION_CONTEXT = {}


class MakeCallView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        to_number = request.data.get('to')
        if not to_number:
            return Response({"error": "Missing 'to' number"}, status=400)

        try:
            account_sid = settings.TWILIO_ACCOUNT_SID
            auth_token = settings.TWILIO_AUTH_TOKEN
            from_number = settings.TWILIO_PHONE_NUMBER  

            client = Client(account_sid, auth_token)
            voice_url = request.build_absolute_uri(reverse('voice-assistant'))

            call = client.calls.create(
                to=to_number,
                from_=from_number,
                url=voice_url
            )

            logger.info(f"Call initiated to {to_number}, CallSid: {call.sid}")
            return Response({"message": "Call initiated", "call_sid": call.sid})

        except Exception as e:
            logger.error(f"Error making call: {str(e)}")
            return Response({"error": str(e)}, status=500)



@method_decorator(csrf_exempt, name='dispatch')
class VoiceAssistantView(View):
    
    def get(self, request):
        """Handle Twilio webhook GET requests (initial call setup)"""
        try:
            call_sid = request.GET.get('CallSid')
            from_number = request.GET.get('From')
            to_number = request.GET.get('To')
            call_status = request.GET.get('CallStatus')
            
            response = VoiceResponse()
            
            if call_status == 'in-progress':
                restaurant = self.get_restaurant_by_phone(to_number)
                
                if restaurant:
                    if not is_plan_active(restaurant):
                        response.say(self.get_plan_expired_message(restaurant))
                        response.hangup()
                        return HttpResponse(str(response), content_type='application/xml')
                    
                    greeting = self.get_welcome_message(restaurant)
                    
                    gather = response.gather(
                        input='speech dtmf',
                        timeout=10,
                        speech_timeout='auto',
                        action=f'/api/twilio_bot/voice-assistant/',
                        method='POST'
                    )
                    gather.say(greeting)
                    
                    response.say("I didn't receive any input. Please try again.")
                    response.redirect('/api/twilio_bot/voice-assistant/')
                else:
                    response.say("Sorry, restaurant information is not available. Please try again later.")
            
            return HttpResponse(str(response), content_type='application/xml')
            
        except Exception as e:
            logger.error(f"GET request error: {e}")
            response = VoiceResponse()
            response.say("Sorry, there was an error. Please try again later.")
            return HttpResponse(str(response), content_type='application/xml')
    
    def post(self, request):
        """Handle Twilio webhook POST requests (user input processing)"""
        try:
            call_sid = request.POST.get('CallSid')
            speech_result = request.POST.get('SpeechResult', '')
            digits = request.POST.get('Digits', '')
            from_number = request.POST.get('From')
            to_number = request.POST.get('To')
            
            user_input = speech_result or digits
            
            # Clean phone number properly
            clean_caller_phone = clean_phone_number(from_number)
            caller_phone_digits = re.sub(r'\D', '', clean_caller_phone)[-10:] if clean_caller_phone else 'Unknown'
            
            session, created = UserSession.objects.get_or_create(
                session_id=call_sid,
                defaults={
                    'current_step': 'welcome',
                    'restaurant': self.get_restaurant_by_phone(to_number),
                    'customer_info': {'phone': caller_phone_digits}
                }
            )
            
            if created and session.restaurant:
                session.customer_info = {
                    'phone': caller_phone_digits,
                    'restaurant_name': session.restaurant.restaurant_name,
                    'restaurant_email': session.restaurant.email_address,
                    'restaurant_phone': session.restaurant.phone_number,
                    'restaurant_address': f"{session.restaurant.address}, {session.restaurant.city}, {session.restaurant.state} {session.restaurant.zip_code}"
                }
                session.save()
            
            response_text = self.process_voice_input(session, user_input)
            
            twiml_response = VoiceResponse()
            
            # Updated to include new steps
            if session.current_step in ['menu_selection', 'item_selection', 'order_confirmation']:
                gather = twiml_response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speech_timeout='auto',
                    action='/api/twilio_bot/voice-assistant/',
                    method='POST'
                )
                gather.say(response_text)
                
                twiml_response.say("I didn't receive any input. Please try again.")
                twiml_response.redirect('/api/twilio_bot/voice-assistant/')
            else:
                twiml_response.say(response_text)
                twiml_response.say("Thank you for calling! Have a great day!")
                twiml_response.hangup()
            
            return HttpResponse(str(twiml_response), content_type='application/xml')
            
        except Exception as e:
            logger.error(f"POST request error: {e}")
            response = VoiceResponse()
            response.say("Sorry, there was an error processing your request. Please try again.")
            return HttpResponse(str(response), content_type='application/xml')
    
    def get_restaurant_by_phone(self, phone_number):
        """Get restaurant by phone number"""
        try:
            clean_phone = clean_phone_number(phone_number)
            digits_only = re.sub(r'\D', '', clean_phone)[-10:] if clean_phone else ''
            
            restaurant = SubAdminProfile.objects.filter(
                phone_number__contains=digits_only
            ).first()
            return restaurant
        except Exception as e:
            logger.error(f"Error finding restaurant by phone {phone_number}: {e}")
            return None
    
    def get_welcome_message(self, restaurant):
        """Get welcome message for restaurant"""
        try:
            current_day = get_current_day()
            today_hours = BusinessHour.objects.filter(
                subadmin_profile=restaurant,
                day=current_day
            ).first()
            
            if today_hours and today_hours.closed_all_day:
                hours_info = "We are closed today"
            elif today_hours:
                hours_info = f"We are open today from {today_hours.opening_time.strftime('%I:%M %p')} to {today_hours.closing_time.strftime('%I:%M %p')}"
            else:
                hours_info = "Please check our website for business hours"
            
            active_menus = Menu.objects.filter(
                subadmin_profile=restaurant,
                is_active=True
            ).count()
            
            return f"""Welcome to {restaurant.restaurant_name}! 
            {hours_info}.
            I can help you place an order today. We have {active_menus} menu categories available.
            Press 1 to continue with your order, or say menu to hear our options."""
        except Exception as e:
            logger.error(f"Error creating welcome message: {e}")
            return f"Welcome to {restaurant.restaurant_name if restaurant else 'our restaurant'}! How can I help you today?"
    
    def process_voice_input(self, session, user_input):
        """Process user voice input based on current step"""
        
        if session.current_step == 'welcome':
            return self.handle_welcome(session, user_input)
        elif session.current_step == 'menu_selection':
            return self.handle_menu_selection(session, user_input)
        elif session.current_step == 'item_selection':  # New step
            return self.handle_item_selection(session, user_input)
        elif session.current_step == 'order_confirmation':
            return self.handle_order_confirmation(session, user_input)
        else:
            return self.handle_welcome(session, user_input)
    
    def handle_welcome(self, session, user_input):
        """Handle welcome step and transition to menu selection"""
        try:
            if not session.restaurant:
                return "Sorry, restaurant information is not available."
            
            if user_input.lower() in ['1', 'one', 'yes', 'menu', 'order']:
                session.current_step = 'menu_selection'
                session.save()
                return self.show_menu_options(session.restaurant)
            else:
                return self.get_welcome_message(session.restaurant)
                
        except Exception as e:
            logger.error(f"Error in handle_welcome: {e}")
            return self.get_fallback_message(session.restaurant.id if session.restaurant else None)
    
    def show_menu_options(self, restaurant):
        """Display available menu categories"""
        try:
            active_menus = Menu.objects.filter(
                subadmin_profile=restaurant,
                is_active=True
            ).order_by('name')
            
            if not active_menus:
                return f"""Sorry, we don't have any active menus available right now. 
                Please call us directly at {restaurant.phone_number} for assistance."""
            
            response = "Here are our available menu categories: "
            
            for index, menu in enumerate(active_menus, 1):
                response += f"Press {index} for {menu.name}. "
                if menu.description:
                    response += f"{menu.description}. "
            
            response += "Which category would you like to order from?"
            
            return response
            
        except Exception as e:
            logger.error(f"Error showing menu options: {e}")
            return "Sorry, there was an error loading our menu. Please try again."
    
    def handle_menu_selection(self, session, user_input):
        """Handle menu category selection - now goes to item selection"""
        try:
            try:
                choice = int(user_input.strip())
            except ValueError:
                word_to_num = {
                    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
                }
                choice = word_to_num.get(user_input.lower().strip(), 0)
            
            active_menus = Menu.objects.filter(
                subadmin_profile=session.restaurant,
                is_active=True
            ).order_by('name')
            
            if choice < 1 or choice > len(active_menus):
                return f"Please choose a valid option between 1 and {len(active_menus)}."
            
            selected_menu = list(active_menus)[choice - 1]
            session.selected_menu = selected_menu
            session.current_step = 'item_selection'  # New step for item selection
            session.save()
            
            return self.show_menu_items(selected_menu)
            
        except Exception as e:
            logger.error(f"Error in handle_menu_selection: {e}")
            return "Please enter a valid number or try again."
    
    def show_menu_items(self, menu):
        """Display items within selected menu category"""
        try:
            menu_items = MenuItem.objects.filter(
                menu=menu,
                is_available=True
            ).order_by('display_order', 'name')
            
            if not menu_items:
                return f"""Sorry, {menu.name} items are not available right now. 
                Press 0 to go back to menu categories or try again later."""
            
            response = f"Great! You selected {menu.name}. Here are the available items: "
            
            for index, item in enumerate(menu_items, 1):
                response += f"Press {index} for {item.name}"
                if item.price:
                    response += f" at {item.price} rupees"
                response += ". "
                if item.description:
                    response += f"{item.description}. "
            
            response += "Press 0 to go back to menu categories. Which item would you like to order?"
            
            return response
            
        except Exception as e:
            logger.error(f"Error showing menu items: {e}")
            return "Sorry, there was an error loading menu items. Please try again."
    
    def handle_item_selection(self, session, user_input):
        """Handle specific menu item selection"""
        try:
            try:
                choice = int(user_input.strip())
            except ValueError:
                word_to_num = {
                    'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
                }
                choice = word_to_num.get(user_input.lower().strip(), -1)
            
            if choice == 0:
                # Go back to menu selection
                session.current_step = 'menu_selection'
                session.selected_menu = None
                session.save()
                return self.show_menu_options(session.restaurant)
            
            menu_items = MenuItem.objects.filter(
                menu=session.selected_menu,
                is_available=True
            ).order_by('display_order', 'name')
            
            if choice < 1 or choice > len(menu_items):
                return f"Please choose a valid option between 1 and {len(menu_items)}, or press 0 to go back."
            
            selected_item = list(menu_items)[choice - 1]
            
            # Store selected item
            selected_items = session.selected_items or []
            selected_items.append({
                'item_id': selected_item.id,
                'name': selected_item.name,
                'price': float(selected_item.price) if selected_item.price else 0,
                'quantity': 1
            })
            session.selected_items = selected_items
            session.current_step = 'order_confirmation'
            session.save()
            
            response = f"""Excellent choice! You've selected {selected_item.name}"""
            if selected_item.price:
                response += f" for {selected_item.price} rupees"
            response += f""".
            
            Order Summary:
            Restaurant: {session.restaurant.restaurant_name}
            Category: {session.selected_menu.name}
            Item: {selected_item.name}"""
            
            if selected_item.price:
                response += f"\nPrice: {selected_item.price} rupees"
            
            response += f"""
            Your phone: {session.customer_info.get('phone', 'Unknown')}
            
            Restaurant Details:
            Address: {session.restaurant.address}, {session.restaurant.city}, {session.restaurant.state}
            Phone: {session.restaurant.phone_number}
            
            Press 1 to confirm and submit your order request.
            Press 2 to cancel and start over.
            
            Note: A staff member will contact you shortly to confirm details and arrange pickup or delivery."""
            
            return response
            
        except Exception as e:
            logger.error(f"Error in handle_item_selection: {e}")
            return "Please enter a valid number or try again."
    
    def handle_order_confirmation(self, session, user_input):
        """Handle final order confirmation"""
        try:
            try:
                choice = int(user_input.strip())
            except ValueError:
                if user_input.lower() in ['yes', 'confirm', 'one']:
                    choice = 1
                elif user_input.lower() in ['no', 'cancel', 'two']:
                    choice = 2
                else:
                    choice = 0
            
            if choice == 1:
                order_result = self.process_order(session)
                session.current_step = 'complete'
                session.save()
                return order_result
                
            elif choice == 2:
                session.current_step = 'welcome'
                session.selected_menu = None
                session.selected_items = []
                session.save()
                return "Order cancelled. " + self.get_welcome_message(session.restaurant)
            
            else:
                return "Please press 1 to confirm order or 2 to cancel."
                
        except Exception as e:
            logger.error(f"Error in handle_order_confirmation: {e}")
            return "Please press 1 to confirm order or 2 to cancel."
    
    def process_order(self, session):
        """Process the final order and send notifications"""
        try:
            customer_info = session.customer_info
            
            # Create main order
            order = Order.objects.create(
                customer_name=f"Customer from {customer_info.get('phone', 'Unknown')}",
                customer_email=session.restaurant.email_address,
                customer_phone=customer_info.get('phone', ''),
                restaurant=session.restaurant,
                menu=session.selected_menu,
                notes=f"Voice order - Items: {', '.join([item['name'] for item in session.selected_items])}"
            )
            
            # Create order items
            for item_data in session.selected_items:
                try:
                    menu_item = MenuItem.objects.get(id=item_data['item_id'])
                    OrderItem.objects.create(
                        order=order,
                        menu_item=menu_item,
                        quantity=item_data.get('quantity', 1)
                    )
                except MenuItem.DoesNotExist:
                    logger.warning(f"MenuItem {item_data['item_id']} not found")
            
            self.send_order_notifications(order)
            
            response = f"""🎉 ORDER SUCCESSFUL! 🎉
            
            Your order #{order.id} has been submitted successfully!
            
            Restaurant: {session.restaurant.restaurant_name}
            Category: {session.selected_menu.name}
            Items ordered: {', '.join([item['name'] for item in session.selected_items])}
            Your Phone: {customer_info.get('phone', 'Unknown')}
            
            Restaurant Contact:
            Address: {session.restaurant.address}, {session.restaurant.city}
            Phone: {session.restaurant.phone_number}
            
            📧 Confirmation email sent to restaurant.
            📱 SMS confirmations sent.
            
            A staff member will call you shortly to confirm details and pricing.
            
            Thank you for choosing {session.restaurant.restaurant_name}!"""
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing order: {e}")
            return self.get_fallback_message(session.restaurant.id if session.restaurant else None)
    
    def send_order_notifications(self, order):
        """Send email and SMS notifications with proper phone formatting"""
        try:
            # Get ordered items
            order_items = OrderItem.objects.filter(order=order)
            items_list = ', '.join([f"{item.menu_item.name} x{item.quantity}" for item in order_items])
            
            # Email to restaurant
            restaurant_subject = f"New Voice Order #{order.id}"
            restaurant_message = f"""
            New voice order request received!
            
            Order #{order.id}
            Customer Phone: {order.customer_phone}
            Selected Category: {order.menu.name}
            Items Ordered: {items_list}
            Order Time: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}
            
            Restaurant: {order.restaurant.restaurant_name}
            Address: {order.restaurant.address}, {order.restaurant.city}, {order.restaurant.state}
            
            Please call customer at {order.customer_phone} to confirm details and pricing.
            
            Notes: {order.notes}
            """
            
            send_mail(
                restaurant_subject,
                restaurant_message,
                settings.DEFAULT_FROM_EMAIL,
                [order.restaurant.email_address],
                fail_silently=True
            )
            
            # SMS notifications with proper formatting
            customer_sms = f"""🍽️ {order.restaurant.restaurant_name}

Order #{order.id} confirmed!

Items: {items_list}

We'll call you shortly at {order.customer_phone} to confirm details.

Restaurant: {order.restaurant.address}, {order.restaurant.city}
Phone: {order.restaurant.phone_number}

Thank you!"""
            
            restaurant_sms = f"""📋 NEW ORDER ALERT

Order #{order.id}
Customer: {order.customer_phone}
Items: {items_list}
Time: {order.created_at.strftime('%H:%M')}

Please call to confirm."""
            
            # Send SMS with proper phone formatting
            customer_sms_success = send_sms(order.customer_phone, customer_sms)
            restaurant_sms_success = send_sms(order.restaurant.phone_number, restaurant_sms)
            
            if customer_sms_success:
                logger.info(f"Customer SMS sent successfully for order #{order.id}")
            else:
                logger.error(f"Failed to send customer SMS for order #{order.id}")
                
            if restaurant_sms_success:
                logger.info(f"Restaurant SMS sent successfully for order #{order.id}")
            else:
                logger.error(f"Failed to send restaurant SMS for order #{order.id}")
            
        except Exception as e:
            logger.error(f"Notification error for order #{order.id}: {e}")
    
    # Keep your existing methods (get_fallback_message, etc.)
    def get_fallback_message(self, restaurant_id):
        """Get SMS fallback message if system fails"""
        try:
            if restaurant_id:
                restaurant = SubAdminProfile.objects.get(id=restaurant_id)
                fallback_settings = getattr(restaurant, 'sms_fallback_settings', None)
                if fallback_settings and fallback_settings.is_active:
                    return fallback_settings.get_processed_message()
            
            return "I'm sorry, there was an error processing your request. Please try again or contact the restaurant directly."
            
        except Exception as e:
            logger.error(f"Error getting fallback message: {e}")
            return "I'm sorry, there was an error processing your request. Please try again."


# Debug view to monitor sessions
class DebugView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        session_details = {}
        for call_sid, value in SESSION_CONTEXT.items():
            session_details[call_sid] = {
                'restaurant': value.get('restaurant_data', {}).get('restaurant_name'),
                'current_flow': value.get('current_flow'),
                'reservation_details': value.get('reservation_details', {}),
                'last_messages': value.get("messages", [])[-2:] if value.get("messages") else []
            }
        return Response({
            'active_sessions': len(SESSION_CONTEXT),
            'sessions': session_details
        })


@api_view(['POST'])
def get_menu_by_twilio_number(request):
    """Endpoint to get menu by Twilio number"""
    twilio_number = (
        request.data.get('to') or
        request.POST.get('to') or
        request.data.get('callee', {}).get('phoneNumber') or
        request.headers.get('X-Vapi-Call-Phone-Number-To') or
        request.headers.get('To') or
        request.data.get('call', {}).get('phoneNumberTo')
    )
    
    if not twilio_number or str(twilio_number).startswith("{{"):
        twilio_number = (
            request.headers.get('X-Twilio-To') or
            request.data.get('phoneNumber') or
            request.data.get('restaurant_phone') or
            request.data.get('number') or
            request.data.get('from') or
            request.data.get('caller')
        )
        
    if not twilio_number:
        return Response({'error': 'Missing phone number in payload.'}, status=400)
        
    # Normalize the phone number
    normalized_number = ''.join(filter(str.isdigit, twilio_number))
    phone_variations = [
        f"+{normalized_number}",
        normalized_number.lstrip('91'),  # Remove India code
        f"+91{normalized_number}" if not normalized_number.startswith('91') else f"+{normalized_number}",
        f"+1{normalized_number}" if not normalized_number.startswith('1') else f"+{normalized_number}"
    ]
    
    # Match to SubAdmin by phone
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
        
    # Get active menu
    active_menus = Menu.objects.filter(subadmin_profile=subadmin, is_active=True)
    if not active_menus.exists():
        return Response({'error': 'No active menu found for this restaurant.'}, status=404)
        
    menu_list = [
        {
            "name": menu.name,
            "description": menu.description,
            "is_special": getattr(menu, 'is_special', False),
            "price": getattr(menu, 'price', '')
        }
        for menu in active_menus
    ]
    
    return Response({
        "restaurant_name": subadmin.restaurant_name,
        "phone_number": twilio_number,
        "menus": menu_list,
        "email": subadmin.email_address,
        "address": subadmin.address,
        "website": subadmin.website_url
    })