from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import CustomUser, SubAdminProfile, UserProfile, ROLE_SUBADMIN, ROLE_USER
from .serializers import (
    RegisterSerializer, LoginSerializer,
    SubAdminProfileSerializer, UserProfileSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken

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
            return Response({'user': serializer.data, 'tokens': tokens}, status=201)
        return Response(serializer.errors, status=400)

# ---------- Login API ----------
class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            tokens = get_tokens_for_user(user)
            return Response({'tokens': tokens, 'role': user.role})
        return Response(serializer.errors, status=400)

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