
import os
from rest_framework import authentication
from rest_framework import exceptions
from supabase import create_client, Client
from django.contrib.auth.models import User

class SupabaseAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        try:
            # Connect to Supabase
            url: str = os.environ.get("SUPABASE_URL")
            key: str = os.environ.get("SUPABASE_KEY")
            supabase: Client = create_client(url, key)

            # Verify token involves getting the user from Supabase
            # The token is passed as "Bearer <token>"
            token = auth_header.split(' ')[1]
            user_data = supabase.auth.get_user(token)
            
            if not user_data:
                raise exceptions.AuthenticationFailed('Invalid token')

            uid = user_data.user.id
            email = user_data.user.email

            # Create a transient user instance without saving to DB
            # We map Supabase UUID to username
            user = User(username=uid, email=email)
            # We explicitly set is_active to True, though it defaults to True
            user.is_active = True
            
            return (user, None)

        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Authentication failed: {str(e)}')
