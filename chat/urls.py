from django.urls import path
from .views import *
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def health_check(request):
    return JsonResponse({"status": "ok", "database": "connected"})

urlpatterns = [
    path('api/health/', health_check, name="health_check"),
    
    # Messages
    path('messages/', MessageListCreateView.as_view(), name='messages'),
    path('messages/<int:pk>/', MessageDetailView.as_view(), name='message-detail'),
    
    # Chat Rooms
    path('rooms/', ChatRoomListCreateView.as_view(), name='chat-rooms'),
    path('rooms/<int:pk>/', ChatRoomDetailView.as_view(), name='chat-room-detail'),
    
    # Status & Read Receipts
    path('status/', MessageStatusView.as_view(), name='message-status'),
    path('unread/', UnreadMessagesView.as_view(), name='unread-messages'),
    path('pending/', PendingMessagesView.as_view(), name='pending-messages'),
    
    # File Upload
    path('upload/', UploadFileView.as_view(), name='upload-file'),
    path('delete-media/', DeleteMediaView.as_view(), name='delete-media'),
    path('sign-upload/', CloudinarySignUploadView.as_view(), name='sign-upload'),
    
    # Cache Management
    path('clear-cache/', ClearChatCacheView.as_view(), name='clear-cache'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)