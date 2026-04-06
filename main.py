import speech_recognition as sr
import os
import json
import subprocess
import re
import sys
import time
import struct
import random
import pvporcupine
import pyaudio
import datetime
import urllib.request
import urllib.parse
from ctypes import *
from dotenv import load_dotenv

# --- Imports from new architecture ---
from core import google_api
from core import local_memory
from google import genai
from google.genai import types
from modules.study_mode import StudyManager
from modules.alarm_mode import AlarmManager
from modules.music_mode import MusicManager
music_manager = MusicManager()

# --- 1. ALSA Error Handler ---
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass

# --- 2. Load Keys & Init Managers ---
load_dotenv('/home/kido1/Smartroom/.env', override=True)

GEMINI_KEY = os.getenv("GEMINI_KEY")
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY")

if not GEMINI_KEY or not PORCUPINE_KEY:
    print("\n[Error] Missing API Keys in .env")
    sys.exit(1)

print(f"[DEBUG] Loaded Gemini Key starting with: {GEMINI_KEY[:5]}...")

study_manager = StudyManager()
alarm_manager = AlarmManager()

# =====================================================================
# --- 3. THE TOOLBOX (הכלים של ג'ארוויס) ---
# =====================================================================

MEMORY_FILE = '/home/kido1/Smartroom/data/jarvis_memory.json'

def remember_fact(fact: str) -> str:
    """Use this tool to save important long-term facts."""
    memories = []
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            try: memories = json.load(f)
            except: pass
    
    if fact not in memories:
        memories.append(fact)
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memories, f, ensure_ascii=False, indent=4)
        return f"Memory successfully saved: {fact}"
    return "I already know this fact."

def check_general_emails() -> str:
    print("[INFO] AI executing: check_general_emails()")
    return google_api.get_unread_emails(max_results=40)

def search_specific_email(search_term: str) -> str:
    print(f"[INFO] AI executing: search_specific_email('{search_term}')")
    try: return google_api.get_specific_email(search_term)
    except Exception as e: return "הייתה בעיה טכנית בעת ביצוע החיפוש."

def check_calendar(query: str) -> str:
    """מושך את האירועים והפגישות הקרובות מהיומן (Google Calendar)"""
    print("\n[INFO] AI executing: check_calendar()")
    try: return google_api.get_upcoming_events()
    except Exception as e: return f"שגיאה בקריאת היומן: {str(e)}"

# ---> הוספנו את המשימות <---
def check_tasks(query: str) -> str:
    """מושך את כל המשימות הפתוחות מ-Google Tasks. השתמש בזה אם מבקשים משימות."""
    print("\n[INFO] AI executing: check_tasks()")
    try: return google_api.get_open_tasks()
    except Exception as e: return f"שגיאה בקריאת המשימות: {str(e)}"

# ---> הוספנו את המוזיקה <---
def play_youtube_music(query: str, is_playlist: bool = False) -> str:
    """מנגן מוזיקה מיוטיוב. אם is_playlist הוא אמת, מחפש בפלייליסטים האישיים."""
    print(f"[INFO] AI executing: play_youtube_music('{query}', {is_playlist})")
    if is_playlist:
        return music_manager.play_my_playlist(query)
    return music_manager.play(query)

def control_music(action: str) -> str:
    """שולט במוזיקה שמתנגנת: pause, resume, skip, stop."""
    print(f"[INFO] AI executing: control_music('{action}')")
    if action == "pause": return music_manager.pause()
    elif action == "resume": return music_manager.resume()
    elif action == "skip": return music_manager.skip()
    elif action == "stop": return music_manager.stop()
    return "פעולה לא חוקית למוזיקה."

def get_user_playlists() -> str:
    """מחזיר רשימה של כל הפלייליסטים שיש למשתמש ביוטיוב. השתמש בזה כששואלים 'איזה פלייליסטים יש לי'."""
    print("[INFO] AI executing: get_user_playlists()")
    return music_manager.get_my_playlists()

def get_recent_music_history() -> str:
    """מחזיר את 10 השירים האחרונים שהמשתמש שמע. השתמש בזה כששואלים 'מה שמעתי לאחרונה'."""
    print("[INFO] AI executing: get_recent_music_history()")
    return music_manager.get_recent_songs(10)

def create_new_folder(folder_name: str) -> str:
    local_memory.create_folder(folder_name)
    return f"התיקייה {folder_name} נוצרה."

def add_note_to_file(file_name: str, content: str, folder_name: str = None) -> str:
    local_memory.save_note(folder_name, file_name, content)
    return f"התוכן נשמר לקובץ {file_name}."

def read_file_content(file_name: str, folder_name: str = None) -> str:
    success, content = local_memory.read_full_file(folder_name, file_name)
    return content if success else f"לא מצאתי קובץ בשם {file_name}."

def search_in_file(file_name: str, search_query: str, folder_name: str = None) -> str:
    success, content = local_memory.search_in_file(folder_name, file_name, search_query)
    return content if success else f"לא מצאתי מידע רלוונטי."

def get_current_time() -> str:
    return datetime.datetime.now().strftime("%H:%M, %A, %d/%m/%Y")

def get_system_status() -> str:
    """מחזיר את טמפרטורת המעבד וסטטוס המערכת של הרסברי פאי."""
    print("[INFO] AI executing: get_system_status()")
    try:
        # קורא ישירות מהחיישן של הלינוקס
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp_c = int(f.read().strip()) / 1000.0
        return f"טמפרטורת המעבד של הרסברי פאי היא {temp_c:.1f} מעלות צלזיוס."
    except Exception as e:
        return f"לא הצלחתי לקרוא את הטמפרטורה: {e}"

def shutdown_system() -> str:
    os.system("sudo shutdown -h now")
    return "מכבה את המערכת."

def search_web(query: str) -> str:
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read().decode('utf-8')
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        if not snippets: return "לא מצאתי תוצאות ברשת."
        clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:3]]
        return "תוצאות חיפוש מהאינטרנט:\n" + "\n".join(clean_snippets)
    except Exception as e:
        return f"שגיאת תקשורת בחיפוש: {e}"

def manage_study_mode(action: str, minutes: int = 0) -> str:
    """
    מנהל את מצב הלמידה (Pomodoro Timer).
    פעולות (action) חובה שג'ארוויס חייב להשתמש בהן:
    'start' - התחלת למידה (חשוב: הסשן הוא תמיד 50 דקות! לעולם אל תשאל את המשתמש כמה זמן הוא רוצה, פשוט הפעל מיד עם minutes=0)    'stop' - סיום 
    'pause' - עצירה
    'resume' - המשך 
    'break' - הפסקה
    'status' - בדיקת סטטוס / כמה זמן נשאר
    'add_time' - הוספת דקות לטיימר (minutes יהיה מספר חיובי)
    'reduce_time' - קיצור/הורדת דקות מהטיימר (minutes יהיה מספר חיובי, המערכת תחסר בעצמה)
    """
    print(f"[INFO] AI executing: manage_study_mode('{action}', {minutes})")
    action = action.lower().strip()
    
    if action in ['start', 'התחל']: return study_manager.start_study()
    elif action in ['stop', 'סיום']: return study_manager.stop_study()
    elif action in ['pause', 'השהה']: return study_manager.pause_study()
    elif action in ['resume', 'המשך']: return study_manager.resume_study()
    elif action in ['break', 'הפסקה']: return study_manager.start_break()
    elif action in ['status', 'זמן', 'time', 'check']: return study_manager.get_time_left()
    elif action in ['add_time', 'הוסף']: return study_manager.add_time(abs(minutes))
    elif action in ['reduce_time', 'קצר', 'הורד']: return study_manager.add_time(-abs(minutes))
    
    return f"שגיאה: פעולה '{action}' לא חוקית."

def manage_alarm_clock(action: str, time_str: str = "") -> str:
    if action == 'set':
        if not time_str: return "חובה לציין שעה בפורמט HH:MM."
        return alarm_manager.set_alarm(time_str)
    elif action == 'cancel': return alarm_manager.cancel_alarm(time_str)
    elif action == 'list': return alarm_manager.get_alarms()
    return "פעולה לא חוקית."

# ---> הוספנו את הפונקציות החדשות לרשימה כדי שג'מיני יראה אותן <---
jarvis_tools = [
    check_general_emails, search_specific_email, create_new_folder,
    add_note_to_file, read_file_content, search_in_file, get_current_time,
    shutdown_system, remember_fact, search_web, check_calendar,
    manage_study_mode, manage_alarm_clock, check_tasks, 
    play_youtube_music, control_music, get_system_status,
    get_user_playlists, get_recent_music_history
]

# --- 4. Init Gemini Brain ---
print("Initializing Gemini V2 Brain...", end='', flush=True)
try:
    client = genai.Client(api_key=GEMINI_KEY)
    
    memory_context = ""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            try:
                memories = json.load(f)
                if memories:
                    memory_context = "\nCRITICAL CONTEXT - IMPORTANT FACTS TO REMEMBER:\n"
                    for i, fact in enumerate(memories):
                        memory_context += f"{i+1}. {fact}\n"
            except: pass

    sys_prompt = f"""You are Jarvis, a highly advanced AI voice assistant for your boss (Amit).
Your main superpower is the ability to USE TOOLS. If you have a tool for a request, USE IT immediately.

{memory_context}

CRITICAL RULES:
1. Google Tasks vs Calendar: 'Tasks' (check_tasks) are to-do items. 'Calendar' (check_calendar) are scheduled events. Distinguish between them based on the user's request.
2. Music: 
   - When asked WHAT playlists the user has, use get_user_playlists. 
   - When asked about recently played songs, use get_recent_music_history.
   - ONLY use play_youtube_music when explicitly asked to PLAY or START music.
3. Keep answers short, conversational, and natural in Hebrew.
4. If you use a tool, summarize the results nicely and briefly.
5. NEVER output markdown (like * or **).
6. If the user implies exit/stop/goodbye, output exactly the word: [EXIT]
"""


    chat = client.chats.create(
        model='gemini-2.5-flash',
        config=types.GenerateContentConfig(
            system_instruction=sys_prompt,
            tools=jarvis_tools, 
            temperature=0.3
        )
    )
    print(" Ready. ✅")
except Exception as e:
    print(f"\n[Error] Brain offline: {e}")
    sys.exit(1)


# --- 5. Speech & Audio Functions ---
def contains_hebrew(text):
    return bool(re.search(r'[\u0590-\u05FF]', text))

def get_audio_stream(pa, sample_rate, frame_length):
    device_index = None
    for i in range(pa.get_device_count()):
        dev_info = pa.get_device_info_by_index(i)
        if dev_info.get('maxInputChannels', 0) > 0:
            name = dev_info.get('name', '')
            if "Jabra" in name or "USB" in name:
                device_index = i
                print(f"[INFO] 🎯 Locked on Jabra/USB Mic at Index {i}")
                break
                
    if device_index is None:
        for i in range(pa.get_device_count()):
            dev_info = pa.get_device_info_by_index(i)
            if dev_info.get('maxInputChannels', 0) > 0:
                device_index = i
                print(f"[WARNING] Jabra not found. Falling back to Index {i}")
                break

    return pa.open(
        rate=sample_rate, channels=1, format=pyaudio.paInt16,
        input=True, frames_per_buffer=frame_length, input_device_index=device_index
    )

def speak(text):
    clean_text = re.sub(r'<[^>]+>', '', text).replace("*", "").strip()
    if not clean_text: return
    
    print(f"\n[Jarvis]: {clean_text}", flush=True)

    try:
        voice = "he-IL-AvriNeural" if contains_hebrew(clean_text) else "en-GB-RyanNeural"
        edge_tts_cmd = '/home/kido1/Smartroom/.venv/bin/edge-tts'
        out_path = '/home/kido1/Smartroom/temp/response.mp3'

        subprocess.run([
            edge_tts_cmd, '--text', clean_text, '--write-media', out_path,
            '--voice', voice, '--rate=+15%'
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        subprocess.run(['mpv', out_path, '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
    except Exception as e:
        print(f"Speak Error: {e}")
        
def listen():
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.energy_threshold = 150
    r.pause_threshold = 1.0

    try: source = sr.Microphone(device_index=0)
    except: source = sr.Microphone()

    with source:
        sys.stdout.write(" Listening...")
        sys.stdout.flush()
        try:
            r.adjust_for_ambient_noise(source, duration=0.5)
            audio = r.listen(source, timeout=2, phrase_time_limit=10)
            sys.stdout.write("\r Processing...")
            sys.stdout.flush()
            return r.recognize_google(audio, language="he-IL") 
        except:
            return None


# --- 6. The Clean V2 Conversation Loop ---
def run_conversation_session():
    silence_count = 0
    
    while True:
        try:
            user_input = listen()
            
            if not user_input:
                if study_manager.is_nagging():
                    silence_count = 0
                    continue
                
                silence_count += 1
                if silence_count == 1:
                    speak("Is there something else, sir?")
                    continue
                else:
                    speak("Very well. Back to standby.")
                    break
            
            silence_count = 0
            print(f"\n[You]: {user_input}")
            user_text = user_input.lower()

            alarm_response = alarm_manager.process_voice_command(user_text)
            if alarm_response:
                speak(alarm_response)
                continue
            
            exit_words = ["בטל", "עזוב", "לא משנה", "מספיק", "תודה", "זהו", "ביי", "stop", "exit"]
            if any(word in user_text for word in exit_words) or user_text.strip() == "לא":
                speak("בסדר גמור, אני כאן אם תצטרך.")
                break
            
            if any(word in user_text for word in ["מייל", "מיילים", "הודעות"]):
                speak(random.choice(["פותח תיבת דואר...", "מציץ במיילים...", "שנייה, שולף הודעות..."]))
            elif any(word in user_text for word in ["חפש", "אינטרנט", "מזג אוויר", "חדשות"]):
                speak(random.choice(["מחפש ברשת...", "מריץ חיפוש...", "בודק אונליין..."]))
            elif any(word in user_text for word in ["קובץ", "תיקייה", "פתק", "תזכור", "שמור"]):
                speak(random.choice(["ניגש לקבצים...", "מעדכן את הזיכרון...", "רושם..."]))
            elif any(word in user_text for word in ["למה", "איך", "מי", "מה", "מתי", "איפה"]):
                speak(random.choice(["מעבד...", "רק רגע...", "תן לי לחשוב על זה..."]))

            response = chat.send_message(user_input)
            
            if "[EXIT]" in response.text:
                speak("Goodbye sir.")
                break
            else:
                speak(response.text)
            
        except Exception as e:
            print(f"[Error] V2 Loop Exception: {e}")
            speak("היתה לי תקלה קטנה במוח המרכזי. חוזר להמתנה.")
            break


# --- 7. Main Engine (Wake Word) ---
def run_jarvis():
    try:
        porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keywords=['jarvis'])
    except Exception as e:
        print(f"Porcupine Error: {e}")
        return

    pa = pyaudio.PyAudio()
    
    while True:
        try:
            audio_stream = get_audio_stream(pa, porcupine.sample_rate, porcupine.frame_length)
            break
        except Exception as e:
            print(f"[WARNING] Waiting for microphone on startup... ({e})")
            time.sleep(3)

    os.system('clear')
    speak("Jarvis V2 Core is online. Awaiting command.")
    print("\n[INFO] Listening for wake word 'Jarvis'...")

    try:
        while True:
            try:
                pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            except Exception as e:
                print(f"[ERROR] Audio read failed: {e}. Retrying...")
                try: audio_stream.close()
                except: pass
                time.sleep(2)
                try: audio_stream = get_audio_stream(pa, porcupine.sample_rate, porcupine.frame_length)
                except: pass
                continue

            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

            if porcupine.process(pcm) >= 0:
                print("\n[WAKE WORD DETECTED]")
                
                # השתקת מוזיקה
                try:
                    if 'music_manager' in globals():
                        music_manager._send_mpv_command(["set_property", "pause", True])
                except: pass

                subprocess.run(['mpv', '/home/kido1/Smartroom/assets/wake.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                audio_stream.stop_stream()
                audio_stream.close()

                run_conversation_session()

                # חזרה להאזנה
                while True:
                    try:
                        audio_stream = get_audio_stream(pa, porcupine.sample_rate, porcupine.frame_length)
                        break
                    except Exception as e:
                        print(f"[WARNING] Waiting for microphone... ({e})")
                        time.sleep(3)
                
                # החזרת מוזיקה
                try:
                    if 'music_manager' in globals():
                        music_manager._send_mpv_command(["set_property", "pause", False])
                except: pass

                print("\n[INFO] Standing by...")

    except KeyboardInterrupt:
        print("\n[INFO] Shutting down Jarvis.")
    finally:
        if porcupine: porcupine.delete()
        if 'audio_stream' in locals() and audio_stream: audio_stream.close()
        if pa: pa.terminate()

if __name__ == "__main__":
    run_jarvis()