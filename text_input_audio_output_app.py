import pyttsx3
import requests
import json

# Initialize OpenAI API
api_key = "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"
selectedModel = "gpt-3.5-turbo"

# Initialize the text to speech engine
engine = pyttsx3.init()

conversation_history = []

def generate_response(prompt):
    global conversation_history
    conversation_history.append({"role": "user", "content": prompt})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    data = {
        "model": selectedModel,
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

def main():
    while True:
        user_input = input("You: ")
        response = generate_response(user_input)
        print(f"GPT says: {response}")
        speak_text(response)

if __name__ == "__main__":
    main()