# your_app/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/audio_chat/(?P<session_id>[^/]+)/$', consumers.AudioConversationConsumer.as_asgi()),
]