from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.views.generic import TemplateView

from .models import Conversation, Message 
from .serializers import SignUpSerializer, ConversationSerializer 

class IndexView(TemplateView):
    """View to serve the HTML client that contains the entire frontend."""
    template_name = "index.html" 

class SignUpView(generics.CreateAPIView):
    """View for registering new users."""
    queryset = User.objects.all()
    serializer_class = SignUpSerializer
    permission_classes = [] 

    def create(self, request, *args, **kwargs):
        """Handles registration, creates the user, and generates the token."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()             
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                "username": user.username,
                "token": token.key
            }, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response({"error": "The username already exists."}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(generics.GenericAPIView):
    """View for logging in and obtaining the token."""
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """Authenticates the user and returns their token."""
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)

        if user:             
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                "username": user.username,
                "token": token.key
            }, status=status.HTTP_200_OK)
        
        return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)


class ConversationListView(generics.ListCreateAPIView):
    """
    View for listing the authenticated user's conversations and creating new ones.
    """
    serializer_class = ConversationSerializer
    
    def get_queryset(self):
                
        return Conversation.objects.filter(participants=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        
        conversation = serializer.save()         
        
        conversation.participants.add(self.request.user)
                
        # The frontend sends a comma-separated string, e.g., "user1,user2"
        invited_usernames = self.request.data.get('invited_username', '')
        
        if invited_usernames:             
            username_list = [name.strip() for name in invited_usernames.split(',') if name.strip()]
                        
            invited_users = User.objects.filter(username__in=username_list)
            
            if invited_users.exists():                 
                conversation.participants.add(*invited_users)

class AddParticipantView(generics.UpdateAPIView):
    """
    View for adding a participant to an existing conversation.
    Requires Conversation ID (pk) in the URL and 'username' in the POST body.
    """
    queryset = Conversation.objects.all()
    
    def update(self, request, *args, **kwargs):
        conversation = self.get_object() 
        username_to_add = request.data.get('username')

        if not username_to_add:
            return Response({"error": "The username ('username') is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:             
            user_to_add = User.objects.get(username=username_to_add)
            
            if user_to_add in conversation.participants.all():
                return Response({"message": f"User {username_to_add} is already in the conversation."}, status=status.HTTP_200_OK)
            
            conversation.participants.add(user_to_add)
            conversation.save()             

            return Response({"message": f"User {username_to_add} added successfully."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": f"The user '{username_to_add}' does not exist."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:             
            print(f"Error adding participant: {e}") 
            return Response({"error": "An error occurred while processing the request."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)