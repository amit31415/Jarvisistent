import speech_recognition as sr
import os
import subprocess
import sys
import struct
import pvporcupine
import ollama
import time
import datetime
import requests
from duckduckgo_search import DDGS
from dotenv import load_dotenv
from pvrecorder import PvRecorder

# --- הגדרות ידניות ---
MODEL_NAME = 'llama3.2'
# נסה לשנות את המספר הזה אם הוא לא שומע (למשל ל-0, 2, או 3)
MIC_INDEX = 0  

# --- טעינת מפתחות ---
load_dotenv()
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY")
if not PORCUPINE_KEY: sys.exit("Error: Check .env file")

# --- פונקציות ---
def stop_speaking():
    # פונקציה למניעת חפיפה בדיבור
    pass 

def speak(text):
    print(f"\n[Jarvis]: {text}")
    try:
        subprocess.run(['edge-tts', '--text', text, '--write-media', 'response.mp3', '--voice', 'en-GB-RyanNeural'], check=True)
        subprocess.run(['mpv', 'response.mp3', '--no-terminal']) 
    except: pass

def ask_local_brain(text):
    print(" Thinking...", end="", flush=True)
    try:
        response = ollama.chat(model=MODEL_NAME, messages=[
            {'role': 'system', 'content': 'You are Jarvis. Answer in English, short and witty.'},
            {'role': 'user', 'content': text}
        ])
        print(" Done.")
        return response['message']['content']
    except: return "System Error."

def listen_with_timeout():
    r = sr.Recognizer()
    try: source = sr.Microphone(device_index=MIC_INDEX)
    except: 
        print(f"Error opening Mic Index {MIC_INDEX}. Try changing the number in the code.")
        return None

    with source:
        sys.stdout.write(" Listening...")
        sys.stdout.flush()
        try:
            audio = r.listen(source, timeout=5)
            return r.recognize_google(audio, language="en-US")
        except: return None

def run_jarvis():
    try: porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keywords=['jarvis'])
    except: return

    # אתחול המיקרופון הישיר (PvRecorder)
    try:
        recorder = PvRecorder(device_index=MIC_INDEX, frame_length=porcupine.frame_length)
    except Exception as e:
        print(f"\n❌ Error with Mic Index {MIC_INDEX}: {e}")
        print("--> Try changing 'MIC_INDEX' at the top of the script to 0, 1, 2 or 3.")
        return

    os.system('clear')
    print(f"System Online. Mic Index: {MIC_INDEX}")
    recorder.start()

    try:
        while True:
            pcm = recorder.read()
            if porcupine.process(pcm) >= 0:
                recorder.stop()
                subprocess.run(['mpv', 'alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # הקשבה לפקודה
                user_input = listen_with_timeout()
                if user_input:
                    print(f"\n[You]: {user_input}")
                    resp = ask_local_brain(user_input)
                    speak(resp)
                
                recorder.start()
    except KeyboardInterrupt: pass
    finally:
        recorder.delete()
        porcupine.delete()

if __name__ == "__main__":
    run_jarvis()
