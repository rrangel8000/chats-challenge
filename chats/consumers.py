import json
import logging
import time
import os
import redis
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async 

api_logger = logging.getLogger('api_logger')

THROTTLE_RATE = 5
THROTTLE_PERIOD = 10


REDIS_HOST = os.environ.get('REDIS_HOST', 'redis') 
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379)) 


def get_redis_client():    
    try:
        r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
        r.ping()    
        api_logger.info(f"REDIS: Direct Redis client ready at {REDIS_HOST}:{REDIS_PORT}.")
        return r
    except redis.exceptions.ConnectionError as e:    
        api_logger.error(f"REDIS: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Error: {e}")
        return None

r = get_redis_client()

@database_sync_to_async
def _sync_check_throttle(user_key):    
    if not r:
        return False
        
    key = f"throttle:{user_key}"
    now = time.time()
            
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, '-inf', now - THROTTLE_PERIOD)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, THROTTLE_PERIOD)
    pipe.zcard(key)
    
    results = pipe.execute()
    count = results[-1]
    
    return count > THROTTLE_RATE


@database_sync_to_async
def _sync_get_history(room_group_name):    
    if r:        
        return r.lrange(room_group_name, 0, -1)
    return []


@database_sync_to_async
def _sync_save_message(room_group_name, msg_data):    
    if r:        
        r.rpush(room_group_name, json.dumps(msg_data))
        r.ltrim(room_group_name, -100, -1) 


class ChatConsumer(AsyncJsonWebsocketConsumer):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_layer = get_channel_layer()

    async def check_throttle(self, user_key):        
        return await _sync_check_throttle(user_key) 

    async def connect(self):
        """Handles the WebSocket connection, checks authentication, and joins the group."""
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
                
        user = self.scope['user']
        
        if not user.is_authenticated:             
            await self.close(code=4000)
            api_logger.warning(f"WS CONNECTION DENIED (4000): Anonymous user tried to connect to {self.room_name}")
            return
        
        user_name = user.username
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )        
        
        await self.accept()
        
        api_logger.info(f"WS CONNECTION ACCEPTED: User {user_name} connected to {self.room_name}")
                        
        history = await _sync_get_history(self.room_group_name)
        
        for message in history:
            try:
                await self.send_json(json.loads(message))
            except json.JSONDecodeError:
                api_logger.error(f"Error decoding Redis history for {self.room_group_name}: {message}")


    async def receive_json(self, content):
        """Receives the client message, applies throttling, and distributes it."""
        message = content.get('message', '').strip()
        user = self.scope['user'].username
        
        api_logger.info(f"WS MESSAGE RECEIVED: User {user} sent message (len: {len(message)}) to room {self.room_group_name}.")

        if not message:
            return        
        
        if await self.check_throttle(user): 
            api_logger.warning(f"THROTTLED: User {user} exceeded message limit in room {self.room_group_name}.")
            
            await self.send_json({"error": f"Too many messages. Limit: {THROTTLE_RATE} per {THROTTLE_PERIOD}s."})
            return
        
        msg_data = {
            'user': user,
            'message': message,
            'timestamp': time.time(),
            'type': 'new_message' 
        } 
                
        await _sync_save_message(self.room_group_name, msg_data)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat.message', 
                'message_data': msg_data
            }
        )
        api_logger.info(f"MESSAGE BROADCAST: User {user} message broadcasted successfully in {self.room_group_name}.")

    
    async def chat_message(self, event):
        """Function to handle the message received from the group."""     
        await self.send_json(event['message_data'])

    async def disconnect(self, close_code):
        """Handles the WebSocket disconnection."""     
        user = self.scope['user'].username
        api_logger.info(f"WS DISCONNECTED: User {user} left room {self.room_group_name} with code {close_code}.")
        
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )