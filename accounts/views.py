from django.utils import timezone
import datetime
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from django.db import models
from .serializers import *
from .models import OTP
import random
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError

User = get_user_model()

class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            OTP.objects.create(
                user=user,
                otp=otp_code,
                purpose='verification'
            )
            
            subject = 'Verify your email'
            message = f'Your OTP for verification is: {otp_code}\n\nThis OTP will expire in 10 minutes.'
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
            
            return Response({
                "message": "Registration successful. Please check your email for OTP.",
                "email": user.email
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')
        
        if not email or not otp_code:
            return Response(
                {"error": "Email and OTP are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if user.is_email_verified:
            return Response(
                {"message": "Email already verified"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            otp = OTP.objects.filter(
                user=user,
                otp=otp_code,
                is_used=False,
                purpose='verification'
            ).latest('created_at')
        except OTP.DoesNotExist:
            return Response(
                {"error": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if otp.is_expired():
            return Response(
                {"error": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp.is_used = True
        otp.save()
        
        user.is_email_verified = True
        user.save()
        
        return Response({
            "message": "Email verified successfully. You can now login."
        })

class ResendOTPView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if user.is_email_verified:
            return Response(
                {"error": "Email already verified"},
                status=status.HTTP_400_BAD_REQUEST
            )

        OTP.objects.filter(user=user, is_used=False, purpose='verification').update(is_used=True)
        
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        OTP.objects.create(
            user=user,
            otp=otp_code,
            purpose='verification'
        )

        subject = 'Verify your email'
        message = f'Your new OTP for verification is: {otp_code}\n\nThis OTP will expire in 10 minutes.'
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

        return Response({
            "message": "New OTP sent to your email"
        })

class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {"error": "Username and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = None
        try:
            if '@' in username:
                user = User.objects.get(email=username)
            else:
                user = User.objects.get(username=username)
        except User.DoesNotExist:
            pass
        
        if user:
            if not user.is_email_verified:
                OTP.objects.filter(user=user, is_used=False, purpose='verification').update(is_used=True)
                
                otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
                OTP.objects.create(
                    user=user,
                    otp=otp_code,
                    purpose='verification'
                )
                
                subject = 'Email Verification Required'
                message = f'Your OTP for verification is: {otp_code}\n\nPlease verify your email before logging in. This OTP will expire in 10 minutes.'
                send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
                
                return Response(
                    {
                        "error": "Please verify your email first. A new OTP has been sent to your email.",
                        "email": user.email,
                        "needs_verification": True
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if user.check_password(password):
                Token.objects.filter(user=user).delete()
                token = Token.objects.create(user=user)
                
                serializer = UserSerializer(user, context={'request': request})
                return Response({
                    'token': token.key,
                    'user': serializer.data
                })
        
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED
        )

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response(
                {"error": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "If your email is registered, you will receive a password reset link."},
                status=status.HTTP_200_OK
            )
        
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        OTP.objects.create(
            user=user,
            otp=otp_code,
            purpose='reset_password'
        )
        
        subject = 'Password Reset'
        message = f'Your password reset OTP is: {otp_code}\n\nThis OTP will expire in 10 minutes.\n\nIf you did not request this, please ignore this email.'
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])
        
        return Response({
            "message": "If your email is registered, you will receive a password reset link."
        })

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        otp_code = request.data.get('otp')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not email or not otp_code or not new_password or not confirm_password:
            return Response(
                {"error": "All fields are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_password != confirm_password:
            return Response(
                {"error": "Passwords don't match"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            otp = OTP.objects.filter(
                user=user,
                otp=otp_code,
                is_used=False,
                purpose='reset_password'
            ).latest('created_at')
        except OTP.DoesNotExist:
            return Response(
                {"error": "Invalid OTP"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if otp.is_expired():
            return Response(
                {"error": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp.is_used = True
        otp.save()
        
        user.set_password(new_password)
        user.save()
        
        Token.objects.filter(user=user).delete()
        
        return Response({
            "message": "Password reset successfully. Please login with your new password."
        })

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)
    
    def put(self, request):
        serializer = UpdateProfileSerializer(
            request.user, 
            data=request.data, 
            context={'request': request}
        )
        if serializer.is_valid():
            # Handle profile picture upload to Cloudinary
            if 'profile_picture' in request.FILES:
                try:
                    profile_pic = request.FILES['profile_picture']
                    upload_result = cloudinary.uploader.upload(
                        profile_pic,
                        folder='profile_pics',
                        width=300,
                        height=300,
                        crop='fill',
                        quality='auto:best',
                        fetch_format='auto'
                    )
                    request.user.profile_picture = upload_result.get('secure_url')
                except CloudinaryError as e:
                    return Response(
                        {"error": f"Failed to upload profile picture: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            serializer.save()
            user_serializer = UserSerializer(request.user, context={'request': request})
            return Response(user_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        serializer = UpdateProfileSerializer(
            request.user, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            if 'profile_picture' in request.FILES:
                try:
                    profile_pic = request.FILES['profile_picture']
                    upload_result = cloudinary.uploader.upload(
                        profile_pic,
                        folder='profile_pics',
                        width=300,
                        height=300,
                        crop='fill',
                        quality='auto:best',
                        fetch_format='auto'
                    )
                    request.user.profile_picture = upload_result.get('secure_url')
                except CloudinaryError as e:
                    return Response(
                        {"error": f"Failed to upload profile picture: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            serializer.save()
            user_serializer = UserSerializer(request.user, context={'request': request})
            return Response(user_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        users = User.objects.exclude(id=request.user.id)
        serializer = UserSerializer(users, many=True, context={'request': request})
        return Response(serializer.data)

class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        search = request.query_params.get('search', '')
        if search:
            users = User.objects.filter(
                models.Q(username__icontains=search) | 
                models.Q(email__icontains=search)
            ).exclude(id=request.user.id)
        else:
            users = User.objects.exclude(id=request.user.id)
        
        serializer = UserSerializer(users, many=True, context={'request': request})
        return Response(serializer.data)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            request.user.auth_token.delete()
            return Response({"message": "Logged out successfully"})
        except:
            return Response({"message": "Logged out successfully"})

class DebugOTPView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response({"error": "Email required"}, status=400)
        
        try:
            user = User.objects.get(email=email)
            
            otps = OTP.objects.filter(user=user).order_by('-created_at')
            otp_data = []
            for otp in otps:
                otp_data.append({
                    "otp": otp.otp,
                    "purpose": otp.purpose,
                    "created_at": otp.created_at,
                    "is_used": otp.is_used,
                    "is_expired": otp.is_expired(),
                    "age_seconds": (timezone.now() - otp.created_at).total_seconds()
                })
            
            return Response({
                "email": user.email,
                "is_email_verified": user.is_email_verified,
                "otps": otp_data,
                "current_time": timezone.now()
            })
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)