# import openai
import speech_recognition
import pyttsx3
import pyaudio
import requests
import json
from dearpygui import dearpygui as dpg
import sys

# Initialize OpenAI API
api_key = "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"

# Initialize the text to speech engine
engine = pyttsx3.init()

conversation_history = []

def transcribe_audio_to_text(filename):
    recognizer = speech_recognition.Recognizer()
    with speech_recognition.AudioFile(filename) as source:
        audio = recognizer.record(source)
    try:
        return recognizer.recognize_google(audio)
    except:
        print("Skipping unknown error")


def generate_response(prompt):
    global conversation_history
    conversation_history.append({"role": "user", "content": prompt})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    data = {
        "model": "gpt-3.5-turbo",
        "messages": conversation_history,
        "max_tokens": 300,
        "n": 1,
        "stop": None,
        "temperature": 0.5,
    }

    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    response_json = response.json()

    if 'choices' in response_json:
        response_text = response_json["choices"][0]["message"]["content"].strip()
        conversation_history.append({"role": "assistant", "content": response_text})
        return response_text
    else:
        raise Exception(f"An error occurred: {response_json}")

def speak_text(text):
    engine.say(text)
    engine.runAndWait()

def record_question():
    if dpg.get_value("allow_microphone_input") == False:
        return
    speak_text("Say vega to start recording your question")
    print("Say 'vega' to start recording your question")
    global conversation_history
    while dpg.get_value("allow_microphone_input"):
        # Wait for user to say "vega"
        
        with speech_recognition.Microphone() as source:
            recognizer = speech_recognition.Recognizer()
            audio = recognizer.listen(source)
            try:
                transcription = recognizer.recognize_google(audio)
                print(f'You said: {transcription}')
                if "vega" in transcription.lower():
                    while dpg.get_value("allow_microphone_input"):
                        # Record audio
                        filename = "input.wav"
                        speak_text("Say your question")
                        print("Say your question (or 'end' to stop asking)")
                        with speech_recognition.Microphone() as source:
                            recognizer = speech_recognition.Recognizer()
                            source.pause_threshold = 1
                            audio = recognizer.listen(source, timeout=30)
                            try:
                                text = recognizer.recognize_google(audio)
                                if text.lower() == "end conversation":
                                    break

                                # Check if there are more than 2 words
                                if len(text.split()) >= 2:
                                    print(f"You said: {text}")

                                    # Generate the response
                                    response = generate_response(text)
                                    print(f"GPT says: {response}")

                                    # Speak the response using text-to-speech
                                    speak_text(response)
                                    speak_text("now follow-up")
                                else:
                                    speak_text("Not enough words.")
                                    print("Not enough words.")
                                
                            except speech_recognition.WaitTimeoutError:
                                speak_text("Timeout reached, waiting for vega again.")
                                print("Timeout reached, waiting for 'vega' again.")
                                break
                            except Exception as e:
                                print(f'An error occurred: {e}')
                                break
                elif transcription.lower() == "terminate program":
                    speak_text("Terminating Program. Goodbye.")
                    print("Terminating Program. Goodbye.")
                    sys.exit()
            except Exception as e:
                # speak_text("An Error occurred.")
                print(f'Could not transcribe to text.')
    speak_text("Voice listening ended.")
    print("Voice listening ended.")

def main():
    
    # Create the GUI
    with dpg.window(label="Voice Assistant", width=250, height=250):
        dpg.add_checkbox(label="Allow microphone input", default_value=False, id="allow_microphone_input", callback=record_question)
    

if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport(title="GPT Voice Assistant GUI", width=-1, height=-1)
    dpg.setup_dearpygui()


    main()

    #this goes at the very end of the script
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()