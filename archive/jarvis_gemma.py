import speech_recognition as sr
import os
import subprocess
import google.generativeai as genai
import re
import sys
import time
import struct
import math
import pvporcupine
import pyaudio
from dotenv import load_dotenv

# --- טעינת מפתחות ---
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_KEY")
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY")

if not GEMINI_KEY or not PORCUPINE_KEY:
    print("\n❌ Error: Missing keys in .env file.")
    sys.exit(1)

genai.configure(api_key=GEMINI_KEY)

# --- קובץ זיכרון ---
MEMORY_FILE = "jarvis_memory.txt"
if not os.path.exists(MEMORY_FILE):
    with open(MEMORY_FILE, "w") as f: f.write("User Facts:\n")

# --- משתנים גלובליים ---
current_player = None
chats = {}      
models = {}     

# --- טעינה (Gemma Speed Edition) ---
print("Initializing Fast Gemma System...", end='', flush=True)

models_to_try = [
    ('main', 'gemma-2-2b-it'),      # עדיפות 1: המודל הכי קטן ומהיר (פחות חכם, אבל עובד)
    ('smart', 'gemma-2-9b-it'),     # עדיפות 2: המודל החכם (שנתקע לך קודם)
    ('flash', 'gemini-1.5-flash-8b') # עדיפות 3: מודל פלאש חדש ומהיר מאוד (אולי פנוי במכסה)
]

for name, model_id in models_to_try:
    try:
        models[name] = genai.GenerativeModel(model_id)
        # בדיקה קצרה
        models[name].generate_content("hi", request_options={'timeout': 10})
    except:
        continue 

if not models:
    print("\nError: Could not connect to any model. Internet or Key issue.")
    sys.exit(1)

print(" Done.")

# --- פונקציות ---
def load_memory():
    try:
        with open(MEMORY_FILE, "r") as f: return f.read()
    except: return ""

def save_to_file(fact):
    try:
        fact = fact.replace("]", "").replace("[", "")
        with open(MEMORY_FILE, "a") as f: f.write(f"- {fact}\n")
        print(f"\n[Saved]: {fact}")
    except: pass

def reset_brains():
    global chats
    long_term_mem = load_memory()
    
    dynamic_prompt = f"""
You are Jarvis.
User Memory: {long_term_mem}
Rules:
1. Short answers (1 sentence).
2. Reply in the language I speak (Hebrew/English).
3. Say "[EXIT]" to stop.
4. To save memory: "[MEM: ...]"
"""

    chats = {}
    for name, model_obj in models.items():
        try:
            chats[name] = model_obj.start_chat(history=[])
            chats[name].send_message(dynamic_prompt)
        except:
            pass

def stop_speaking():
    global current_player
    if current_player:
        if current_player.poll() is None:
            current_player.terminate()
        current_player = None

def play_sound(sound_type="wake"):
    try:
        text = "Yes?" if sound_type == "wake" else "Mmhmm?"
        subprocess.run(['edge-tts', '--text', text, '--write-media', 'alert.mp3', '--voice', 'en-GB-RyanNeural', '--rate=+40%'], check=False)
        subprocess.run(['mpv', 'alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def contains_hebrew(text):
    return bool(re.search(r'[\u0590-\u05FF]', text))

def speak(text):
    global current_player
    stop_speaking()
    
    clean_text = text.replace("[EXIT]", "")
    clean_text = re.sub(r'\[MEM:.*?\]', '', clean_text)
    clean_text = clean_text.replace("*", "").strip()
    
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
    except KeyboardInterrupt:
        # טיפול בעצירה ידנית בזמן דיבור
        stop_speaking()
        print("\n[Stopped Speaking]")
    except Exception as e:
        pass

def listen_with_timeout(timeout_seconds=6):
    r = sr.Recognizer()
    r.dynamic_energy_threshold = False
    r.energy_threshold = 150 
    
    try:
        source = sr.Microphone(device_index=0)
    except:
        source = sr.Microphone()

    with source:
        sys.stdout.write(" Listening...")
        sys.stdout.flush()
        
        try:
            audio = r.listen(source, timeout=timeout_seconds, phrase_time_limit=None)
            sys.stdout.write("\r Processing...")
            sys.stdout.flush()
            text = r.recognize_google(audio, language="he-IL")
            return text
        except:
            return None

def ask_brain(text):
    for key in ['main', 'smart', 'flash']:
        if key in chats:
            try:
                # הגדלתי ל-30 שניות כדי לתת לו זמן לחשוב
                response = chats[key].send_message(text, request_options={'timeout': 30})
                response_text = response.text.strip()
                
                if "[MEM:" in response_text:
                    try:
                        match = re.search(r'\[MEM:(.*?)\]', response_text)
                        if match: save_to_file(match.group(1).strip())
                    except: pass
                
                return response_text
            except Exception as e:
                # הדפסה של השגיאה האמיתית במקום סתם Timeout
                print(f"\n[Error {key}]: {str(e)[:100]}...") 
                continue

    return "No response (Check internet or quota)."

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
                
                if "סיימנו" in user_input or "ביי" in user_input:
                    speak("Goodbye.")
                    break
                
                if "כיבוי" in user_input and "מערכת" in user_input:
                    speak("Shutting down.")
                    os.system("sudo shutdown -h now")
                    break

                response = ask_brain(user_input)
                
                if "[EXIT]" in response:
                    speak(response)
                    break
                
                speak(response)
        except KeyboardInterrupt:
            print("\nStopping conversation.")
            break

def run_jarvis():
    try:
        porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keywords=['jarvis'])
    except:
        print("Error: Check Porcupine Key.")
        return

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(
        rate=porcupine.sample_rate,
        channels=1,
        format=pyaudio.paInt16,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )

    os.system('clear')
    speak("Jarvis V37 (Fast Gemma).")
    print("\n[INFO] System Ready. Waiting for wake word...")

    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            keyword_index = porcupine.process(pcm)

            if keyword_index >= 0:
                stop_speaking()
                play_sound("wake")
                reset_brains()
                audio_stream.stop_stream()
                audio_stream.close()
                run_conversation_session()
                audio_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)
                print("\n[INFO] Standing by...")

    except KeyboardInterrupt: pass
    finally:
        if porcupine: porcupine.delete()
        if audio_stream: audio_stream.close()
        if pa: pa.terminate()

if __name__ == "__main__":
    run_jarvis()
