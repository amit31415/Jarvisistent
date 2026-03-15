import speech_recognition as sr
import os
import subprocess
import json
import shutil
import re
import sys
import time
import struct
import pvporcupine
import pyaudio
import datetime
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

# --- 3. אתחול המוח (Gemini 2.5 Flash + Internet + Clock) ---
print("Initializing Gemini Brain...", end='', flush=True)
try:
    client = genai.Client(api_key=GEMINI_KEY)
    
    sys_prompt = """You are Jarvis, a smart room AI voice assistant. 
CRITICAL RULE: You are connected directly to a Text-to-Speech engine. Output ONLY the final words to be spoken aloud. 
NEVER output internal thoughts, planning, <think> tags, markdown, or reasoning. 
Keep answers extremely short, conversational, and practical. Reply in the exact same language the user speaks. 
If the user implies exit/stop/goodbye, output exactly: [EXIT]"""
    
    # חיבור הכלי של חיפוש בגוגל
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

        # יצירת קובץ השמע
        subprocess.run([
            edge_tts_cmd, '--text', clean_text, '--write-media', 'response.mp3',
            '--voice', voice, '--rate=+15%'
        ], check=True)

        # הרצת האודיו ברקע (Non-blocking)
        player = subprocess.Popen(['mpv', 'response.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # לולאת ההתפרצות (Barge-in)
        if porcupine and pa:
            # פתיחת מיקרופון ייעודי לזיהוי "Jarvis" בזמן הדיבור
            temp_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)
            try:
                while player.poll() is None:
                    pcm = temp_stream.read(porcupine.frame_length, exception_on_overflow=False)
                    pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
                    
                    if porcupine.process(pcm) >= 0:
                        player.terminate() # השתקה מיידית!
                        print("\n[INTERRUPTED BY USER]")
                        subprocess.run(['mpv', 'alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return True # מחזיר אמת - המשתמש קטע אותנו
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

# --- מנגנון מעקב API מקומי (אופליין) ---
DAILY_API_LIMIT = 1500 # המכסה היומית הממוצעת בחינם. תוכל לשנות אם תצטרך.
QUOTA_FILE = "api_quota.json"

def log_api_call():
    today = datetime.date.today().isoformat()
    try:
        with open(QUOTA_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"date": today, "count": 0}

    if data.get("date") != today:
        data = {"date": today, "count": 1} # יום חדש, איפוס מונה
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

def get_local_stats():
    try:
        # קריאת טמפרטורת מעבד בלינוקס
        temp_raw = subprocess.check_output(['cat', '/sys/class/thermal/thermal_zone0/temp']).decode('utf-8')
        temp = float(temp_raw) / 1000.0
        
        # קריאת זיכרון פנוי (במגה-בייט)
        mem_raw = subprocess.check_output(['free', '-m']).decode('utf-8')
        free_mem = mem_raw.splitlines()[1].split()[3]
        
        return f"מערכות הליבה תקינות. המעבד בטמפרטורה של {temp:.1f} מעלות, ויש {free_mem} מגה-בייט של זיכרון פנוי."
    except Exception as e:
        return "יש לי שגיאה בקריאת נתוני החומרה."

# --- לולאת שיחה רציפה ---
def run_conversation_session(porcupine, pa):
    silence_counter = 0
    while True:
        silence_counter = 0
        print(f"\n[You]: {user_input}")
        
        user_text = user_input.lower()
 
# --- המוח המקומי (Local Brain / Fast Path) ---
        exit_words = ["לא", "מספיק", "תודה", "זהו", "ביי", "stop", "exit"]
        if any(word in user_text for word in exit_words) or user_text.strip() == "לא":
            speak("בסדר גמור, אני כאן אם תצטרך.", porcupine, pa)
            break
            
        if "כיבוי" in user_text and "מערכת" in user_text:
            speak("מכבה מערכות. להתראות.", porcupine, pa)
            os.system("sudo shutdown -h now")
            sys.exit(0)
            
        if "מה השעה" in user_text or "זמן" in user_text:
            now = datetime.datetime.now().strftime("%H:%M")
            speak(f"השעה עכשיו היא {now}.", porcupine, pa)
            continue
            
        # ניתוב שאלות חומרה מדויקות:
        if "מצב זיכרון" in user_text or "ראם" in user_text:
            speak(get_detailed_stats("memory"), porcupine, pa)
            continue
            
        if "שטח אחסון" in user_text or "מקום פנוי" in user_text:
            speak(get_detailed_stats("storage"), porcupine, pa)
            continue
            
        if "מצב מעבד" in user_text or "טמפרטורה" in user_text:
            speak(get_detailed_stats("cpu"), porcupine, pa)
            continue
            
        # ניתוב שאלת מכסת API!
        if "מכסה" in user_text or "פניות" in user_text or "api" in user_text:
            status = get_api_status()
            speak(status, porcupine, pa)
            continue
       
#מוח ענן (Cloud Brain / Slow Path) ---
        # מגיע לפה רק אם זה לא נתפס במוח המקומי
        response = ask_brain(user_input)
        if "[EXIT]" in response:
            speak(response, porcupine, pa)
            break
        else:
            speak(response, porcupine, pa)

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
                
                # סוגרים מיקרופון של השכמה כדי לפנות למנוע השיחה
                audio_stream.stop_stream()
                audio_stream.close()

                # כניסה לשיחה רציפה (מעבירים את האובייקטים כדי שידע להקשיב להתפרצויות)
                run_conversation_session(porcupine, pa)

                # פתיחה מחדש להשכמה
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
