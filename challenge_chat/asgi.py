import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'challenge_chat.settings')

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from chats import routing
from chats.middleware import QueryStringTokenAuthMiddlewareStack 


application = ProtocolTypeRouter({    
    "http": django_asgi_app,    
    
    "websocket": QueryStringTokenAuthMiddlewareStack(
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})
