from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import CustomUser, SubAdminProfile, UserProfile, ROLE_SUBADMIN, ROLE_USER
from .serializers import (
    RegisterSerializer, LoginSerializer,
    SubAdminProfileSerializer, UserProfileSerializer
)
from urllib.parse import urlencode
from rest_framework_simplejwt.tokens import RefreshToken,TokenError
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .utils import account_activation_token
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .utils import success_response, error_response

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

# ---------- Registration API ----------
class RegisterAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)
            return success_response(
                message="User registered successfully",
                data={'user': serializer.data, 'tokens': tokens},
                status_code=201
            )
        return error_response("Validation failed", serializer.errors)

# ---------- Login API ----------
class LoginAPIView(APIView):

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)
            return success_response("Login successful", {
                'tokens': tokens,
                'role': user.role,
                'user_id': user.id,
                'email': user.email,
                'username': user.first_name
            })
        return error_response("Invalid login credentials", serializer.errors)
     
     
# ---------Logout API ----------------#
class LogoutAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return success_response("Successfully logged out", status_code=status.HTTP_200_OK)
        except KeyError:
            return error_response("Refresh token is required")
        except TokenError:
            return error_response("Invalid or expired refresh token")
        


class CustomTokenRefreshAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return error_response("Refresh token is required")

        try:
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            return success_response("Access token refreshed successfully", {"access": access_token})
        except TokenError:
            return error_response("Invalid or expired refresh token")


class ForgotPasswordAPIView(APIView):

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return error_response("Email is required")

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return error_response("User with this email does not exist", status_code=404)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)

        # Prepare query string
        query_params = urlencode({
            "uid": uid,
            "token": token,
            "email": email
        })

        # Send URL with query string only (no path params)
        reset_url = f"{settings.FRONTEND_URL}auth/reset-password?{query_params}"

        context = {
            'user': user,
            'reset_url': reset_url,
            'support_email': settings.SUPPORT_EMAIL,
            'company_name': settings.COMPANY_NAME,
        }

        html_content = render_to_string('emails/password_reset.html', context)
        text_content = strip_tags(html_content)

        msg = EmailMultiAlternatives(
            subject="Reset Your Password - Action Required",
            body=text_content,
            from_email=f"{settings.COMPANY_NAME} <{settings.DEFAULT_FROM_EMAIL}>",
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()

        return success_response("Password reset link has been sent to your email")

    

class ResetPasswordAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist):
            return error_response("Invalid reset link")

        if not account_activation_token.check_token(user, token):
            return error_response("Invalid or expired token")

        new_password = request.data.get("password")
        if not new_password:
            return error_response("Password is required")

        user.set_password(new_password)
        user.save()
        return success_response("Password reset successful")


# ---------- SubAdmin Profile Update API ----------
class SubAdminProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != ROLE_SUBADMIN:
            return Response({"detail": "Unauthorized"}, status=403)
        profile, _ = SubAdminProfile.objects.get_or_create(user=request.user)
        serializer = SubAdminProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request):
        if request.user.role != ROLE_SUBADMIN:
            return Response({"detail": "Unauthorized"}, status=403)
        profile, _ = SubAdminProfile.objects.get_or_create(user=request.user)
        serializer = SubAdminProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)


# ---------- User Profile Update API ----------
class UserProfileAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != ROLE_USER:
            return Response({"detail": "Unauthorized"}, status=403)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    def put(self, request):
        if request.user.role != ROLE_USER:
            return Response({"detail": "Unauthorized"}, status=403)
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)