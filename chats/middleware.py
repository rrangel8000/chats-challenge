import urllib.parse
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
import logging
from rest_framework.authtoken.models import Token 

api_logger = logging.getLogger('api_logger')
User = get_user_model()

@database_sync_to_async
def get_user_by_token(token_key):
    """
    Busca el usuario asociado a la clave de token proporcionada
    utilizando el modelo Token de Django REST Framework.
    """
    if not token_key:
        return AnonymousUser()
        
    try:        
        token = Token.objects.select_related('user').get(key=token_key)
                
        return token.user
        
    except Token.DoesNotExist:        
        api_logger.warning(f"WS AUTH FAILED: Invalid token key provided: {token_key}")
        return AnonymousUser()
    except Exception as e:
        api_logger.error(f"WS AUTH ERROR: Unexpected error during token lookup: {e}")
        return AnonymousUser()


class QueryStringTokenAuthMiddleware:
    """
    Middleware que lee el token de la query string (ws://.../?token=xyz)
    y lo usa para autenticar al usuario.
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):        
        if scope['type'] == 'websocket':
            try:                
                query_string = scope['query_string'].decode()
                params = urllib.parse.parse_qs(query_string)                
                
                token_key = params.get('token', [None])[0]
                                
                scope['user'] = await get_user_by_token(token_key)
                
            except Exception as e:                
                api_logger.error(f"Error general en QueryStringTokenAuthMiddleware: {e}")
                scope['user'] = AnonymousUser()
        
        return await self.inner(scope, receive, send)

def QueryStringTokenAuthMiddlewareStack(inner):
    return QueryStringTokenAuthMiddleware(AuthMiddlewareStack(inner))