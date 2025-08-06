import json
import asyncio
import logging
import speech_recognition as sr
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone
from asgiref.sync import sync_to_async
from .models import Conversation, Message
from .utils import transcribe_audio, generate_llm_response, text_to_speech

logger = logging.getLogger(__name__)

class AudioConversationConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.recognizer = sr.Recognizer()
        self.conversation_history = [
            {"role": "system", "content": "You are a helpful assistant."}
        ]
        self.conversation_obj = None
        self.audio_buffer = bytearray()
        self.expected_audio_length = 0
        self.is_receiving_audio = False

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        try:
            self.conversation_obj = await sync_to_async(self.get_or_create_conversation)()
            await self.accept()
            await self.send_system_message(
                'connection_established',
                'You are now connected!'
            )
            logger.info(f"WebSocket connected for session {self.session_id}")
        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            await self.close(code=4000)

    def get_or_create_conversation(self):
        conversation, created = Conversation.objects.get_or_create(
            session_id=self.session_id,
            defaults={'created_at': timezone.now()}
        )
        return conversation

    async def disconnect(self, close_code):
        logger.info(f"WebSocket disconnected for session {self.session_id} with code {close_code}")
        if self.conversation_obj:
            await sync_to_async(self.conversation_obj.save)()

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if text_data:
                await self.handle_text_message(text_data)
            elif bytes_data:
                await self.handle_binary_data(bytes_data)
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send_error_message(str(e))

    async def handle_text_message(self, text_data):
        """Handle incoming text messages"""
        try:
            data = self.validate_and_parse_json(text_data)
            
            if data['type'] == 'heartbeat':
                await self.send_heartbeat_ack()
            elif data['type'] == 'start_audio':
                await self.handle_start_audio(data)
            elif data['type'] == 'end_audio':
                await self.handle_end_audio()
            else:
                raise ValueError(f"Unsupported message type: {data['type']}")
                
        except Exception as e:
            raise ValueError(f"Text message handling error: {str(e)}")

    async def handle_binary_data(self, binary_data):
        """Handle incoming binary audio data"""
        if not self.is_receiving_audio:
            raise ValueError("Received audio data without start_audio message")
        
        self.audio_buffer.extend(binary_data)
        if len(self.audio_buffer) >= self.expected_audio_length:
            await self.process_complete_audio()

    async def handle_start_audio(self, data):
        """Initialize audio reception"""
        if 'length' not in data:
            raise ValueError("Missing audio length in start_audio message")
        
        self.is_receiving_audio = True
        self.expected_audio_length = data['length']
        self.audio_buffer = bytearray()
        await self.send_system_message('audio_reception_started', 'Ready to receive audio')

    async def handle_end_audio(self):
        """Finalize audio reception"""
        if not self.is_receiving_audio:
            raise ValueError("Received end_audio without start_audio")
        
        if len(self.audio_buffer) < self.expected_audio_length:
            raise ValueError(f"Expected {self.expected_audio_length} bytes, got {len(self.audio_buffer)}")
        
        await self.process_complete_audio()

    async def process_complete_audio(self):
        """Process complete audio buffer"""
        try:
            # Reset audio state first in case of errors
            self.is_receiving_audio = False
            audio_data = bytes(self.audio_buffer)
            self.audio_buffer = bytearray()
            
            # Transcribe audio
            text_input = await asyncio.to_thread(
                transcribe_audio,
                audio_data
            )
            
            # Add to conversation history
            self.conversation_history.append(
                {"role": "user", "content": text_input}
            )
            
            # Save message to database
            user_message = await sync_to_async(Message.objects.create)(
                conversation=self.conversation_obj,
                text_input=text_input,
                text_response="",
                created_at=timezone.now()
            )
            
            # Get and stream LLM response
            full_response = await self.process_llm_response()
            
            # Update database with full response
            user_message.text_response = full_response
            await sync_to_async(user_message.save)()
            
            # Convert and send audio response
            await self.send_audio_response(full_response)
            
        except Exception as e:
            logger.error(f"Audio processing error: {str(e)}")
            raise

    async def process_llm_response(self):
        """Get and stream LLM response"""
        response_stream = await asyncio.to_thread(
            generate_llm_response,
            self.conversation_history
        )
        
        full_response = ""
        async for chunk in response_stream:
            if 'content' in chunk.choices[0].delta:
                chunk_content = chunk.choices[0].delta['content']
                full_response += chunk_content
                await self.send_text_chunk(chunk_content)
        
        self.conversation_history.append(
            {"role": "assistant", "content": full_response}
        )
        return full_response

    async def send_audio_response(self, text):
        """Convert text to speech and send audio chunks"""
        audio_buffer = await asyncio.to_thread(
            text_to_speech,
            text
        )
        
        # First send audio metadata
        await self.send_system_message(
            'start_audio_response',
            {'length': len(audio_buffer.getvalue())}
        )
        
        # Then send audio chunks
        chunk_size = 4096
        audio_buffer.seek(0)
        while True:
            chunk = audio_buffer.read(chunk_size)
            if not chunk:
                break
            await self.send(bytes_data=chunk)
        
        # Signal end of audio
        await self.send_system_message('end_audio_response', 'Audio transmission complete')

    # Helper methods for standardized messaging
    async def send_system_message(self, message_type, content):
        """Send a standardized system message"""
        await self.send(text_data=json.dumps({
            'type': message_type,
            'content': content,
            'timestamp': timezone.now().isoformat()
        }))

    async def send_error_message(self, error_message):
        """Send a standardized error message"""
        await self.send_system_message('error', error_message)

    async def send_text_chunk(self, text_chunk):
        """Send a text chunk from LLM"""
        await self.send_system_message('text_chunk', text_chunk)

    async def send_heartbeat_ack(self):
        """Acknowledge heartbeat"""
        await self.send_system_message('heartbeat_ack', 'Heartbeat received')

    # Validation utilities
    def validate_and_parse_json(self, text_data):
        """Validate and parse incoming JSON"""
        text_data = text_data.strip()
        if not text_data:
            raise ValueError("Empty message received")
        
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")
        
        if not isinstance(data, dict):
            raise ValueError("Message must be a JSON object")
        
        if 'type' not in data:
            raise ValueError("Message must contain 'type' field")
        
        return data