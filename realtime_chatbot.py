import os
import json
import asyncio
import websockets
import base64
import sounddevice as sd
import numpy as np
import re
from typing import Dict, Any

class OpenAIHandlerRealtime:
    def __init__(self, api_key):
        self.api_key = api_key
        self.ws = None
        self.audio_queue = asyncio.Queue()
        self.playback_lock = asyncio.Lock()
        self.model = 'gpt-4o-realtime-preview-2024-10-01'

        # Define functions and function_map
        self.functions = [
            {
                "name": "CreateTicket",
                "description": "Creates a support ticket with the provided user details and issue description.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The name of the user."
                        },
                        "email": {
                            "type": "string",
                            "description": "The user's email address."
                        },
                        "issue": {
                            "type": "string",
                            "description": "Description of the issue."
                        },
                        "contact_number": {
                            "type": "string",
                            "description": "The user's contact number (optional)."
                        }
                    },
                    "required": ["name", "email", "issue"]
                }
            }
        ]
        self.function_map = {
            "CreateTicket": CreateTicket
        }

    async def connect(self):
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }
        print(f"Connecting to {url} with headers {headers}")
        try:
            self.ws = await websockets.connect(url, extra_headers=headers)
            print("Connected to OpenAI Realtime API.")
            # Initialize the conversation
            await self.initialize_conversation()
            # Start listening to incoming messages
            asyncio.create_task(self.listen())
            # Start sending audio from the queue
            asyncio.create_task(self.send_audio_stream())
        except Exception as e:
            print(f"Failed to connect to OpenAI Realtime API: {e}")

    async def initialize_conversation(self):
        event = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "instructions": "You are a helpful assistant.",
                "voice": "alloy",
                "tools": self.functions,  # Provide function definitions
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "enabled": True,  # Ensure transcription is enabled
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
            }
        }
        await self.ws.send(json.dumps(event))
        print("Initialized conversation with function definitions.")

    async def listen(self):
        try:
            async for message in self.ws:
                print(f"Received message from WebSocket: {message}")
                event = json.loads(message)
                await self.handle_event(event)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")
        except Exception as e:
            print(f"Error while listening to messages: {e}")

    async def handle_event(self, event: Dict[str, Any]):
        print(f"Handling event: {json.dumps(event, indent=2)}")
        if 'error' in event:
            print(f"Error from server: {event['error']}")
            return

        event_type = event.get("type")
        if event_type == "conversation.item.created":
            print("Event is conversation.item.created.")
            item = event.get("item", {})
            item_type = item.get("type")
            print(f"Item type: {item_type}")

            if item_type == "message":
                role = item.get("role")
                content = item.get("content", [])
                print(f"Message role: {role}")
                print(f"Message content: {content}")

                for content_piece in content:
                    content_type = content_piece.get("type")
                    print(f"Content type: {content_type}")

                    if content_type == "input_audio":
                        transcript = content_piece.get("transcript")
                        print(f"Received transcript: {transcript}")
                        if transcript:
                            print(f"User said: {transcript}")
                        else:
                            print("No transcript received.")

                    elif content_type == "output_audio":
                        assistant_audio = content_piece.get("audio")
                        if assistant_audio:
                            print("Received assistant audio. Playing audio response.")
                            await self.play_audio_response(assistant_audio)

                    elif content_type == "output_text":
                        text = content_piece.get("text")
                        print(f"Assistant said: {text}")

                    elif content_type == "function_call":
                        func_name = content_piece["function_call"]["name"]
                        func_args_str = content_piece["function_call"]["arguments"]
                        print(f"Received function call: {func_name} with arguments {func_args_str}")

                        try:
                            func_args = json.loads(func_args_str)
                        except json.JSONDecodeError as e:
                            print(f"Error decoding function arguments: {e}")
                            func_args = {}

                        await self.execute_function(func_name, func_args)
            else:
                print(f"Unhandled item type: {item_type}")

        elif event_type == "function_call_output":
            item = event.get("item", {})
            content = item.get("content", {})
            func_name = content.get("function_name")
            output = content.get("output")
            print(f"Received function call output for {func_name}: {output}")
            if "error" in output:
                print(f"Function '{func_name}' Error: {output['error']}")
            else:
                print(f"Function '{func_name}' Output: {output}")
            # Send the function output back to the assistant if necessary
            await self.send_function_output(func_name, output)

        elif event_type == "session.created":
            session_info = event.get("session", {})
            print(f"Session created with settings: {json.dumps(session_info, indent=2)}")

        elif event_type == "session.updated":
            session_info = event.get("session", {})
            print(f"Session updated with settings: {json.dumps(session_info, indent=2)}")

        else:
            print(f"Unhandled event type: {event_type}")

    async def execute_function(self, func_name: str, func_args: Dict[str, Any]):
        """
        Execute the specified function with the provided arguments and send the output.
        """
        function = self.function_map.get(func_name)
        if function:
            try:
                result = function(**func_args)
                print(f"Function '{func_name}' executed with result: {result}")
                await self.send_function_output(func_name, result)
            except Exception as e:
                print(f"Error executing function '{func_name}': {e}")
                await self.send_function_output(func_name, {"error": str(e)})
        else:
            print(f"Function '{func_name}' is not implemented.")
            await self.send_function_output(func_name, {"error": f"Function '{func_name}' is not implemented."})

    async def send_function_output(self, func_name: str, output: Dict[str, Any]):
        """
        Send the function's output back to the conversation.
        """
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "content": {
                    "function_name": func_name,
                    "output": output
                }
            }
        }
        try:
            await self.ws.send(json.dumps(event))
            print(f"Sent function output for '{func_name}': {output}")
        except Exception as e:
            print(f"Error sending function output: {e}")

    async def send_user_audio(self, audio_bytes):
        await self.audio_queue.put(audio_bytes)

    async def send_audio_stream(self):
        """
        Continuously send audio data from the queue to the Realtime API.
        """
        while True:
            audio_bytes = await self.audio_queue.get()
            if audio_bytes is None:
                break  # Exit signal
            print(f"Dequeued audio bytes of length {len(audio_bytes)} for sending.")
            try:
                # The audio_bytes are already in PCM16 format from the microphone
                pcm_base64 = base64.b64encode(audio_bytes).decode()
                print(f"Encoded audio to base64, length {len(pcm_base64)}.")

                event = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "message",
                        "role": "user",
                        "content": [
                            {
                                "type": "input_audio",
                                "audio": pcm_base64
                            }
                        ]
                    }
                }
                await self.ws.send(json.dumps(event))
                print("Sent audio input event to WebSocket.")
            except Exception as e:
                print(f"Error sending audio: {e}")

    async def play_audio_response(self, audio_base64: str):
        """
        Decode and play the assistant's audio response.
        """
        try:
            print("Decoding assistant audio.")
            # Decode base64 audio
            audio_bytes = base64.b64decode(audio_base64)
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
            audio_array /= 32768.0  # Normalize to [-1, 1]
            print(f"Playing audio of length {len(audio_array)} samples.")
            async with self.playback_lock:
                sd.play(audio_array, samplerate=24000)
                sd.wait()
                print("Finished playing assistant's audio response.")
        except  Exception as e:
            print(f"Error playing audio response: {e}")

async def audio_capture(handler: OpenAIHandlerRealtime, loop: asyncio.AbstractEventLoop):
    """
    Capture audio from the default microphone and send it to the handler.
    """
    samplerate = 24000  # 24kHz
    channels = 1  # Mono
    blocksize = 2400  # Increase blocksize to send larger chunks (0.1 sec of audio)

    print("Starting audio capture. Speak into the microphone...")

    def callback(indata, frames, time_info, status):
        if status:
            print(f"Audio Status: {status}")
        print(f"Captured audio chunk with {frames} frames.")
        # Convert to bytes and enqueue
        audio_bytes = indata.copy().tobytes()
        print(f"Enqueuing audio bytes of length {len(audio_bytes)}.")
        asyncio.run_coroutine_threadsafe(handler.send_user_audio(audio_bytes), loop)

    try:
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback, blocksize=blocksize):
            while True:
                await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        print("Audio capture stopped.")
    except Exception as e:
        print(f"Error in audio capture: {e}")


async def main():
    api_key = os.getenv("openai_token")
    if not api_key:
        print("Error: OpenAI API key not found. Please set the 'openai_token' environment variable.")
        return

    loop = asyncio.get_running_loop()
    handler = OpenAIHandlerRealtime(api_key=api_key)
    await handler.connect()
    audio_task = asyncio.create_task(audio_capture(handler, loop))

    try:
        await asyncio.Future()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        audio_task.cancel()
        await handler.ws.close()

def CreateTicket(name: str, email: str, issue: str, contact_number: str = None) -> Dict[str, Any]:
    """
    Creates a support ticket with the provided details.

    Parameters:
        name (str): The name of the user.
        email (str): The user's email address.
        issue (str): Description of the issue.
        contact_number (str, optional): The user's contact number.

    Returns:
        dict: A dictionary containing ticket details or an error message.
    """
    # Validate the email format
    email_regex = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
    if not re.match(email_regex, email):
        return {"error": "Invalid email format"}

    # Simulate ticket creation process (integrate with a real ticketing system)
    try:
        ticket = {
            "ticket_id": "12345",
            "name": name,
            "email": email,
            "issue": issue,
            "contact_number": contact_number,
            "status": "Open",
            "created_at": "2024-04-01T12:34:56Z"
        }
        print(f"Ticket Created: {ticket}")
        return ticket
    except Exception as e:
        print(f"Error creating ticket: {e}")
        return {"error": "Failed to make ticket"}

if __name__ == '__main__':
    asyncio.run(main())