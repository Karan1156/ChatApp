from rest_framework import serializers
from .models import Message, ChatRoom, MessageStatus
from django.contrib.auth import get_user_model

User = get_user_model()

class MessageStatusSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = MessageStatus
        fields = ('id', 'user', 'username', 'is_delivered', 'is_read', 'delivered_at', 'read_at')

class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)
    receiver_name = serializers.CharField(source='receiver.username', read_only=True)
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    receiver_email = serializers.CharField(source='receiver.email', read_only=True)
    
    media_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    statuses = MessageStatusSerializer(many=True, read_only=True)
    time_ago = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'id', 'sender', 'receiver', 'sender_name', 'receiver_name',
            'sender_email', 'receiver_email', 'content', 'message_type',
            'media_file', 'media_url', 'thumbnail', 'thumbnail_url',
            'file_name', 'file_size', 'mime_type', 'timestamp', 'is_read',
            'is_delivered', 'is_deleted', 'reply_to', 'statuses', 'time_ago',
            'is_mine', 'cloudinary_public_id'
        )
        read_only_fields = ('sender', 'timestamp', 'is_read', 'is_delivered')

    def get_media_url(self, obj):
        if obj.media_url:
            return obj.media_url
        if obj.media_file:
            return obj.media_file
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            return obj.thumbnail
        return None

    def get_time_ago(self, obj):
        from django.utils import timezone
        
        now = timezone.now()
        diff = now - obj.timestamp
        
        if diff.days > 365:
            return f"{diff.days // 365}y ago"
        elif diff.days > 30:
            return f"{diff.days // 30}mo ago"
        elif diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        else:
            return "Just now"

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.sender.id == request.user.id
        return False

    def validate(self, data):
        if not data.get('content') and not data.get('media_file'):
            raise serializers.ValidationError("Message must have content or media")
        return data

class ChatRoomSerializer(serializers.ModelSerializer):
    last_message = MessageSerializer(read_only=True)
    participants = serializers.PrimaryKeyRelatedField(
        many=True, 
        read_only=True
    )
    participant_count = serializers.SerializerMethodField()
    last_message_time = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    room_icon_url = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = (
            'id', 'participants', 'participant_count', 'created_at',
            'last_message', 'last_message_time', 'is_group', 'room_name',
            'room_icon', 'room_icon_url', 'unread_count'
        )

    def get_participant_count(self, obj):
        return obj.participants.count()

    def get_last_message_time(self, obj):
        if obj.last_message:
            return obj.last_message.timestamp
        return obj.created_at

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return MessageStatus.objects.filter(
                message__chat_room_last_message__in=[obj],
                user=request.user,
                is_read=False
            ).count()
        return 0

    def get_room_icon_url(self, obj):
        if obj.room_icon:
            return obj.room_icon
        return None