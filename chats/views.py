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
    template_name = "index.html" 

class SignUpView(generics.CreateAPIView):
    """Vista para registrar nuevos usuarios."""
    queryset = User.objects.all()
    serializer_class = SignUpSerializer
    permission_classes = [] 

    def create(self, request, *args, **kwargs):
        """Maneja el registro, crea el usuario y genera el token."""
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
            return Response({"error": "El nombre de usuario ya existe."}, status=status.HTTP_400_BAD_REQUEST)


class LoginView(generics.GenericAPIView):
    """Vista para iniciar sesión y obtener el token."""
    permission_classes = []

    def post(self, request, *args, **kwargs):
        """Autentica al usuario y devuelve su token."""
        username = request.data.get('username')
        password = request.data.get('password')

        user = authenticate(username=username, password=password)

        if user:            
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                "username": user.username,
                "token": token.key
            }, status=status.HTTP_200_OK)
        
        return Response({"error": "Credenciales inválidas"}, status=status.HTTP_400_BAD_REQUEST)


class ConversationListView(generics.ListCreateAPIView):
    """
    Vista para listar las conversaciones del usuario autenticado y crear nuevas.
    """
    serializer_class = ConversationSerializer
    
    def get_queryset(self):        
        return Conversation.objects.filter(participants=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):        
        conversation = serializer.save()
                
        conversation.participants.add(self.request.user)
                
        invited_usernames = self.request.data.get('invited_username', '')
        
        if invited_usernames:            
            username_list = [name.strip() for name in invited_usernames.split(',') if name.strip()]
                        
            invited_users = User.objects.filter(username__in=username_list)
            
            if invited_users.exists():                
                conversation.participants.add(*invited_users)

class AddParticipantView(generics.UpdateAPIView):
    
    queryset = Conversation.objects.all()
    
    def update(self, request, *args, **kwargs):
        conversation = self.get_object()
        username_to_add = request.data.get('username')

        if not username_to_add:
            return Response({"error": "Se requiere el nombre de usuario ('username')."}, status=status.HTTP_400_BAD_REQUEST)

        try:            
            user_to_add = User.objects.get(username=username_to_add)            
            
            if user_to_add in conversation.participants.all():
                return Response({"message": f"El usuario {username_to_add} ya está en la conversación."}, status=status.HTTP_200_OK)
            
            conversation.participants.add(user_to_add)
            conversation.save()            

            return Response({"message": f"Usuario {username_to_add} añadido exitosamente."}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": f"El usuario '{username_to_add}' no existe."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:            
            print(f"Error al añadir participante: {e}") 
            return Response({"error": "Ocurrió un error al procesar la solicitud."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)