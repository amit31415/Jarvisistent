import speech_recognition as sr
from gtts import gTTS
import os
import subprocess
import time

def speak(text):
    print(f"[Jarvis]: {text}")
    try:
        tts = gTTS(text=text, lang='en')
        tts.save("response.mp3")
        # שימוש ב-mpg123 שהוא נגן MP3 קליל ויציב
        subprocess.run(['mpg123', '-q', "response.mp3"])
    except Exception as e:
        print(f"Error speaking: {e}")

def listen():
    recognizer = sr.Recognizer()
    
    # חיפוש אוטומטי של מיקרופון USB
    mic_index = None
    for index, name in enumerate(sr.Microphone.list_microphone_names()):
        if "USB" in name:
            mic_index = index
            print(f"Found USB Mic: {name} at index {index}")
            break
            
    # הגדרות רגישות - קריטי למניעת תקיעות!
    recognizer.energy_threshold = 400  # רגישות בסיסית (נמוך = רגיש יותר)
    recognizer.dynamic_energy_threshold = True 

    with sr.Microphone(device_index=mic_index) as source:
        print("\nAdjusting noise... (Silence please!)")
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Listening... (Say 'Hello')")
        
        try:
            # timeout=5: אם לא דיברת תוך 5 שניות - שחרר
            # phrase_time_limit=5: אל תקליט יותר מ-5 שניות רצוף
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            print("Processing...")
            
            text = recognizer.recognize_google(audio)
            return text.lower()
            
        except sr.WaitTimeoutError:
            print("No speech detected (Timeout).")
            return None
        except sr.UnknownValueError:
            print("Google didn't understand audio.")
            return None
        except sr.RequestError:
            speak("No internet connection.")
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None

if __name__ == "__main__":
    speak("System ready.")
    
    while True:
        try:
            command = listen()
            
            if command:
                print(f"[You]: {command}")
                if "hello" in command:
                    speak("Hello there. The audio system is fully operational.")
                elif "stop" in command or "exit" in command:
                    speak("Goodbye.")
                    break
                else:
                    speak(f"You said: {command}")
        except KeyboardInterrupt:
            break
