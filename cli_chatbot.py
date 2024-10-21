import os
import sys
from chatbot.openai_handler import OpenAIHandler
from chatbot.tts import TTS

def main():
    api_key = os.environ.get("openai_token")
    if not api_key:
        print("Error: OpenAI API key not found in environment variable 'openai_token'.")
        sys.exit(1)

    chatbot = OpenAIHandler(api_key=api_key, model="gpt-4o-mini")
    tts = TTS()

    print("ChatBot CLI started. Type 'new chat' to reset conversation or 'exit' to quit.")
    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() == "new chat":
                chatbot.reset_conversation()
                tts.speak("Conversation cleared.")
                print("Conversation history has been cleared.")
                continue
            elif user_input.lower() in ["exit", "quit"]:
                print("Exiting ChatBot CLI.")
                break
            elif not user_input:
                continue
            response, finished = chatbot.generate_response(user_input)
            if response:
                print(f"GPT: {response}")
                tts.speak(response)
            if finished:
                tts.speak("Conversation completed. Goodbye.")
                exit()
        except KeyboardInterrupt:
            print("\nExiting ChatBot CLI.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            tts.speak("An error occurred. Please try again.")

if __name__ == "__main__":
    main()