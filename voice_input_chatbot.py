import re
import speech_recognition
import os
import datetime

from chatbot.openai_handler import OpenAIHandler
from chatbot.tts import TTS

# Initialize OpenAI API and TTS
api_key = os.environ.get("openai_token")
if not api_key:
    raise Exception("OpenAI API key not found in environment variable 'openai_token'.")

chatbot = OpenAIHandler(api_key=api_key, model="gpt-4o-mini")
tts = TTS()

speaking = False

# Function to check offline responses (date/time)
def offline_response(text):
    # Get the current date
    if text == "what date is it" or text == "what is the date":
        date = datetime.datetime.now()
        formatted_date = date.strftime("%A, %B %d, %Y")
        return f"Today is {formatted_date}"
    
    # Get the current time
    if text == "what time is it" or text == "what is the time":
        time = datetime.datetime.now()
        formatted_time = time.strftime("%I:%M %p")
        return f"The current time is {formatted_time}"
    
    # Catch-all for unhandled offline responses
    return ""

# Function to speak and listen for stop command
def speak_text(text):
    global speaking
    speaking = True

    non_code_text, code_blocks = extract_code_and_text(text)

    # Print the code blocks to the console
    if code_blocks:
        print("\nCode output detected. I will not read it out loud, but here it is:\n")
        for code_block in code_blocks:
            print(f"{code_block.strip()}\n")

    tts.speak(non_code_text)  # Using TTS from chatbot module

    speaking = False

def extract_code_and_text(text):
    code_blocks = re.findall(r'```(.*?)```', text, re.DOTALL)
    non_code_text = re.sub(r'```(.*?)```', '', text, flags=re.DOTALL).strip()
    return non_code_text, code_blocks

# Handle requests, either offline or via GPT
def process_request(request_text):
    # Offline input checks
    response = offline_response(request_text)
    if response:
        speak_text(response)
        return
    
    # GPT response using OpenAIHandler from chatbot module
    response, finished = chatbot.generate_response(request_text)
    if response:
        print(f"GPT: {response}")
        speak_text(response)
    if finished:
        tts.speak("Conversation completed. Goodbye.")
        exit()

# Main function to continuously listen for voice input
def record_question():
    tts.speak("Hello, how may I help you?")
    while True:
        with speech_recognition.Microphone() as source:
            recognizer = speech_recognition.Recognizer()
            try:
                print("Listening...")
                audio = recognizer.listen(source)
                transcription = recognizer.recognize_google(audio)
                print(f'You said: {transcription}')
                process_request(transcription)
            except Exception as e:
                print(f'An error occurred: {e}')
                continue

if __name__ == "__main__":
    # Start listening loop on startup
    record_question()
