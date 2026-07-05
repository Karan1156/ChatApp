from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.conf import settings
import random
import datetime

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()
    profile_picture_optimized = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'profile_picture', 'profile_picture_url', 
                 'profile_picture_optimized', 'bio', 'is_email_verified')
        read_only_fields = ('id', 'is_email_verified')
    
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            return obj.profile_picture
        return None
    
    def get_profile_picture_optimized(self, obj):
        if obj.profile_picture:
            return obj.profile_picture
        return None

class UserDetailSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()
    profile_picture_optimized = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'profile_picture', 'profile_picture_url',
                 'profile_picture_optimized', 'bio', 'is_email_verified')
        read_only_fields = ('id', 'is_email_verified')
    
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            return obj.profile_picture
        return None
    
    def get_profile_picture_optimized(self, obj):
        if obj.profile_picture:
            return obj.profile_picture
        return None

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'confirm_password')

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords don't match"})
        
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({"email": "Email already exists"})
        
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({"username": "Username already exists"})
        
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        user = User.objects.create_user(**validated_data)
        user.is_active = True
        user.is_email_verified = False
        user.save()
        return user

class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('username', 'email', 'bio', 'profile_picture')
        
    def validate_email(self, value):
        user = self.context.get('request').user
        if User.objects.exclude(id=user.id).filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value
    
    def validate_username(self, value):
        user = self.context.get('request').user
        if User.objects.exclude(id=user.id).filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value