from rest_framework import authentication
from rest_framework import exceptions
from django.contrib.auth.models import User

class AllowDummyTokenAuthentication(authentication.BaseAuthentication):
    
    def authenticate(self, request):        
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return None         
        
        parts = auth_header.split()

        if parts[0].lower() != 'token' or len(parts) != 2:
            return None 

        token = parts[1]        
        
        if not token.startswith('dummy-auth-token-'):
            return None 
        
        try:
            username = token.split('dummy-auth-token-')[1]
        except IndexError:
            raise exceptions.AuthenticationFailed('Malformed dummy authentication token.')
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User associated with the dummy token not found.')
                    
        return (user, token)