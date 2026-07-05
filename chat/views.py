from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from .models import Message, ChatRoom, MessageStatus
from .serializers import MessageSerializer, ChatRoomSerializer
import mimetypes
import cloudinary.uploader
import cloudinary.api
from cloudinary.exceptions import Error as CloudinaryError
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)
User = get_user_model()

class MessageListCreateView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        other_user_id = self.request.query_params.get('user_id')
        
        if other_user_id:
            messages = Message.objects.filter(
                Q(sender=user, receiver_id=other_user_id) |
                Q(sender_id=other_user_id, receiver=user)
            ).select_related('sender', 'receiver').prefetch_related('statuses')
            
            # Mark messages as read
            Message.objects.filter(
                sender_id=other_user_id,
                receiver=user,
                is_read=False
            ).update(is_read=True)
            
            MessageStatus.objects.filter(
                message__sender_id=other_user_id,
                message__receiver=user,
                is_read=False
            ).update(is_read=True, read_at=timezone.now())
            
            return messages.order_by('timestamp')
        
        return Message.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender', 'receiver').prefetch_related('statuses').order_by('-timestamp')

    def create(self, request, *args, **kwargs):
        try:
            receiver_id = request.data.get('receiver')
            content = request.data.get('content', '')
            message_type = request.data.get('message_type', 'text')
            media_file = request.FILES.get('media_file')
            reply_to_id = request.data.get('reply_to')
            
            # Validate receiver
            if not receiver_id:
                return Response(
                    {"error": "receiver is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                receiver = User.objects.get(id=receiver_id)
            except User.DoesNotExist:
                return Response(
                    {"error": "Receiver not found"}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Create message object
            message = Message(
                sender=request.user,
                receiver=receiver,
                content=content,
                message_type=message_type,
                reply_to_id=reply_to_id
            )
            
            # Handle media file if present
            if media_file:
                try:
                    # Get file info
                    mime_type = media_file.content_type or mimetypes.guess_type(media_file.name)[0]
                    
                    # Determine resource type and message type
                    resource_type = 'auto'
                    detected_message_type = 'file'
                    
                    if mime_type and mime_type.startswith('image/'):
                        resource_type = 'image'
                        detected_message_type = 'image'
                    elif mime_type and mime_type.startswith('video/'):
                        resource_type = 'video'
                        detected_message_type = 'video'
                    elif mime_type and mime_type.startswith('audio/'):
                        resource_type = 'video'
                        detected_message_type = 'audio'
                    else:
                        resource_type = 'raw'
                        detected_message_type = 'file'
                    
                    # Update message_type if media is present
                    if detected_message_type != 'text':
                        message.message_type = detected_message_type
                    
                    # Prepare upload options
                    upload_options = {
                        'resource_type': resource_type,
                        'folder': 'chat_media',
                        'use_filename': True,
                        'unique_filename': True,
                    }
                    
                    # Add image-specific options
                    if resource_type == 'image':
                        upload_options.update({
                            'width': 1200,
                            'height': 1200,
                            'crop': 'limit',
                            'quality': 'auto:best',
                            'fetch_format': 'auto'
                        })
                    
                    # Upload to Cloudinary
                    logger.info(f"Uploading to Cloudinary: {media_file.name} ({resource_type})")
                    upload_result = cloudinary.uploader.upload(media_file, **upload_options)
                    
                    # Save Cloudinary data to message
                    message.cloudinary_public_id = upload_result.get('public_id')
                    message.cloudinary_version = upload_result.get('version')
                    message.file_name = upload_result.get('original_filename', media_file.name)
                    message.file_size = upload_result.get('bytes', media_file.size)
                    message.mime_type = mime_type or upload_result.get('format')
                    message.media_url = upload_result.get('secure_url')
                    message.media_file = upload_result.get('secure_url')
                    
                    # Generate thumbnail for images
                    if resource_type == 'image':
                        try:
                            from cloudinary.utils import cloudinary_url
                            thumbnail_url, options = cloudinary_url(
                                upload_result.get('public_id'),
                                width=200,
                                height=200,
                                crop='thumb',
                                gravity='face',
                                quality='auto',
                                fetch_format='auto',
                                secure=True
                            )
                            message.thumbnail = thumbnail_url
                        except Exception as e:
                            logger.error(f"Thumbnail creation failed: {e}")
                    
                    # For videos, generate video thumbnail
                    elif resource_type == 'video':
                        try:
                            from cloudinary.utils import cloudinary_url
                            thumbnail_url, options = cloudinary_url(
                                upload_result.get('public_id'),
                                resource_type='video',
                                width=200,
                                height=200,
                                crop='thumb',
                                format='jpg',
                                secure=True
                            )
                            message.thumbnail = thumbnail_url
                        except Exception as e:
                            logger.error(f"Video thumbnail creation failed: {e}")
                    
                    logger.info(f"Upload successful: {upload_result.get('public_id')}")
                    
                except CloudinaryError as e:
                    logger.error(f"Cloudinary upload error: {e}")
                    return Response(
                        {"error": f"Failed to upload media: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
                except Exception as e:
                    logger.error(f"Unexpected error during upload: {e}")
                    return Response(
                        {"error": f"Upload failed: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )
            
            # Save the message
            message.save()
            
            # Create message statuses
            MessageStatus.objects.create(
                message=message, 
                user=request.user, 
                is_delivered=True,
                delivered_at=timezone.now()
            )
            MessageStatus.objects.create(
                message=message, 
                user=receiver, 
                is_delivered=False
            )
            
            # Update or create chat room
            chat_room = ChatRoom.objects.filter(
                participants=request.user
            ).filter(participants=receiver).first()
            
            if not chat_room:
                chat_room = ChatRoom.objects.create()
                chat_room.participants.add(request.user, receiver)
            
            chat_room.last_message = message
            chat_room.save()
            
            # Cache the message
            cache_key = f"message_{message.id}"
            cache.set(cache_key, message, timeout=300)
            
            # Return the created message
            serializer = self.get_serializer(message, context={'request': request})
            return Response(serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error in message create: {e}")
            return Response(
                {"error": f"Failed to create message: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class MessageDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        try:
            message = Message.objects.get(id=pk)
            if message.sender != request.user and message.receiver != request.user:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = MessageSerializer(message, context={'request': request})
            return Response(serializer.data)
        except Message.DoesNotExist:
            return Response(
                {"error": "Message not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, pk):
        try:
            message = Message.objects.get(id=pk)
            if message.sender != request.user:
                return Response(
                    {"error": "Not authorized to delete this message"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Delete from Cloudinary if it exists
            if message.cloudinary_public_id:
                try:
                    resource_type = 'image'
                    if message.mime_type and message.mime_type.startswith('video/'):
                        resource_type = 'video'
                    elif message.mime_type and not message.mime_type.startswith('image/'):
                        resource_type = 'raw'
                    
                    cloudinary.uploader.destroy(
                        message.cloudinary_public_id,
                        resource_type=resource_type
                    )
                except CloudinaryError as e:
                    logger.error(f"Error deleting from Cloudinary: {e}")
            
            message.is_deleted = True
            message.save()
            return Response({"message": "Message deleted successfully"})
        except Message.DoesNotExist:
            return Response(
                {"error": "Message not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class ChatRoomListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        cache_key = f"chat_rooms_{user.id}"
        rooms = cache.get(cache_key)
        
        if rooms is None:
            rooms = ChatRoom.objects.filter(
                participants=user
            ).select_related('last_message').prefetch_related(
                'participants', 'last_message__sender', 'last_message__receiver'
            ).order_by('-created_at')
            
            cache.set(cache_key, rooms, timeout=30)
        
        return rooms

    def perform_create(self, serializer):
        chat_room = serializer.save()
        chat_room.participants.add(self.request.user)

class ChatRoomDetailView(generics.RetrieveAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatRoom.objects.filter(participants=self.request.user)

class UnreadMessagesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        unread_count = Message.objects.filter(
            receiver=request.user,
            is_read=False
        ).count()
        
        return Response({"unread_count": unread_count})

class MessageStatusView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        message_id = request.data.get('message_id')
        status_type = request.data.get('status_type')
        
        try:
            message = Message.objects.get(id=message_id)
            if message.receiver != request.user:
                return Response(
                    {"error": "Not authorized"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            status, created = MessageStatus.objects.get_or_create(
                message=message,
                user=request.user
            )
            
            if status_type == 'read':
                status.is_read = True
                status.read_at = timezone.now()
                message.is_read = True
                message.save()
            elif status_type == 'delivered':
                status.is_delivered = True
                status.delivered_at = timezone.now()
                message.is_delivered = True
                message.save()
            
            status.save()
            return Response({"success": True})
        except Message.DoesNotExist:
            return Response(
                {"error": "Message not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class PendingMessagesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        pending_messages = Message.objects.filter(
            receiver=request.user,
            is_delivered=False
        ).select_related('sender')
        
        serializer = MessageSerializer(pending_messages, many=True, context={'request': request})
        return Response(serializer.data)

class UploadFileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        file = request.FILES.get('file')
        chunk_index = request.data.get('chunk_index', 0)
        total_chunks = request.data.get('total_chunks', 1)
        
        if not file:
            return Response(
                {"error": "File is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if file.size > 50 * 1024 * 1024:
            return Response(
                {"error": "File size exceeds 50MB limit"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Determine resource type
            mime_type = file.content_type or mimetypes.guess_type(file.name)[0]
            resource_type = 'auto'
            if mime_type and mime_type.startswith('image/'):
                resource_type = 'image'
            elif mime_type and mime_type.startswith('video/'):
                resource_type = 'video'
            else:
                resource_type = 'raw'
            
            upload_result = cloudinary.uploader.upload(
                file,
                resource_type=resource_type,
                folder='chat_uploads',
                use_filename=True,
                unique_filename=True
            )
            
            return Response({
                "success": True,
                "file_url": upload_result.get('secure_url'),
                "public_id": upload_result.get('public_id'),
                "file_name": upload_result.get('original_filename'),
                "file_size": upload_result.get('bytes'),
                "format": upload_result.get('format')
            })
            
        except CloudinaryError as e:
            return Response(
                {"error": f"Upload failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DeleteMediaView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        public_id = request.data.get('public_id')
        resource_type = request.data.get('resource_type', 'auto')
        
        if not public_id:
            return Response(
                {"error": "Public ID is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = cloudinary.uploader.destroy(
                public_id,
                resource_type=resource_type
            )
            return Response({
                "success": True,
                "result": result
            })
        except CloudinaryError as e:
            return Response(
                {"error": f"Delete failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ClearChatCacheView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        cache_key = f"chat_rooms_{request.user.id}"
        cache.delete(cache_key)
        return Response({"message": "Cache cleared"})

class CloudinarySignUploadView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        folder = request.data.get('folder', 'chat_uploads')
        resource_type = request.data.get('resource_type', 'auto')
        
        try:
            from cloudinary.utils import api_sign_request
            from django.conf import settings
            
            timestamp = int(timezone.now().timestamp())
            
            signature = api_sign_request(
                {
                    'timestamp': timestamp,
                    'folder': folder,
                    'resource_type': resource_type
                },
                settings.CLOUDINARY_API_SECRET
            )
            
            return Response({
                'timestamp': timestamp,
                'signature': signature,
                'api_key': settings.CLOUDINARY_API_KEY,
                'cloud_name': settings.CLOUDINARY_CLOUD_NAME,
                'folder': folder
            })
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )