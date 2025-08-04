# utils.py
from twilio.rest import Client
from django.conf import settings
from datetime import datetime
import logging
import re
from django.utils import timezone
from datetime import timedelta


logger = logging.getLogger(__name__)

def get_current_day():
    """Get current day of week"""
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return days[datetime.now().weekday()]


def clean_phone_number(phone_number):
    """Clean and format phone number properly"""
    if not phone_number:
        return None
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', str(phone_number))
    
    # Handle different phone number formats
    if digits_only.startswith('91') and len(digits_only) == 12:
        # Already has country code
        return f"+{digits_only}"
    elif len(digits_only) == 10:
        # Add India country code
        return f"+91{digits_only}"
    elif digits_only.startswith('1') and len(digits_only) == 11:
        # US number
        return f"+{digits_only}"
    else:
        # Return as is if we can't determine format
        return f"+91{digits_only[-10:]}"

def format_business_hours(business_hours_queryset):
    """Format business hours for display"""
    hours_text = ""
    for hours in business_hours_queryset:
        if hours.closed_all_day:
            hours_text += f"{hours.day}: Closed\n"
        else:
            hours_text += f"{hours.day}: {hours.opening_time.strftime('%I:%M %p')} - {hours.closing_time.strftime('%I:%M %p')}\n"
    return hours_text

def send_sms(phone_number, message):
    """Send SMS using Twilio with proper phone number formatting"""
    try:
        # Get Twilio credentials from settings
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        twilio_phone_number = settings.TWILIO_PHONE_NUMBER
        
        # Validate required settings
        if not all([account_sid, auth_token, twilio_phone_number]):
            logger.error("Twilio credentials not properly configured")
            return False
        
        # Clean and format phone number
        formatted_phone = clean_phone_number(phone_number)
        
        if not formatted_phone:
            logger.error(f"Invalid phone number format: {phone_number}")
            return False
        
        logger.info(f"Sending SMS to formatted number: {formatted_phone}")
        
        # Create Twilio client
        client = Client(account_sid, auth_token)
        
        # Send SMS
        message_instance = client.messages.create(
            body=message,
            from_=twilio_phone_number,
            to=formatted_phone
        )
        
        logger.info(f"SMS sent successfully. Message SID: {message_instance.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Twilio SMS sending error: {e}")
        return False

def validate_phone_number(phone_number):
    """Validate phone number format"""
    import re
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone_number)
    
    # Check if it's a valid Indian mobile number (10 digits)
    if len(digits_only) == 10 and digits_only.startswith(('6', '7', '8', '9')):
        return True
    
    # Check if it's already in international format
    if len(digits_only) == 12 and digits_only.startswith('91'):
        return True
        
    return False



def is_plan_active(subadmin):
    """Check if the subadmin has an active paid plan"""
    try:
        from superadmin.models import PlanPayment  # Replace 'your_app' with your actual app name
        
        # Get the latest PAID payment for this subadmin
        latest_payment = PlanPayment.objects.filter(
            subadmin=subadmin,
            payment_status='PAID'
        ).order_by('-created_at').first()
        
        if not latest_payment:
            return False
        
        # Check if plan is not expired (assuming 30 days validity)
        expiry_date = latest_payment.created_at + timedelta(days=30)
        
        return timezone.now() < expiry_date
        
    except Exception as e:
        logger.error(f"Error checking plan status for {subadmin}: {e}")
        return False
