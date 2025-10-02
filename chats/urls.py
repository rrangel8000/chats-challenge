from django.urls import path
from .views import IndexView, SignUpView, LoginView, ConversationListView, AddParticipantView

urlpatterns = [    
    path('', IndexView.as_view(), name='index'), 
        
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'), 
    path('conversations/', ConversationListView.as_view(), name='conversation_list'),
        
    path('conversations/<int:pk>/add_participant/', AddParticipantView.as_view(), name='add_participant'),
]