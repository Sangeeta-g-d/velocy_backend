# support/middleware.py
from channels.middleware.base import BaseMiddleware
from channels.db import database_sync_to_async

class AdminAllowMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Simply allow connection with admin user
        from django.contrib.auth.models import AnonymousUser
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        # Example: attach a superuser for testing
        scope['user'] = await database_sync_to_async(user_model.objects.get)(is_superuser=True)
        return await super().__call__(scope, receive, send)
