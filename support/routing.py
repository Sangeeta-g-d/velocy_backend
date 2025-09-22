# routing.py
from django.urls import re_path
from . import consumers
from .consumers import SupportChatConsumer

websocket_urlpatterns = [
    re_path(r'^ws/support/(?P<chat_id>\w+)/$', SupportChatConsumer.as_asgi()),
]
