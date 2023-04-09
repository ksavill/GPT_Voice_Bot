# import openai

import pyaudio
import requests
import json
from dearpygui import dearpygui as dpg

import sys
import threading
import re
import speech_recognition
import pyttsx3
import datetime

# Initialize OpenAI API
api_key = "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"
speaking = False

callingName = "Vega"
selectedModel = "gpt-3.5-turbo"
immediateQuestion = ""
globalWidth = 800
globalHeight = 800

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

def offline_response(text):

    # turn off mic listening
    if text == "stop listening":
        dpg.set_value("allow_microphone_input", False)
        return "Turning off microphone input"
    
    # get the current date
    if text == "what date is it" or text == "what is the date":
        date = datetime.datetime.now()
        formatted_date = date.strftime("%A, %B %d, %Y")
        return f"Today is {formatted_date}"
    
    # get the current time
    if text == "what time is it" or text == "what is the time":
        time = datetime.datetime.now()
        formatted_time = time.strftime("%I:%M %p")
        return f"The current time is {formatted_time}"
    

    # catch all
    return ""

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

def extract_code_and_text(text):
    code_blocks = re.findall(r'```(.*?)```', text, re.DOTALL)
    non_code_text = re.sub(r'```(.*?)```', '', text, flags=re.DOTALL).strip()

    return non_code_text, code_blocks

def speak_text(text):
    global speaking, immediateQuestion
    dpg.set_value("last_response", text)
    speaking = True
    stop_listener_thread = threading.Thread(target=listen_for_stop)
    stop_listener_thread.start()

    non_code_text, code_blocks = extract_code_and_text(text)

    # Print the code blocks to the console
    if code_blocks:
        print("\nCode output detected. I will not read it out loud, but here it is:\n")
        for code_block in code_blocks:
            print(f"{code_block.strip()}\n")

    # Split the non-code text into words and create a list to store blocks of 10 words max
    words = non_code_text.split()
    text_blocks = []

    # Break the words into blocks of 10 words max
    for i in range(0, len(words), 8):
        text_block = " ".join(words[i:i+8])
        text_blocks.append(text_block)

    # Call engine.say() for each block of words in the list
    for text_block in text_blocks:
        if speaking == True:
            engine.say(text_block)
            engine.runAndWait()
        else:
            break

    speaking = False
    stop_listener_thread.join()

    if immediateQuestion:
        request_text = immediateQuestion
        immediateQuestion = ""
        process_request(request_text)

def listen_for_stop():
    global speaking, immediateQuestion
    print("listening for stop")
    stopSaid = False
    while speaking and dpg.get_value("allow_microphone_input"):
        with speech_recognition.Microphone() as source:
            recognizer = speech_recognition.Recognizer()
            recognizer.pause_threshold = 0.5
            try:
                audio = recognizer.listen(source, timeout=1)
                transcription = recognizer.recognize_google(audio)
                print(f"You said: {transcription}")
                if "stop" in transcription.lower():
                    speaking = False
                    stopSaid = True
                    print("stopping text output")
                    break
            except speech_recognition.WaitTimeoutError:
                pass
            except Exception as e:
                print("An error occurred: {}".format(e))
    print("no longer listening for stop")
    if stopSaid == True and len(transcription.lower()) > 4:
        print("placeholder for stop and another likely question has been spoken.")
        text = transcription.lower()
        immediateQuestion = text.replace("stop", "", 1).strip()

def process_request(request_text):
    # update you_said
    dpg.set_value("you_said", request_text)
    # offline input checks
    response = offline_response(request_text)
    if response:
        speak_text(response)
        return
    
    # openai gpt 
    response = generate_response(request_text)
    print(f"GPT says: {response}")
    if response:
        speak_text(response)
        return
    
    # catch-all speak text.
    response = "No valid response given."
    speak_text(response)

def record_question():
    if dpg.get_value("allow_microphone_input") == False:
        return
    speak_text(f"Say {callingName} to ask your question")
    print(f"Say {callingName} to ask your question")
    global conversation_history
    while dpg.get_value("allow_microphone_input"):
        
        with speech_recognition.Microphone() as source:
            recognizer = speech_recognition.Recognizer()
            audio = recognizer.listen(source)
            try:
                transcription = recognizer.recognize_google(audio)
                print(f'You said: {transcription}')
                if callingName.lower() in transcription.lower():
                    while dpg.get_value("allow_microphone_input"):
                        speak_text("Say your question")
                        print("Say your question (or 'end' to stop asking)")
                        with speech_recognition.Microphone() as source:
                            recognizer = speech_recognition.Recognizer()
                            source.pause_threshold = 1
                            audio = recognizer.listen(source, timeout=30)
                            try:
                                text = recognizer.recognize_google(audio)
                                text = text.lower()
                                if text == "stop conversation":
                                    speak_text("Breaking from thead.")
                                    break

                                # Check if there are more than 2 words
                                if len(text.split()) >= 2:
                                    print(f"You said: {text}")

                                    process_request(text)
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

def UpdateCallingName():
    global callingName
    inputName = dpg.get_value("callingName")
    if len(inputName) > 2:
        callingName = dpg.get_value("callingName")
        speak_text(f"Wake word updated to {callingName}")
    else:
        speak_text("Invalid name input.")

def UpdateSelectedModel():
    global selectedModel
    selectedModel = dpg.get_value("selectedModel")
    speak_text(f"Selected Model has been updated to {selectedModel}")

def main():
    global callingName

    # Create the GUI
    with dpg.window(label="Voice Assistant", width=globalWidth, height=globalHeight):
        dpg.add_checkbox(label="Allow microphone input", default_value=False, tag="allow_microphone_input", callback=record_question)
        with dpg.group(horizontal=True):
            dpg.add_text("Calling word: ")
            dpg.add_input_text(tag="callingName", default_value=callingName, width=100, on_enter=True, callback=UpdateCallingName)
            dpg.add_button(label="Update Calling Name", callback=UpdateCallingName)
        dpg.add_text("Select Chat Model")
        dpg.add_radio_button(['gpt-3.5-turbo','whisper-1','text-davinci-003'], tag="selectedModel", default_value="gpt-3.5-turbo", callback=UpdateSelectedModel)
    
        dpg.add_text("You said:")
        dpg.add_text(tag="you_said")
        dpg.add_text("\n\n")
        dpg.add_text("Last response:")
        dpg.add_text(tag="last_response")
    

if __name__ == "__main__":
    dpg.create_context()
    dpg.create_viewport(title="GPT Voice Assistant GUI", width=globalWidth, height=globalHeight)
    dpg.setup_dearpygui()


    main()

    #this goes at the very end of the script
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()