# urls.py (in your twilio_bot app)
from django.urls import path
from .views import MakeCallView, VoiceAssistantView, DebugView,get_menu_by_twilio_number
from . import views

urlpatterns = [
    path('make-call/', MakeCallView.as_view(), name='make-call'),
    path('voice-assistant/', VoiceAssistantView.as_view(), name='voice-assistant'),
    path('debug/', DebugView.as_view(), name='debug'),
    path('get-menu-by-twilio/', get_menu_by_twilio_number, name='get_menu_by_twilio'),
    path('chat/', views.chat_view, name='chat'),
    path('chat/<str:session_id>/', views.chat_view, name='chat_with_session'),
    path('api/conversations/', views.ConversationListCreateView.as_view()),
    path('api/conversations/<str:session_id>/messages/', views.MessageListView.as_view(), name='message-list'),
]