import json
import pytest
import time
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from challenge_chat.asgi import application 
from chats.consumers import THROTTLE_RATE, THROTTLE_PERIOD 

from rest_framework.test import APIClient
from django.urls import reverse
from chats.models import Conversation

@pytest.fixture
def api_client():
    """Fixture for the REST API client."""
    return APIClient()

@pytest.fixture
def create_user():
    """Fixture to create a test user in the DB."""     
    def _create_user(username, password='testpassword'):
        return User.objects.create_user(username=username, password=password, email=f'{username}@test.com')
    return _create_user

@pytest.fixture
def authenticated_user(create_user):
    """Fixture that creates and authenticates a user for WS tests."""
    user = create_user('test_user')     
    scope = {'user': user} 
    return user, scope

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_websocket_connect_and_disconnect(authenticated_user):
    """Tests that a client connects and disconnects correctly."""
    user, scope = authenticated_user     
    
    communicator = WebsocketCommunicator(application, "/ws/chat/test_room/", scope=scope)
    connected, subprotocol = await communicator.connect()
    
    assert connected
    await communicator.disconnect()

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_chat_message_distribution(authenticated_user):
    """Tests that a message is sent and received by another client."""
    user1, scope1 = authenticated_user
    user2, scope2 = authenticated_user     
    
    communicator1 = WebsocketCommunicator(application, "/ws/chat/room_a/", scope=scope1)
    await communicator1.connect()
    
    communicator2 = WebsocketCommunicator(application, "/ws/chat/room_a/", scope=scope1) 
    await communicator2.connect()     
    
    await communicator1.receive_nothing()
    await communicator2.receive_nothing()     
    
    test_message = "Distribution Test"
    await communicator1.send_json_to({
        "message": test_message,
    })
    
    response2 = await communicator2.receive_json_from()
    
    assert response2['message'] == test_message
    assert response2['user'] == user1.username
    assert response2['type'] == 'new_message'

    await communicator1.disconnect()
    await communicator2.disconnect()

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_chat_throttling(authenticated_user):
    """Tests that the consumer applies the message rate limit."""
    user, scope = authenticated_user
    
    communicator = WebsocketCommunicator(application, "/ws/chat/throttle_room/", scope=scope)
    await communicator.connect()
    
    for i in range(THROTTLE_RATE):
        await communicator.send_json_to({"message": f"Message {i+1}"})         
        response = await communicator.receive_json_from()
        assert response['message'] == f"Message {i+1}"
        
    await communicator.send_json_to({"message": "Blocked message"})
        
    error_response = await communicator.receive_json_from()
    assert 'error' in error_response
    assert 'Too many messages' in error_response['error']
    
    await communicator.disconnect()


@pytest.mark.django_db
def test_signup_successful(api_client):
    """Tests the registration of a new user."""
    url = reverse('signup')
    data = {
        'first_name': 'Alejandro',
        'last_name': 'Test',
        'email': 'alejandro.test@email.com',
        'password': 'password1234'
    }
    response = api_client.post(url, data, format='json')
    assert response.status_code == 201
    assert User.objects.count() == 1
    assert 'user_id' in response.data

@pytest.mark.django_db
def test_conversation_creation(api_client, create_user):
    """Tests that only authenticated users can create conversations."""
    user1 = create_user('chat_user1')
    user2 = create_user('chat_user2')     
    
    api_client.force_authenticate(user=user1)
    
    url = reverse('conversation-list-create')
    data = {
        'name': 'My First Room',
        'participants': [user1.id, user2.id]
    }
    
    response = api_client.post(url, data, format='json')
    assert response.status_code == 201
    assert Conversation.objects.count() == 1
    
    conversation = Conversation.objects.first()
    assert conversation.name == 'My First Room'
    assert conversation.participants.count() == 2

@pytest.mark.django_db
def test_conversation_list_unauthenticated(api_client):
    """Tests that the conversation list requires authentication."""
    url = reverse('conversation-list-create')
    response = api_client.get(url)
    assert response.status_code == 403

@pytest.mark.django_db
def test_add_participant_to_conversation(api_client, create_user):
    """Tests adding a participant to an existing conversation."""
    user_owner = create_user('owner')
    new_participant = create_user('new_guy')
        
    conversation = Conversation.objects.create(name="Test Room")
    conversation.participants.add(user_owner)
        
    api_client.force_authenticate(user=user_owner)
        
    url = reverse('add_participant', kwargs={'pk': conversation.pk})
    data = {'user_id': new_participant.id}
    
    response = api_client.post(url, data, format='json')
        
    assert response.status_code == 200
    assert 'status' in response.data
    assert 'Participant added' in response.data['status']
        
    conversation.refresh_from_db()
    assert conversation.participants.count() == 2
    assert new_participant in conversation.participants.all()