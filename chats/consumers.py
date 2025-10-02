import json
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.layers import get_channel_layer
import redis
import time
import os

api_logger = logging.getLogger('api_logger')

THROTTLE_RATE = 5      
THROTTLE_PERIOD = 10   

REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379)) 


r = None 
try:
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    r.ping()    
    api_logger.info(f"REDIS: Direct Redis connection for throttling and history established at {REDIS_HOST}:{REDIS_PORT}.")
except redis.exceptions.ConnectionError as e:    
    api_logger.error(f"REDIS: Could not connect to Redis at {REDIS_HOST}:{REDIS_PORT}. Error: {e}")


class ChatConsumer(AsyncJsonWebsocketConsumer):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)        
        self.channel_layer = get_channel_layer()

    async def check_throttle(self, user_key):
        """Checks if the user has exceeded the message limit in the period."""
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


    async def connect(self):
        """Handles the WebSocket connection, checks authentication, and joins the group."""
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        user = self.scope['user'].username         
        
        if not self.scope['user'].is_authenticated:             
            await self.close(code=4000)            
            api_logger.warning(f"WS CONNECTION DENIED (4000): Anonymous user tried to connect to {self.room_name}")
            return         
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )         
        
        await self.accept()
        
        api_logger.info(f"WS CONNECTION ACCEPTED: User {user} connected to {self.room_name}")
                
        if r:
            history = r.lrange(self.room_group_name, 0, -1)
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
        
        if r:
            r.rpush(self.room_group_name, json.dumps(msg_data))             # Store message in Redis
            r.ltrim(self.room_group_name, -100, -1) # Keep only the last 100 messages
                
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