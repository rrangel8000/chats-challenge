from django.db import models
from django.contrib.auth.models import User

class Conversation(models.Model):
    
    name = models.CharField(max_length=128, unique=True)    
    participants = models.ManyToManyField(User, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Message(models.Model):     
    conversation = models.ForeignKey(Conversation, related_name='messages', on_delete=models.CASCADE)
    
    user = models.ForeignKey(User, related_name='messages', on_delete=models.CASCADE)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username}: {self.content[:20]}'

    class Meta:        
        ordering = ['timestamp']