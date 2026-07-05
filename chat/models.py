from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import os

User = get_user_model()

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('video', 'Video'),
        ('audio', 'Audio'),
        ('file', 'File'),
    ]
    
    sender = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='sent_messages'
    )
    receiver = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='received_messages'
    )
    content = models.TextField(blank=True, null=True)
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    
    # Media fields - using URLField for Cloudinary
    media_file = models.URLField(max_length=500, blank=True, null=True)
    media_url = models.URLField(max_length=500, blank=True, null=True)
    thumbnail = models.URLField(max_length=500, blank=True, null=True)
    
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)
    is_delivered = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    # Cloudinary metadata
    cloudinary_public_id = models.CharField(max_length=255, blank=True, null=True)
    cloudinary_version = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['sender', 'receiver', 'timestamp']),
            models.Index(fields=['receiver', 'is_read']),
            models.Index(fields=['message_type']),
        ]

    def __str__(self):
        return f'{self.sender.username} to {self.receiver.username}: {self.content[:30] if self.content else self.message_type}'

class MessageStatus(models.Model):
    """Track message delivery and read status per user"""
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='statuses')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_delivered = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['message', 'user']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.message.id} - {self.user.username}"

class ChatRoom(models.Model):
    participants = models.ManyToManyField(
        User, 
        related_name='chat_rooms'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_message = models.ForeignKey(
        Message, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='chat_room_last_message'
    )
    is_group = models.BooleanField(default=False)
    room_name = models.CharField(max_length=255, blank=True, null=True)
    room_icon = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        if self.is_group:
            return f'Group: {self.room_name or self.id}'
        participants = ', '.join([user.username for user in self.participants.all()])
        return f'Chat Room: {participants}'