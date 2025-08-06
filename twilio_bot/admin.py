from django.contrib import admin
from .models import Conversation, Message   


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'created_at', 'updated_at')
    search_fields = ('session_id',)
    ordering = ('-created_at',) 


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'text_input', 'text_response', 'created_at')
    search_fields = ('text_input', 'text_response')
    ordering = ('-created_at',)
    list_filter = ('created_at',)
    raw_id_fields = ('conversation',)



    