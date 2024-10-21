import pyttsx3
import threading

class TTS:
    def __init__(self, rate=150, volume=1.0, voice=None):
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', rate)
        self.engine.setProperty('volume', volume)
        if voice:
            self.engine.setProperty('voice', voice)
        self.lock = threading.Lock()

    def speak(self, text):
        with self.lock:
            self.engine.say(text)
            self.engine.runAndWait()

    def stop(self):
        with self.lock:
            self.engine.stop()