import speech_recognition as sr
import os
import subprocess
import sys
import struct
import pvporcupine
import pyaudio
import ollama
import re
import time
from dotenv import load_dotenv

# --- טעינת מפתחות ---
load_dotenv()
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY")

if not PORCUPINE_KEY:
    print("\n❌ Error: PORCUPINE_KEY is missing in .env file.")
    sys.exit(1)

# --- משתנים גלובליים ---
current_player = None
# כאן השינוי: משתמשים ב-Qwen במקום ב-Llama
MODEL_NAME = 'qwen2.5:1.5b' 

# --- פונקציות עזר ---
def contains_hebrew(text):
    return bool(re.search(r'[\u0590-\u05FF]', text))

def stop_speaking():
    global current_player
    if current_player:
        if current_player.poll() is None:
            current_player.terminate()
        current_player = None

def speak(text):
    global current_player
    stop_speaking()
    
    clean_text = text.replace("*", "").replace("#", "").replace('"', '').strip()
    print(f"\n[Jarvis]: {clean_text}")
    
    if not clean_text: return

    try:
        voice = "en-GB-RyanNeural"
        if contains_hebrew(clean_text):
            voice = "he-IL-AvriNeural"
        
        subprocess.run([
            'edge-tts', '--text', clean_text, '--write-media', 'response.mp3', 
            '--voice', voice, '--rate=+20%'
        ], check=True)

        subprocess.run(['mpv', 'response.mp3', '--no-terminal']) 
    except: pass

def ask_local_brain(text):
    print(" Thinking...", end="", flush=True)
    try:
        # שינוי פרומפט כדי שיתאים ל-Qwen
        response = ollama.chat(model=MODEL_NAME, messages=[
            {
                'role': 'system',
                'content': 'You are Jarvis. Be helpful and very concise. If the user speaks Hebrew, you MUST answer in Hebrew. If English, answer in English.'
            },
            {
                'role': 'user',
                'content': text
            },
        ], keep_alive='5m') 
        
        print(" Done.")
        return response['message']['content']
    except Exception as e:
        print(f"\n[Ollama Error]: {e}")
        return "Brain offline."

def listen_with_timeout(timeout_seconds=6):
    r = sr.Recognizer()
    try: source = sr.Microphone(device_index=0)
    except: source = sr.Microphone()

    with source:
        sys.stdout.write(" Listening...")
        sys.stdout.flush()
        try:
            audio = r.listen(source, timeout=timeout_seconds, phrase_time_limit=10)
            sys.stdout.write("\r Processing...")
            sys.stdout.flush()
            text = r.recognize_google(audio, language="he-IL")
            return text
        except: return None

def run_conversation_session():
    silence_counter = 0
    while True:
        try:
            user_input = listen_with_timeout(timeout_seconds=6)
            sys.stdout.write("\r" + " " * 20 + "\r") 
            
            if user_input is None:
                silence_counter += 1
                if silence_counter == 1:
                    speak("Are we done?")
                    continue
                elif silence_counter >= 2:
                    break
            else:
                silence_counter = 0
                print(f"[You]: {user_input}")
                
                if "סיימנו" in user_input or "ביי" in user_input or "stop" in user_input.lower():
                    speak("Goodbye.")
                    break
                
                if "כיבוי" in user_input and "מערכת" in user_input:
                    speak("Shutting down.")
                    os.system("sudo shutdown -h now")
                    break

                response = ask_local_brain(user_input)
                speak(response)
                
        except KeyboardInterrupt:
            break

def run_jarvis():
    try: 
        porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keywords=['jarvis'])
    except: 
        print("Error: Check Porcupine Key.")
        return

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)

    os.system('clear')
    
    # חימום מנועים
    print(f"Warming up {MODEL_NAME}...", end='', flush=True)
    try:
        ollama.chat(model=MODEL_NAME, messages=[{'role':'user', 'content':'hi'}])
        print(" Ready.")
    except:
        print(" Error loading model (Did you run 'ollama run qwen2.5:1.5b'?).")

    speak("System Online.")
    print("\n[INFO] Waiting for wake word...")

    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            
            if porcupine.process(pcm) >= 0:
                stop_speaking()
                subprocess.run(['mpv', 'alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                audio_stream.stop_stream()
                audio_stream.close()
                
                run_conversation_session()
                
                audio_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)
                print("\n[INFO] Standing by...")

    except KeyboardInterrupt:
        pass
    finally:
        if porcupine: porcupine.delete()
        if audio_stream: audio_stream.close()
        if pa: pa.terminate()

if __name__ == "__main__":
    run_jarvis()
