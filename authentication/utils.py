from django.contrib.auth.tokens import PasswordResetTokenGenerator
import six
from rest_framework.response import Response
from rest_framework import status

class TokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        return (
            six.text_type(user.pk) + six.text_type(timestamp) + six.text_type(user.is_active)
        )

account_activation_token = TokenGenerator()



def success_response(message=None, data=None, status_code=status.HTTP_200_OK):
    return Response({
        "success": True,
        "message": message,
        "data": data
    }, status=status_code)

def error_response(message="An error occurred", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    # Flatten serializer errors into a single-line string
    if isinstance(errors, dict):
        error_list = []
        for field, messages in errors.items():
            if isinstance(messages, list):
                for msg in messages:
                    error_list.append(f"{msg}")
            else:
                error_list.append(f"{messages}")
        error_string = " | ".join(error_list)
    else:
        error_string = str(errors)

    return Response({
        "success": False,
        "message": message,
        "error": error_string
    }, status=status_code)
