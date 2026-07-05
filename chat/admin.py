from django.contrib import admin
from .models import Message, ChatRoom, MessageStatus

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'message_type', 'content_preview', 'timestamp', 'is_read', 'is_delivered')
    list_filter = ('message_type', 'is_read', 'is_delivered', 'timestamp')
    search_fields = ('sender__username', 'receiver__username', 'content')
    readonly_fields = ('timestamp', 'cloudinary_public_id', 'media_url')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if obj.content else 'No content'
    content_preview.short_description = 'Content Preview'

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'room_name', 'is_group', 'created_at')
    filter_horizontal = ('participants',)

@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'is_delivered', 'is_read', 'delivered_at', 'read_at')