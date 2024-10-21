import speech_recognition as sr
import logging

class SpeechRecognizer:
    def __init__(self, language="en-US", microphone_index=None):
        self.recognizer = sr.Recognizer()
        self.language = language
        self.microphone_index = microphone_index
        self.setup_microphone()

    def setup_microphone(self):
        mic_list = sr.Microphone.list_microphone_names()
        if not mic_list:
            logging.error("No microphones found. Please connect a microphone.")
            raise ValueError("No microphones found.")

        logging.info("Available Microphones:")
        for index, name in enumerate(mic_list):
            logging.info(f"Microphone {index}: {name}")

        if self.microphone_index is not None:
            if self.microphone_index < 0 or self.microphone_index >= len(mic_list):
                logging.error(f"Invalid microphone index: {self.microphone_index}")
                raise ValueError(f"Invalid microphone index: {self.microphone_index}")
            self.device_index = self.microphone_index
            logging.info(f"Selected Microphone {self.device_index}: {mic_list[self.device_index]}")
        else:
            self.device_index = None
            logging.info("Using default microphone.")

    def listen(self, timeout=None, phrase_time_limit=None):
        try:
            with sr.Microphone(device_index=self.device_index) as source:
                logging.info("Adjusting for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                logging.info("Listening...")
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                transcription = self.recognizer.recognize_google(audio, language=self.language)
                logging.info(f"You said: {transcription}")
                return transcription.lower()
        except sr.WaitTimeoutError:
            logging.warning("Listening timed out while waiting for phrase to start.")
            return None
        except sr.UnknownValueError:
            logging.warning("Could not understand audio.")
            return None
        except sr.RequestError as e:
            logging.error(f"Could not request results; {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            return None