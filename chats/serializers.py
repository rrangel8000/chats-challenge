from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Conversation, Message 

class SignUpSerializer(serializers.ModelSerializer):    
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        return user

class MessageSerializer(serializers.ModelSerializer):    
    user = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'user', 'content', 'timestamp')

class ConversationSerializer(serializers.ModelSerializer):
    
    participants_info = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ('id', 'name', 'participants_info', 'created_at')
        read_only_fields = ('created_at',)

    def get_participants_info(self, obj):     
        
        return [user.username for user in obj.participants.all()]