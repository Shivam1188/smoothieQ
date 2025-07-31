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
from subadmin.models import Menu, BusinessHour
from rest_framework.decorators import api_view
from django.core.mail import send_mail
from .models import Reservation, Order
import re

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
class VoiceAssistantView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [FormParser]

    def get(self, request, *args, **kwargs):
        """Handle both initial calls, speech input, and DTMF input via GET"""
        call_sid = request.GET.get('CallSid')
        to_number = request.GET.get('To')
        speech_result = request.GET.get('SpeechResult', '').strip()
        digits = request.GET.get('Digits', '').strip()

        if speech_result:
            speech_result = urllib.parse.unquote_plus(speech_result)
        
        logger.info(f"GET - CallSid: {call_sid}, To: {to_number}, Speech: '{speech_result}', Digits: '{digits}'")

        # Initialize session if doesn't exist
        if call_sid not in SESSION_CONTEXT:
            SESSION_CONTEXT[call_sid] = {
                'messages': [],
                'restaurant_data': None,
                'to_number': to_number,
                'current_flow': None,
                'reservation_details': {},
                'order_details': {
                    'items': [],
                    'current_item': None,
                    'state': None  # 'selecting_item', 'getting_quantity', 'getting_instructions', 'confirming'
                },
                'call_record': None
            }
            self._load_restaurant_data(call_sid, to_number)
            self._create_call_record(call_sid, to_number)
            if not speech_result and not digits:
                return self._initial_greeting(request, call_sid)

        # Handle DTMF input
        if digits:
            return self._process_digits(call_sid, digits, request)

        # Handle speech input
        if speech_result:
            return self._process_speech(call_sid, speech_result, request)
        else:
            return self._ask_again(request, call_sid)

    def post(self, request, *args, **kwargs):
        """Handle speech input and DTMF input via POST"""
        call_sid = request.data.get('CallSid')
        to_number = request.data.get('To')
        speech_result = request.data.get('SpeechResult', '').strip()
        digits = request.data.get('Digits', '').strip()
        
        logger.info(f"POST - CallSid: {call_sid}, To: {to_number}, Speech: '{speech_result}', Digits: '{digits}'")

        # Initialize session if doesn't exist
        if call_sid not in SESSION_CONTEXT:
            SESSION_CONTEXT[call_sid] = {
                'messages': [],
                'restaurant_data': None,
                'to_number': to_number,
                'current_flow': None,
                'reservation_details': {},
                'order_details': {
                    'items': [],
                    'current_item': None,
                    'state': None
                },
                'call_record': None
            }
            self._load_restaurant_data(call_sid, to_number)

        if digits:
            return self._process_digits(call_sid, digits, request)
        if speech_result:
            return self._process_speech(call_sid, speech_result, request)
        else:
            return self._ask_again(request, call_sid)

    def _initial_greeting(self, request, call_sid):
        """Initial greeting with main menu options"""
        restaurant_data = SESSION_CONTEXT[call_sid]['restaurant_data']
        restaurant_name = restaurant_data.get('restaurant_name', 'our restaurant') if restaurant_data else 'our restaurant'
        
        response = VoiceResponse()
        response.say(
            f"Thank you for calling {restaurant_name}. "
            "Press 1 to make a reservation, "
            "2 to hear today's specials, "
            "3 to place an order, "
            "4 to speak with our staff, "
            "or 5 for our hours of operation.", 
            voice='alice'
        )
        response.gather(
            input='dtmf',
            timeout=10,
            numDigits=1,
            action=request.build_absolute_uri(),
            method='GET'
        )
        return HttpResponse(str(response), content_type='text/xml')

    def _ask_again(self, request, call_sid):
        """Re-prompt for user input"""
        session = SESSION_CONTEXT[call_sid]
        restaurant_data = session['restaurant_data']
        restaurant_name = restaurant_data.get('restaurant_name', 'our restaurant') if restaurant_data else 'our restaurant'
        
        response = VoiceResponse()
        
        if session['current_flow'] == 'reservation':
            if 'date' not in session['reservation_details']:
                response.say("Sorry, I didn't catch the date. Please say or enter the date for your reservation.", voice='alice')
            elif 'time' not in session['reservation_details']:
                response.say("Sorry, I didn't catch the time. Please say or enter the time for your reservation.", voice='alice')
            elif 'party_size' not in session['reservation_details']:
                response.say("Sorry, I didn't catch your party size. Please say or enter the number of people in your party.", voice='alice')
            else:
                response.say("Sorry, I didn't catch that. Please try again.", voice='alice')
        elif session['current_flow'] == 'order':
            order_state = session['order_details'].get('state')
            if order_state == 'selecting_item':
                response.say("Sorry, I didn't catch the item you want to order. Please say the name of the item.", voice='alice')
            elif order_state == 'getting_quantity':
                response.say("Sorry, I didn't catch the quantity. Please say how many you'd like to order.", voice='alice')
            elif order_state == 'getting_instructions':
                response.say("Sorry, I didn't catch your instructions. Please say any special instructions or say 'no'.", voice='alice')
            else:
                response.say("Sorry, I didn't catch that. Please try again.", voice='alice')
        else:
            response.say(
                f"Sorry, I didn't catch that. For {restaurant_name}, "
                "press 1 for reservations, 2 for specials, 3 for orders, 4 for staff, or 5 for hours.", 
                voice='alice'
            )
        
        response.gather(
            input='speech dtmf',
            timeout=10,
            speechTimeout='auto',
            action=request.build_absolute_uri(),
            method='GET'
        )
        return HttpResponse(str(response), content_type='text/xml')

    def _load_restaurant_data(self, call_sid, to_number):
        """Load restaurant data based on Twilio number"""
        try:
            restaurant = SubAdminProfile.objects.filter(phone_number=to_number).first()
            if not restaurant:
                logger.error(f"No restaurant found for phone number: {to_number}")
                SESSION_CONTEXT[call_sid]['restaurant_data'] = None
                return

            # Get business hours
            business_hours = BusinessHour.objects.filter(subadmin_profile=restaurant)
            hours_list = []
            for bh in business_hours:
                if bh.closed_all_day:
                    hours_list.append(f"{bh.day}: Closed")
                elif bh.opening_time and bh.closing_time:
                    hours_list.append(f"{bh.day}: {bh.opening_time.strftime('%I:%M %p')} to {bh.closing_time.strftime('%I:%M %p')}")

            # Get active menus for specials and orders
            menus = Menu.objects.filter(subadmin_profile=restaurant, is_active=True)
            specials = [menu for menu in menus if getattr(menu, 'is_special', False)]
            menu_items = [menu for menu in menus if not getattr(menu, 'is_special', False)]

            restaurant_data = {
                'restaurant_name': restaurant.restaurant_name,
                'phone_number': restaurant.phone_number,
                'email': restaurant.email_address,
                'address': restaurant.address,
                'website': restaurant.website_url,
                'hours': hours_list,
                'specials': [{
                    'name': special.name,
                    'description': special.description,
                    'price': getattr(special, 'price', 'Price Available on Request')
                } for special in specials],
                'menu_items': [{
                    'name': item.name,
                    'description': item.description,
                    'price': getattr(item, 'price', 'Price Available on Request') if getattr(item, 'price', '') else 'Price Available on Request'
                } for item in menu_items]
            }

            SESSION_CONTEXT[call_sid]['restaurant_data'] = restaurant_data
            logger.info(f"Loaded data for restaurant: {restaurant.restaurant_name}")
            
        except Exception as e:
            logger.error(f"Error loading restaurant data: {str(e)}")
            SESSION_CONTEXT[call_sid]['restaurant_data'] = None

    def _process_digits(self, call_sid, digits, request):
        """Process DTMF input"""
        session = SESSION_CONTEXT[call_sid]
        restaurant_data = session['restaurant_data']
        restaurant_name = restaurant_data.get('restaurant_name', 'our restaurant')
        
        response = VoiceResponse()
        
        if session['current_flow'] == 'reservation':
            return self._handle_reservation_digits(call_sid, digits, request)
        elif session['current_flow'] == 'order':
            return self._handle_order_digits(call_sid, digits, request)
        
        # Main menu options
        if digits == '1':
            # Start reservation flow
            session['current_flow'] = 'reservation'
            session['reservation_details'] = {}
            response.say(
                "Let's make a reservation. Please say or enter the date for your reservation. "
                "For example, say 'today' or 'July 30th'.", 
                voice='alice'
            )
            response.gather(
                input='speech dtmf',
                timeout=10,
                speechTimeout='auto',
                action=request.build_absolute_uri(),
                method='GET'
            )
            
        elif digits == '2':
            # Today's specials
            session['current_flow'] = 'specials'
            specials = restaurant_data.get('specials', [])
            if not specials:
                response.say(f"Sorry, there are no specials available today at {restaurant_name}.", voice='alice')
                response.say(
                    "Press 1 to make a reservation, 3 to place an order, or stay on the line to return to the main menu.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf',
                    timeout=10,
                    numDigits=1,
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            else:
                specials_text = ". ".join([
                    f"{special['name']}. {special['description']}"
                    for special in specials
                ])
                response.say(
                    f"Today's specials at {restaurant_name} are: {specials_text}. "
                    "Press 1 to make a reservation, 3 to place an order, or stay on the line to return to the main menu.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf',
                    timeout=10,
                    numDigits=1,
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
        elif digits == '3':
            # Start order flow
            session['current_flow'] = 'order'
            session['order_details'] = {
                'items': [],
                'current_item': None,
                'state': 'selecting_item'
            }
            menu_items = restaurant_data.get('menu_items', [])
            if not menu_items:
                response.say(f"Sorry, there are no menu items available at {restaurant_name}.", voice='alice')
                response.say(
                    "Press 1 to make a reservation or stay on the line to return to the main menu.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf',
                    timeout=10,
                    numDigits=1,
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            else:
                # Create a more readable menu list without prices for initial announcement
                menu_text = ". ".join([
                    f"{item['name']}, {item['description']}"
                    for item in menu_items[:3]  # Limit to first 3 items to keep it short
                ])
                if len(menu_items) > 3:
                    menu_text += f", and {len(menu_items) - 3} more items"
                
                response.say(
                    f"Here are our available menu items: {menu_text}. "
                    "Please say the name of the item you want to order.",
                    voice='alice'
                )
                response.gather(
                    input='speech dtmf',
                    timeout=15,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
        elif digits == '4':
            # Transfer to staff
            session['current_flow'] = 'staff'
            response.say(f"Transferring you to the {restaurant_name} team. Please hold.", voice='alice')
            response.dial(restaurant_data['phone_number'])
            self._update_call_record(call_sid, 'transferred')
            
        elif digits == '5':
            # Hours of operation
            session['current_flow'] = 'hours'
            hours = restaurant_data.get('hours', ["Monday-Friday 7AM-8PM, Saturday-Sunday 8AM-6PM"])
            hours_text = ". ".join(hours) if isinstance(hours, list) else hours
            response.say(
                f"{restaurant_name} is open {hours_text}. "
                "Press 1 to make a reservation, 3 to place an order, or stay on the line to return to the main menu.",
                voice='alice'
            )
            response.gather(
                input='dtmf',
                timeout=10,
                numDigits=1,
                action=request.build_absolute_uri(),
                method='GET'
            )
            
        else:
            # Invalid option
            response.say(
                "Sorry, that's not a valid option. "
                "Press 1 for reservations, 2 for specials, 3 for orders, 4 for staff, or 5 for hours.", 
                voice='alice'
            )
            response.gather(
                input='dtmf',
                timeout=10,
                numDigits=1,
                action=request.build_absolute_uri(),
                method='GET'
            )
        
        return HttpResponse(str(response), content_type='text/xml')

    def _handle_reservation_digits(self, call_sid, digits, request):
        """Handle digits during reservation flow"""
        session = SESSION_CONTEXT[call_sid]
        reservation_details = session['reservation_details']
        
        response = VoiceResponse()
        
        if 'date' not in reservation_details:
            # Process date input
            try:
                if digits == '1':
                    reservation_details['date'] = 'today'
                elif digits == '2':
                    reservation_details['date'] = 'tomorrow'
                else:
                    response.say("Sorry, I didn't understand that date. Please try again.", voice='alice')
                    response.gather(
                        input='speech dtmf',
                        timeout=10,
                        speechTimeout='auto',
                        action=request.build_absolute_uri(),
                        method='GET'
                    )
                    return HttpResponse(str(response), content_type='text/xml')
                
                response.say(
                    f"Got it. You want to reserve a table for {reservation_details['date']}. "
                    "Now, please say or enter the time for your reservation. For example, say '7 PM' or enter '1900' for 7:00 PM.",
                    voice='alice'
                )
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
            except Exception as e:
                logger.error(f"Error processing reservation date: {str(e)}")
                response.say("Sorry, I didn't understand that. Please try again.", voice='alice')
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
        elif 'time' not in reservation_details:
            # Process time input
            try:
                if len(digits) == 3:
                    digits = '0' + digits
                if len(digits) == 4:
                    hour = int(digits[:2])
                    minute = digits[2:]
                    period = 'AM' if hour < 12 else 'PM'
                    if hour > 12:
                        hour -= 12
                    reservation_details['time'] = f"{hour}:{minute} {period}"
                else:
                    response.say("Sorry, I didn't understand that time. Please try again.", voice='alice')
                    response.gather(
                        input='speech dtmf',
                        timeout=10,
                        speechTimeout='auto',
                        action=request.build_absolute_uri(),
                        method='GET'
                    )
                    return HttpResponse(str(response), content_type='text/xml')
                
                response.say(
                    f"Got it. Your reservation is for {reservation_details['time']}. "
                    "Now, please say or enter the number of people in your party.",
                    voice='alice'
                )
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
            except Exception as e:
                logger.error(f"Error processing reservation time: {str(e)}")
                response.say("Sorry, I didn't understand that. Please try again.", voice='alice')
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
        elif 'party_size' not in reservation_details:
            # Process party size
            try:
                party_size = int(digits)
                if party_size < 1:
                    raise ValueError("Party size must be at least 1")
                    
                reservation_details['party_size'] = party_size
                
                # Confirm reservation
                response.say(
                    f"Let me confirm your reservation: "
                    f"Table for {reservation_details['party_size']} on {reservation_details['date']} "
                    f"at {reservation_details['time']}. "
                    "Press 1 to confirm, or 2 to start over.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf',
                    timeout=10,
                    numDigits=1,
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
            except Exception as e:
                logger.error(f"Error processing party size: {str(e)}")
                response.say("Sorry, I didn't understand that. Please say or enter the number of people in your party.", voice='alice')
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
                
        else:
            # Confirmation step
            if digits == '1':
                # Confirm reservation
                if self._process_reservation(call_sid):
                    response.say(
                        "Your reservation has been confirmed! "
                        "We'll send you a confirmation text message. "
                        "Thank you for calling, and we look forward to serving you!",
                        voice='alice'
                    )
                    self._update_call_record(call_sid, 'completed')
                    if call_sid in SESSION_CONTEXT:
                        del SESSION_CONTEXT[call_sid]
                else:
                    response.say(
                        "We couldn't process your reservation at this time. "
                        "Please call back or contact the restaurant directly. "
                        "Thank you for calling!",
                        voice='alice'
                    )
            elif digits == '2':
                # Start over
                session['reservation_details'] = {}
                response.say(
                    "Let's start over. Please say or enter the date for your reservation. "
                    "For example, say 'today' or 'July 30th'.",
                    voice='alice'
                )
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            else:
                response.say(
                    "Sorry, I didn't understand that. "
                    "Press 1 to confirm your reservation, or 2 to start over.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf',
                    timeout=10,
                    numDigits=1,
                    action=request.build_absolute_uri(),
                    method='GET'
                )
        
        return HttpResponse(str(response), content_type='text/xml')

    def _handle_order_digits(self, call_sid, digits, request):
        """Handle digits during order flow"""
        session = SESSION_CONTEXT[call_sid]
        order_details = session['order_details']
        restaurant_data = session['restaurant_data']
        
        response = VoiceResponse()
        
        if order_details['state'] == 'getting_quantity':
            # Process quantity
            try:
                quantity = int(digits)
                if quantity < 1:
                    raise ValueError("Quantity must be at least 1")
                order_details['current_item']['quantity'] = quantity
                order_details['state'] = 'getting_instructions'
                
                response.say(
                    f"Got it. {quantity} {order_details['current_item']['name']}. "
                    "Would you like to add any special instructions for this item? "
                    "For example, 'no onions' or 'extra spicy'. "
                    "If not, just say 'no'.",
                    voice='alice'
                )
                response.gather(
                    input='speech',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            except Exception as e:
                logger.error(f"Error processing quantity: {str(e)}")
                response.say("Sorry, I didn't understand that. Please say or enter the quantity.", voice='alice')
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
        elif order_details['state'] == 'confirming':
            # Confirmation step
            if digits == '1':
                # Confirm order
                if self._process_order(call_sid):
                    response.say(
                        "Your order has been successfully placed! "
                        "We'll send you a confirmation text message with the details. "
                        "Thank you for your order, and we look forward to serving you!",
                        voice='alice'
                    )
                    self._update_call_record(call_sid, 'completed')
                    if call_sid in SESSION_CONTEXT:
                        del SESSION_CONTEXT[call_sid]
                else:
                    response.say(
                        "We couldn't process your order at this time. "
                        "Please call back or contact the restaurant directly. "
                        "Thank you for calling!",
                        voice='alice'
                    )
            elif digits == '2':
                # Start over
                session['order_details'] = {
                    'items': [],
                    'current_item': None,
                    'state': 'selecting_item'
                }
                menu_items = restaurant_data.get('menu_items', [])
                menu_text = ". ".join([
                    f"{item['name']}, {item['description']}"
                    for item in menu_items[:3]
                ])
                if len(menu_items) > 3:
                    menu_text += f", and {len(menu_items) - 3} more items"
                
                response.say(
                    f"Let's start over. Here are our available menu items: {menu_text}. "
                    "Please say the name of the item you want to order.",
                    voice='alice'
                )
                response.gather(
                    input='speech dtmf',
                    timeout=15,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            elif digits == '3':
                # Add another item
                session['order_details']['state'] = 'selecting_item'
                menu_items = restaurant_data.get('menu_items', [])
                menu_text = ". ".join([
                    f"{item['name']}, {item['description']}"
                    for item in menu_items[:3]
                ])
                if len(menu_items) > 3:
                    menu_text += f", and {len(menu_items) - 3} more items"
                
                response.say(
                    f"Great! What else would you like to order? Here are our menu items: {menu_text}. "
                    "Please say the name of the next item you want to order.",
                    voice='alice'
                )
                response.gather(
                    input='speech dtmf',
                    timeout=15,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            else:
                response.say(
                    "Sorry, I didn't understand that. "
                    "Press 1 to confirm your order, 2 to start over, or 3 to add another item.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf',
                    timeout=10,
                    numDigits=1,
                    action=request.build_absolute_uri(),
                    method='GET'
                )
        else:
            response.say("Sorry, I didn't understand that. Please try again.", voice='alice')
            response.gather(
                input='speech dtmf',
                timeout=10,
                speechTimeout='auto',
                action=request.build_absolute_uri(),
                method='GET'
            )
        
        return HttpResponse(str(response), content_type='text/xml')

    def _process_reservation(self, call_sid):
        """Process and store the reservation"""
        try:
            session = SESSION_CONTEXT[call_sid]
            reservation_details = session['reservation_details']
            restaurant_data = session['restaurant_data']
            
            # Save to database
            reservation = Reservation.objects.create(
                restaurant=SubAdminProfile.objects.get(phone_number=restaurant_data['phone_number']),
                date=reservation_details['date'],
                time=reservation_details['time'],
                party_size=reservation_details['party_size'],
                customer_phone=session['to_number']
            )
            
            # Send confirmation SMS
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=(
                    f"Your reservation at {restaurant_data['restaurant_name']} is confirmed!\n"
                    f"Date: {reservation_details['date']}\n"
                    f"Time: {reservation_details['time']}\n"
                    f"Party Size: {reservation_details['party_size']}\n"
                    f"Phone: {restaurant_data['phone_number']}\n"
                    f"Address: {restaurant_data['address']}"
                ),
                from_=settings.TWILIO_PHONE_NUMBER,
                to=session['to_number']
            )
            
            # Send email to restaurant
            send_mail(
                subject=f"New Reservation for {reservation_details['date']} at {reservation_details['time']}",
                message=(
                    f"New reservation details:\n"
                    f"Restaurant: {restaurant_data['restaurant_name']}\n"
                    f"Date: {reservation_details['date']}\n"
                    f"Time: {reservation_details['time']}\n"
                    f"Party Size: {reservation_details['party_size']}\n"
                    f"Customer Phone: {session['to_number']}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[restaurant_data['email']],
                fail_silently=False
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing reservation: {str(e)}")
            return False

    def _process_order(self, call_sid):
        """Process and store the order with enhanced handling"""
        try:
            session = SESSION_CONTEXT[call_sid]
            order_details = session['order_details']
            restaurant_data = session['restaurant_data']
            
            if not order_details['items']:
                raise ValueError("No items in order")
            
            # Get restaurant profile
            restaurant = SubAdminProfile.objects.get(phone_number=restaurant_data['phone_number'])
            
            # Create order in database
            order = Order.objects.create(
                restaurant=restaurant,
                customer_phone=session['to_number'],
                status='received'
            )
            
            # Add order items
            for item in order_details['items']:
                OrderItem.objects.create(
                    order=order,
                    item_name=item['name'],
                    quantity=item['quantity'],
                    price=item.get('price', 0),
                    special_instructions=item.get('instructions', '')
                )
            
            # Prepare order summary for notifications
            order_summary = "\n".join([
                f"- {item['quantity']} x {item['name']} ({item.get('price', 'Price on request')})"
                + (f"\n  Special Instructions: {item['instructions']}" if item.get('instructions') else "")
                for item in order_details['items']
            ])
            total_items = sum(item['quantity'] for item in order_details['items'])
            
            # Send confirmation SMS to customer
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            customer_message = client.messages.create(
                body=(
                    f"📋 Order Confirmation from {restaurant_data['restaurant_name']}\n"
                    f"Order #: {order.id}\n"
                    f"Items:\n{order_summary}\n"
                    f"Total items: {total_items}\n\n"
                    f"📍 {restaurant_data['address']}\n"
                    f"📞 {restaurant_data['phone_number']}\n"
                    f"Estimated ready time: 20-30 minutes"
                ),
                from_=settings.TWILIO_PHONE_NUMBER,
                to=session['to_number']
            )
            
            # Send detailed email to restaurant
            send_mail(
                subject=f"🆕 New Order #{order.id} - {total_items} items",
                message=(
                    f"New order received!\n\n"
                    f"Restaurant: {restaurant_data['restaurant_name']}\n"
                    f"Order #: {order.id}\n"
                    f"Customer Phone: {session['to_number']}\n\n"
                    f"Order Details:\n{order_summary}\n\n"
                    f"Total items: {total_items}\n\n"
                    f"Please prepare this order and contact the customer if needed."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[restaurant_data['email']],
                fail_silently=False
            )
            
            # Send SMS alert to restaurant
            try:
                restaurant_alert = client.messages.create(
                    body=(
                        f"🚨 New Order Alert!\n"
                        f"{total_items} items in Order #{order.id}\n"
                        f"Customer: {session['to_number']}\n"
                        f"Check your email for full details."
                    ),
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=restaurant_data['phone_number']
                )
            except Exception as sms_error:
                logger.warning(f"Could not send SMS to restaurant: {str(sms_error)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing order: {str(e)}", exc_info=True)
            return False

    def _process_speech(self, call_sid, user_input, request):
        """Process the user's speech input"""
        session = SESSION_CONTEXT[call_sid]
        user_input_lower = user_input.lower()
        
        logger.info(f"Processing speech: '{user_input}' for CallSid: {call_sid}")
        
        if session['current_flow'] == 'reservation':
            return self._handle_reservation_speech(call_sid, user_input, request)
        elif session['current_flow'] == 'order':
            return self._handle_order_speech(call_sid, user_input, request)
            
        response = VoiceResponse()
        response.say("Sorry, I didn't understand that. Please try again.", voice='alice')
        response.gather(
            input='speech dtmf',
            timeout=10,
            speechTimeout='auto',
            action=request.build_absolute_uri(),
            method='GET'
        )
        return HttpResponse(str(response), content_type='text/xml')

    def _handle_reservation_speech(self, call_sid, user_input, request):
        """Handle speech input during reservation flow"""
        session = SESSION_CONTEXT[call_sid]
        reservation_details = session['reservation_details']
        
        response = VoiceResponse()
        
        if 'date' not in reservation_details:
            reservation_details['date'] = user_input
            response.say(
                f"Got it. You want to reserve a table for {user_input}. "
                "Now, please say or enter the time for your reservation. For example, say '7 PM' or enter '1900' for 7:00 PM.",
                voice='alice'
            )
            response.gather(
                input='speech dtmf',
                timeout=10,
                speechTimeout='auto',
                action=request.build_absolute_uri(),
                method='GET'
            )
        elif 'time' not in reservation_details:
            reservation_details['time'] = user_input
            response.say(
                f"Got it. Your reservation is for {user_input}. "
                "Now, please say or enter the number of people in your party.",
                voice='alice'
            )
            response.gather(
                input='speech dtmf',
                timeout=10,
                speechTimeout='auto',
                action=request.build_absolute_uri(),
                method='GET'
            )
        elif 'party_size' not in reservation_details:
            try:
                party_size = int(''.join(filter(str.isdigit, user_input)))
                if party_size < 1:
                    raise ValueError("Party size must be at least 1")
                reservation_details['party_size'] = party_size
                response.say(
                    f"Let me confirm your reservation: "
                    f"Table for {reservation_details['party_size']} on {reservation_details['date']} "
                    f"at {reservation_details['time']}. "
                    "Press 1 to confirm, or 2 to start over.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf',
                    timeout=10,
                    numDigits=1,
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            except Exception as e:
                logger.error(f"Error processing party size: {str(e)}")
                response.say("Sorry, I didn't understand that. Please say or enter the number of people in your party.", voice='alice')
                response.gather(
                    input='speech dtmf',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
        else:
            response.say("Sorry, I didn't understand that. Please try again.", voice='alice')
            response.gather(
                input='speech dtmf',
                timeout=10,
                speechTimeout='auto',
                action=request.build_absolute_uri(),
                method='GET'
            )
        
        return HttpResponse(str(response), content_type='text/xml')

    def _handle_order_speech(self, call_sid, user_input, request):
        """Handle order flow with both speech and DTMF input support"""
        session = SESSION_CONTEXT[call_sid]
        order_details = session['order_details']
        restaurant_data = session['restaurant_data']
        
        response = VoiceResponse()
        user_input_lower = user_input.lower().strip() if isinstance(user_input, str) else ""

        # Get menu items for reference
        menu_items = restaurant_data.get('menu_items', [])
        menu_options = {str(i+1): item for i, item in enumerate(menu_items[:9])}  # Limit to 9 items for DTMF
        
        # State machine for order flow
        if order_details['state'] == 'selecting_item':
            # Check if input is a DTMF menu selection
            if user_input.isdigit() and user_input in menu_options:
                selected_item = menu_options[user_input]
                order_details['current_item'] = {
                    'name': selected_item['name'],
                    'price': selected_item.get('price', 'Price on request'),
                    'description': selected_item.get('description', '')
                }
                order_details['state'] = 'getting_quantity'
                
                response.say(
                    f"You selected {selected_item['name']}. "
                    "Please enter the quantity using your keypad or say the number you want.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf speech',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            else:
                # Handle speech input for item selection
                best_match = None
                best_score = 0
                
                # Find best matching menu item
                for item in menu_items:
                    item_name_lower = item['name'].lower()
                    score = fuzz.ratio(user_input_lower, item_name_lower)
                    if score > best_score:
                        best_match = item
                        best_score = score
                
                if best_match and best_score > 60:  # Threshold for acceptable match
                    order_details['current_item'] = {
                        'name': best_match['name'],
                        'price': best_match.get('price', 'Price on request'),
                        'description': best_match.get('description', '')
                    }
                    order_details['state'] = 'getting_quantity'
                    
                    response.say(
                        f"I think you want {best_match['name']}. "
                        "Please say or enter the quantity. "
                        "For example, say 'two' or press 2 on your keypad.",
                        voice='alice'
                    )
                    response.gather(
                        input='dtmf speech',
                        timeout=10,
                        speechTimeout='auto',
                        action=request.build_absolute_uri(),
                        method='GET'
                    )
                else:
                    # No match found - present DTMF options
                    response.say(
                        "Please select an item using your keypad:",
                        voice='alice'
                    )
                    for i, item in menu_options.items():
                        response.say(f"Press {i} for {item['name']}", voice='alice')
                    
                    response.say(
                        "Or say the name of the item you want.",
                        voice='alice'
                    )
                    response.gather(
                        input='dtmf speech',
                        timeout=15,
                        speechTimeout='auto',
                        action=request.build_absolute_uri(),
                        method='GET'
                    )
        
        elif order_details['state'] == 'getting_quantity':
            try:
                # Handle both DTMF and speech input for quantity
                if user_input.isdigit():
                    quantity = int(user_input)
                else:
                    quantity = self._extract_quantity(user_input)
                    
                if quantity < 1:
                    raise ValueError("Quantity must be at least 1")
                    
                order_details['current_item']['quantity'] = quantity
                order_details['state'] = 'getting_instructions'
                
                response.say(
                    f"Got {quantity} {order_details['current_item']['name']}. "
                    "For special instructions, say them now or press 1 to skip.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf speech',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
            except Exception as e:
                logger.error(f"Error processing quantity: {str(e)}")
                response.say(
                    "Sorry, I didn't understand. Please enter the quantity using your keypad or say the number.",
                    voice='alice'
                )
                response.gather(
                    input='dtmf speech',
                    timeout=10,
                    speechTimeout='auto',
                    action=request.build_absolute_uri(),
                    method='GET'
                )
        
        elif order_details['state'] == 'getting_instructions':
            # Handle special instructions
            if user_input.isdigit() and user_input == '1':
                # User pressed 1 to skip instructions
                pass
            elif user_input_lower not in ('no', 'none', 'skip'):
                order_details['current_item']['instructions'] = user_input
            
            # Add item to order
            order_details['items'].append(order_details['current_item'])
            order_details['current_item'] = None
            order_details['state'] = 'confirming'
            
            # Present confirmation options
            item_count = len(order_details['items'])
            if item_count == 1:
                response.say(
                    "You have 1 item in your order. "
                    "Press 1 to confirm, 2 to add another item, or 3 to start over.",
                    voice='alice'
                )
            else:
                order_summary = ", ".join(
                    f"{item['quantity']} {item['name']}" 
                    for item in order_details['items']
                )
                response.say(
                    f"Your order has: {order_summary}. "
                    "Press 1 to confirm, 2 to add another item, or 3 to start over.",
                    voice='alice'
                )
            
            response.gather(
                input='dtmf',
                timeout=10,
                numDigits=1,
                action=request.build_absolute_uri(),
                method='GET'
            )
        
        else:
            response.say("Sorry, I didn't understand. Let's try again.", voice='alice')
            return self._ask_again(request, call_sid)
        
        return HttpResponse(str(response), content_type='text/xml')

    def _extract_quantity(self, text):
        """Extract quantity from spoken text"""
        # First try to find direct numbers
        numbers = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
        }
        
        text_lower = text.lower()
        
        # Check for word numbers
        for word, num in numbers.items():
            if word in text_lower:
                return num
        
        # Check for digits in the text
        digits = re.findall(r'\d+', text)
        if digits:
            return int(digits[0])
        
        # Default to 1 if we can't determine
        return 1

    def _create_call_record(self, call_sid, to_number):
        """Create a record of the call in the database"""
        try:
            from superadmin.models import CallRecord, SubAdminProfile
            restaurant = SubAdminProfile.objects.filter(phone_number=to_number).first()
            if restaurant:
                call_record = CallRecord.objects.create(
                    restaurant=restaurant,
                    call_sid=call_sid,
                    status='in-progress'
                )
                SESSION_CONTEXT[call_sid]['call_record'] = call_record
                logger.info(f"Created call record: {call_record.id}")
        except Exception as e:
            logger.error(f"Error creating call record: {str(e)}")

    def _update_call_record(self, call_sid, status):
        """Update the call record status"""
        try:
            if call_sid in SESSION_CONTEXT and SESSION_CONTEXT[call_sid].get('call_record'):
                call_record = SESSION_CONTEXT[call_sid]['call_record']
                call_record.status = status
                call_record.save()
                logger.info(f"Updated call record {call_record.id} to status: {status}")
        except Exception as e:
            logger.error(f"Error updating call record: {str(e)}")

    def _say_goodbye(self, call_sid):
        """Handle call ending"""
        restaurant_data = SESSION_CONTEXT[call_sid]['restaurant_data']
        restaurant_name = restaurant_data.get('restaurant_name', 'us') if restaurant_data else 'us'
        response = VoiceResponse()
        response.say(f"Thank you for calling {restaurant_name}! We appreciate your interest and hope to serve you soon. Have a wonderful day!", voice='alice')
        
        self._update_call_record(call_sid, 'completed')
        if call_sid in SESSION_CONTEXT:
            del SESSION_CONTEXT[call_sid]
        
        return HttpResponse(str(response), content_type='text/xml')




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