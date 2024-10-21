**Overview**

This repository contains two Python applications: app.py and text_input_audio_output_app.py. Both applications utilize the OpenAI API to generate responses based on user input, and use text-to-speech to vocalize responses. app.py includes a GUI for voice interactions, while text_input_audio_output_app.py is a console-based application for text input and audio output.

**Prerequisites**

- Python 3.7 or higher
- OpenAI API key
- Required Python packages: 
  - pyaudio
  - requests
  - dearpygui
  - speechrecognition
  - pyttsx3
  - datetime
  - sounddevice

**Installation**
Clone the repository:

`git clone <repository_url>`

`cd <repository_directory>`

Install the required packages:

`pip install pyaudio requests dearpygui speech_recognition pyttsx3`

Set up the OpenAI API key:

Add your OpenAI API key to your environment variables:

`export openai_token=<your_openai_api_key>`

**Usage**

Running app.py

app.py provides a GUI for voice interaction with the OpenAI API.

Run the application:

`python app.py`

The GUI window will appear. You can enable microphone input, update the calling name, and select the chat model.

Speak the calling name to initiate a question, and the application will process your request and respond via text-to-speech.

**Key Features**

- Transcribe Audio to Text: Converts recorded audio to text using Google Speech Recognition.
- Offline Response: Provides offline responses for simple queries (date, time, stopping microphone input).
- OpenAI Response: Generates responses using the OpenAI API.
- Text-to-Speech: Vocalizes responses using pyttsx3.
- GUI: Provides a user-friendly interface for interaction.

**Running text_input_audio_output_app.py**
text_input_audio_output_app.py is a console-based application that takes text input from the user and provides audio output of the responses.

Run the application:

`python text_input_audio_output_app.py`

Enter your queries in the console. The application will generate responses using the OpenAI API and vocalize them using pyttsx3.

**Key Features**

- OpenAI Response: Generates responses using the OpenAI API.
- Text-to-Speech: Vocalizes responses using pyttsx3.
- Clear Conversation History: Enter "new chat" to clear the conversation history.

**Configuration**

- API Key: Ensure the OpenAI API key is set in your environment variables.
- Calling Name: Change the default calling name in the GUI or via the input field in the application.
- Chat Model: Select different OpenAI models from the GUI.
