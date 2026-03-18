import speech_recognition as sr
import os
import subprocess
import re
import sys
import time
import struct
import pvporcupine
import pyaudio
import datetime
import json
import shutil
import local_memory
from dotenv import load_dotenv
from ctypes import *
from google import genai
from google.genai import types

# --- 1. השתקת שגיאות ALSA ---
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass

# --- 2. טעינת מפתחות ---
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_KEY")
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY")

if not GEMINI_KEY or not PORCUPINE_KEY:
    print("\n❌ Error: Missing GEMINI_KEY or PORCUPINE_KEY in .env file.")
    sys.exit(1)

# --- 3. אתחול המוח (Gemini 2.5 Flash + Internet) ---
print("Initializing Gemini Brain...", end='', flush=True)
try:
    client = genai.Client(api_key=GEMINI_KEY)
    
    sys_prompt = """You are Jarvis, a smart room AI voice assistant. 
CRITICAL RULE: You are connected directly to a Text-to-Speech engine. Output ONLY the final words to be spoken aloud. 
NEVER output internal thoughts, planning, <think> tags, markdown, or reasoning. 
Keep answers extremely short, conversational, and practical. Reply in the exact same language the user speaks. 
If the user implies exit/stop/goodbye, output exactly: [EXIT]"""
    
    search_tool = types.Tool(google_search=types.GoogleSearch())

    chat = client.chats.create(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(
            system_instruction=sys_prompt,
            tools=[search_tool]
        )
    )
    print(" Ready. ✅")
except Exception as e:
    print(f"\n❌ Brain offline. Connection error: {e}")
    sys.exit(1)

# --- מנגנון מעקב API מקומי (אופליין) ---
DAILY_API_LIMIT = 1500
QUOTA_FILE = "api_quota.json"

def log_api_call():
    today = datetime.date.today().isoformat()
    try:
        with open(QUOTA_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"date": today, "count": 0}

    if data.get("date") != today:
        data = {"date": today, "count": 1}
    else:
        data["count"] += 1

    with open(QUOTA_FILE, "w") as f:
        json.dump(data, f)

def get_api_status():
    today = datetime.date.today().isoformat()
    try:
        with open(QUOTA_FILE, "r") as f:
            data = json.load(f)
        count = data["count"] if data.get("date") == today else 0
    except:
        count = 0
    
    remaining = DAILY_API_LIMIT - count
    return f"ניצלנו היום {count} פניות לענן. נותרו בערך {remaining} פניות. המכסה תתאפס הלילה בחצות."

# --- טלמטריה חומרתית מורחבת ---
def get_detailed_stats(request_type="all"):
    try:
        if request_type == "memory":
            mem_raw = subprocess.check_output(['free', '-m']).decode('utf-8')
            free_mem = mem_raw.splitlines()[1].split()[3]
            return f"יש לך {free_mem} מגה-בייט של זיכרון ראם פנוי כרגע."
            
        elif request_type == "storage":
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            return f"נשארו לנו {free_gb} ג'יגה-בייט פנויים בכרטיס הזיכרון."
            
        elif request_type == "cpu":
            temp_raw = subprocess.check_output(['cat', '/sys/class/thermal/thermal_zone0/temp']).decode('utf-8')
            temp = float(temp_raw) / 1000.0
            load1, _, _ = os.getloadavg()
            cpu_load = (load1 / os.cpu_count()) * 100
            return f"המעבד בטמפרטורה של {temp:.1f} מעלות, ועומס העבודה הוא באזור ה-{cpu_load:.0f} אחוז."
            
    except Exception as e:
        return "מצטער, יש לי בעיה לגשת לחיישני המערכת כרגע."

# --- פונקציות עזר ודיבור (עם Interrupt) ---
def contains_hebrew(text):
    return bool(re.search(r'[\u0590-\u05FF]', text))

def speak(text, porcupine=None, pa=None):
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = re.sub(r'\[.*?\]', '', clean_text)
    clean_text = clean_text.replace("*", "").strip()
    
    if not clean_text: return False
    
    print(f"\n[Jarvis]: {clean_text}")

    try:
        voice = "en-GB-RyanNeural"
        if contains_hebrew(clean_text):
            voice = "he-IL-AvriNeural"

        edge_tts_cmd = '/home/kido1/Smartroom/.venv/bin/edge-tts'

        subprocess.run([
            edge_tts_cmd, '--text', clean_text, '--write-media', 'response.mp3',
            '--voice', voice, '--rate=+15%'
        ], check=True)

        player = subprocess.Popen(['mpv', 'response.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if porcupine and pa:
            temp_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)
            try:
                while player.poll() is None:
                    pcm = temp_stream.read(porcupine.frame_length, exception_on_overflow=False)
                    pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
                    
                    if porcupine.process(pcm) >= 0:
                        player.terminate() 
                        print("\n[INTERRUPTED BY USER]")
                        subprocess.run(['mpv', 'alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True 
            finally:
                temp_stream.stop_stream()
                temp_stream.close()
        else:
            player.wait()
            
        return False
        
    except Exception as e:
        print(f"Speak Error: {e}")
        return False

# --- פונקציות האזנה וחשיבה ---
def listen():
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = 150
    r.pause_threshold = 1.0

    try:
        source = sr.Microphone(device_index=0)
    except:
        source = sr.Microphone()

    with source:
        sys.stdout.write(" Listening...")
        sys.stdout.flush()
        try:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
            sys.stdout.write("\r Processing...")
            sys.stdout.flush()
            return r.recognize_google(audio, language="he-IL") 
        except:
            return None

def ask_brain(text):
    now = datetime.datetime.now().strftime("%H:%M, %A, %d/%m/%Y")
    enriched_text = f"[System Time: {now}]. User says: {text}"
    
    log_api_call() 
    
    try:
        response = chat.send_message(enriched_text)
        return response.text.strip()
    except Exception as e:
        error_msg = str(e)
        print(f"\n[Error API]: {error_msg}")
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return "הגעתי למגבלת הפניות. נסה שוב בעוד רגע."
        return "יש לי תקלה בחיבור לרשת."

# --- לולאת שיחה רציפה + מנהל דיאלוג (State Machine) ---
def run_conversation_session(porcupine, pa):
    silence_counter = 0
    
    # זיכרון מצב של מנהל השיחה
    active_intent = None
    slots = {"type": None, "name": None, "folder": "כללי", "content": None}
    awaiting_slot = None
    
    while True:
        try:
            user_input = listen()
            
            if not user_input:
                silence_counter += 1
                if silence_counter == 1:
                    was_interrupted = speak("תרצה עוד משהו?", porcupine, pa)
                    if was_interrupted:
                        silence_counter = 0 
                    continue
                else:
                    speak("חוזר למצב המתנה.", porcupine, pa)
                    break
            
            silence_counter = 0
            print(f"\n[You]: {user_input}")
            user_text = user_input.lower()
            
            # --- פקודות מערכת מיידיות (עוקף את מנהל השיחה) ---
            exit_words = ["לא", "מספיק", "תודה", "זהו", "ביי", "stop", "exit"]
            if any(word in user_text for word in exit_words) or user_text.strip() == "לא":
                speak("בסדר גמור, אני כאן אם תצטרך.", porcupine, pa)
                break
                
            if "מה השעה" in user_text or "זמן" in user_text:
                now = datetime.datetime.now().strftime("%H:%M")
                speak(f"השעה עכשיו היא {now}.", porcupine, pa)
                continue

            # ==========================================
            # מנהל השיחה (Dialog Manager - Slot Filling)
            # ==========================================
            
            # שלב 1: קליטת תשובות ממוקדות (אם אנחנו באמצע תהליך)
            if active_intent and awaiting_slot:
                if awaiting_slot == "type":
                    if "תיקי" in user_text: slots["type"] = "folder"
                    elif "קובץ" in user_text or "פתק" in user_text: slots["type"] = "file"
                    else:
                        speak("לא הבנתי. ליצור תיקייה או קובץ?", porcupine, pa)
                        continue
                        
                elif awaiting_slot == "name":
                    # ניקוי מילים מיותרות שהמשתמש עלול להגיד
                    clean_name = user_text.replace("תקרא לזה", "").replace("בשם", "").strip()
                    slots["name"] = clean_name
                    
                elif awaiting_slot == "content":
                    slots["content"] = user_text.strip()
                
                awaiting_slot = None # קיבלנו את התשובה, נתקדם.
            
            # שלב 2: זיהוי כוונה חדשה (אם אנחנו לא באמצע תהליך)
            elif not active_intent:
                if any(w in user_text for w in ["צור", "ליצור", "תייצר", "תיצור"]):
                    active_intent = "CREATE"
                    if "תיקי" in user_text: slots["type"] = "folder"
                    elif "קובץ" in user_text: slots["type"] = "file"
                
                elif any(w in user_text for w in ["תוסיף", "תכתוב", "הערה"]):
                    active_intent = "ADD_NOTE"
                    slots["type"] = "file"
            
            # שלב 3: בדיקת משבצות חסרות וביצוע
            if active_intent:
                
                # תהליך יצירה (CREATE)
                if active_intent == "CREATE":
                    if not slots["type"]:
                        awaiting_slot = "type"
                        speak("אין בעיה, מה ליצור? תיקייה או קובץ?", porcupine, pa)
                        continue
                    if not slots["name"]:
                        awaiting_slot = "name"
                        tipo = "התיקייה" if slots["type"] == "folder" else "הקובץ"
                        speak(f"באיזה שם לקרוא ל{tipo}?", porcupine, pa)
                        continue
                        
                    # הכל מלא! מבצעים פעולה.
                    speak(f"מייצר עכשיו את ה{slots['type']} {slots['name']}...", porcupine, pa)
                    if slots["type"] == "folder":
                        local_memory.create_folder(slots["name"])
                    else:
                        local_memory.save_note(slots["folder"], slots["name"], "נוצר בהצלחה.")
                    speak("בוצע.", porcupine, pa)
                    
                    # איפוס מנהל השיחה בסיום!
                    active_intent = None
                    slots = {"type": None, "name": None, "folder": "כללי", "content": None}
                    continue

                # תהליך הוספת הערה (ADD_NOTE)
                elif active_intent == "ADD_NOTE":
                    if not slots["content"]:
                        awaiting_slot = "content"
                        speak("מה תרצה שאכתוב בהערה?", porcupine, pa)
                        continue
                    if not slots["name"]:
                        awaiting_slot = "name"
                        speak("לאיזה קובץ להוסיף את זה?", porcupine, pa)
                        continue
                        
                    # הכל מלא! מבצעים פעולה.
                    speak(f"מעדכן את קובץ {slots['name']}...", porcupine, pa)
                    local_memory.save_note(slots["folder"], slots["name"], slots["content"])
                    speak("שמרתי אדוני.", porcupine, pa)
                    
                    # איפוס מנהל השיחה בסיום!
                    active_intent = None
                    slots = {"type": None, "name": None, "folder": "כללי", "content": None}
                    continue

            # --- מוח ענן (אם שום דבר לא תפס במקומי) ---
            if not active_intent:
                response = ask_brain(user_input)
                if "[EXIT]" in response:
                    speak(response, porcupine, pa)
                    break
                else:
                    speak(response, porcupine, pa)
                
        except Exception as e:
            print(f"Conversation error: {e}")
            speak("היתה לי תקלה קטנה בלולאה, חוזר להמתנה.", porcupine, pa)
            break

# --- ליבת המערכת (השכמה) ---
def run_jarvis():
    try:
        porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keywords=['jarvis'])
    except Exception as e:
        print(f"Porcupine Error: {e}")
        return

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)

    os.system('clear')
    speak("System integrated and online. Awaiting your command.")
    print("\n[INFO] Listening for wake word 'Jarvis'...")

    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

            if porcupine.process(pcm) >= 0:
                print("\n[WAKE WORD DETECTED]")
                subprocess.run(['mpv', 'alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                audio_stream.stop_stream()
                audio_stream.close()

                run_conversation_session(porcupine, pa)

                audio_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)
                print("\n[INFO] Standing by...")

    except KeyboardInterrupt:
        print("\n[INFO] Shutting down Jarvis.")
    finally:
        if porcupine: porcupine.delete()
        if 'audio_stream' in locals() and audio_stream: audio_stream.close()
        if pa: pa.terminate()

if __name__ == "__main__":
    run_jarvis()
