from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import datetime

class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    is_email_verified = models.BooleanField(default=False)
    profile_picture = models.URLField(
        max_length=500,
        null=True,
        blank=True
    )
    bio = models.TextField(max_length=500, blank=True)
    followers = models.ManyToManyField('self', symmetrical=False, related_name='following', blank=True)

    def __str__(self):
        return self.username

class OTP(models.Model):
    PURPOSES = [
        ('verification', 'Email Verification'),
        ('reset_password', 'Password Reset'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='otps')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    purpose = models.CharField(max_length=20, choices=PURPOSES, default='verification')
    
    def is_expired(self):
        expiry_time = self.created_at + datetime.timedelta(minutes=10)
        return timezone.now() > expiry_time
    
    def __str__(self):
        return f"{self.user.email} - {self.otp} ({self.purpose})"