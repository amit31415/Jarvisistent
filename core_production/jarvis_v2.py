import speech_recognition as sr
import os
import json
import subprocess
import re
import sys
import time
import struct
import pvporcupine
import pyaudio
import datetime
import google_api 
import local_memory
from dotenv import load_dotenv
from ctypes import *
from google import genai
from google.genai import types

# --- 1. ALSA Error Handler (השתקת שגיאות אודיו מציקות) ---
ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
def py_error_handler(filename, line, function, err, fmt):
    pass
c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
try:
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)
except:
    pass

# --- 2. Load Keys ---
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_KEY")
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY")

if not GEMINI_KEY or not PORCUPINE_KEY:
    print("\n[Error] Missing API Keys in .env")
    sys.exit(1)

# =====================================================================
# --- 3. THE TOOLBOX (הכלים של ג'ארוויס - כאן הקסם קורה) ---
# ההסברים (Docstrings) הם קריטיים! ג'מיני קורא אותם כדי להבין מתי להפעיל כל כלי.
# =====================================================================

MEMORY_FILE = '/home/kido1/Smartroom/core_production/jarvis_memory.json'

def remember_fact(fact: str) -> str:
    """
    Use this tool to save important long-term facts about the user, preferences, or the room.
    Call this tool ONLY when the user explicitly asks you to remember something, or if you learn a critical persistent fact.
    """
    memories = []
    # קריאת הזיכרונות הקיימים
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            try:
                memories = json.load(f)
            except:
                pass
    
    # הוספת הזיכרון החדש
    if fact not in memories:
        memories.append(fact)
        # שמירה חזרה לקובץ
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memories, f, ensure_ascii=False, indent=4)
        return f"Memory successfully saved: {fact}"
    else:
        return "I already know this fact."

def check_general_emails() -> str:
    """מושך את המיילים האחרונים שלא נקראו מ-3 הימים האחרונים. השתמש בזה כשהבוס מבקש עדכון כללי על המייל שלו או שואל אם יש הודעות חדשות.
    "CRITICAL: When the user asks you to perform an action (like checking emails, reading files, etc), YOU MUST CALL THE TOOL IMMEDIATELY. DO NOT reply with text saying 'I will check' or 'Checking now'. Just execute the tool right away!"
    """
    print("[INFO] AI executing: check_general_emails()")
    return google_api.get_unread_emails(max_results=40)

def search_specific_email(search_term: str) -> str:
    """מחפש וקורא מייל ספציפי לפי שם שולח או נושא. השתמש בזה כשהבוס שואל על מייל מאדם ספציפי (למשל 'מייל מראובן') או בנושא ספציפי."""
    print(f"[INFO] AI executing: search_specific_email(search_term='{search_term}')")
    try:
        # אנחנו מנסים לקרוא לפונקציה מ-google_api
        return google_api.get_specific_email(search_term)
    except Exception as e:
        # אם יש שגיאה בתוך google_api, נתפוס אותה ונדפיס אותה!
        print(f"\n[CRITICAL ERROR] The search in google_api.py failed!")
        print(f"Error details: {str(e)}")
        return "הייתה בעיה טכנית בעת ביצוע החיפוש בג'ימייל."

def create_new_folder(folder_name: str) -> str:
    """יוצר תיקייה חדשה במערכת הקבצים. השתמש בזה כשהבוס מבקש ליצור או לפתוח תיקייה."""
    print(f"[INFO] AI executing: create_new_folder('{folder_name}')")
    local_memory.create_folder(folder_name)
    return f"התיקייה {folder_name} נוצרה בהצלחה."

def add_note_to_file(file_name: str, content: str, folder_name: str = None) -> str:
    """יוצר קובץ חדש או מוסיף טקסט/הערה/משימה לקובץ קיים. השתמש בזה כשהבוס מבקש לכתוב, להוסיף, או לשמור משהו בקובץ/פתק."""
    print(f"[INFO] AI executing: add_note_to_file('{file_name}', ...)")
    local_memory.save_note(folder_name, file_name, content)
    return f"התוכן נשמר בהצלחה לקובץ {file_name}."

def read_file_content(file_name: str, folder_name: str = None) -> str:
    """קורא את כל התוכן של קובץ או פתק מסוים. השתמש בזה כשהבוס מבקש להקריא לו מה כתוב בקובץ מסוים."""
    print(f"[INFO] AI executing: read_file_content('{file_name}')")
    success, content = local_memory.read_full_file(folder_name, file_name)
    return content if success else f"לא מצאתי קובץ בשם {file_name}."

def search_in_file(file_name: str, search_query: str, folder_name: str = None) -> str:
    """מחפש מידע ספציפי בתוך קובץ קיים. השתמש בזה כשהבוס מחפש מונח או מילה בתוך קובץ מסוים."""
    print(f"[INFO] AI executing: search_in_file('{file_name}', '{search_query}')")
    success, content = local_memory.search_in_file(folder_name, file_name, search_query)
    return content if success else f"לא מצאתי את המידע {search_query} בקובץ."

def get_current_time() -> str:
    """מחזיר את השעה והתאריך הנוכחיים. השתמש בזה כשהבוס שואל מה השעה."""
    return datetime.datetime.now().strftime("%H:%M, %A, %d/%m/%Y")

def shutdown_system() -> str:
    """מכבה את הרסברי פאי לחלוטין. השתמש אך ורק כשהבוס מבקש במפורש לכבות את המערכת או את הרסברי פאי."""
    print("[INFO] AI executing: shutdown_system()")
    os.system("sudo shutdown -h now")
    return "מכבה את המערכת."

# רשימת הכלים שאנחנו נותנים למוח של ג'ארוויס (כולל חיפוש בגוגל מובנה!)
jarvis_tools = [
    check_general_emails,
    search_specific_email,
    create_new_folder,
    add_note_to_file,
    read_file_content,
    search_in_file,
    get_current_time,
    shutdown_system,
    remember_fact
    
]


# --- 4. Init Gemini Brain ---
print("Initializing Gemini V2 Brain...", end='', flush=True)
try:
    client = genai.Client(api_key=GEMINI_KEY)
    
    # הוראת העל - פשוטה, ברורה, ונותנת לו אוטונומיה מלאה
    sys_prompt = """You are Jarvis, a highly advanced, intelligent AI voice assistant for your boss (Amit).
Your main superpower is the ability to USE TOOLS. You have tools to check emails, manage notes/files, check the time, search the web, and even shutdown the system.
Whenever the user asks you to do something, THINK if you have a tool for it. If you do, USE IT. Do not guess.

Rules for Voice Output:
1. Keep answers extremely short, conversational, and natural in Hebrew.
2. If you use a tool to fetch info (like emails), summarize the results nicely and briefly.
3. NEVER output markdown (like * or **).
4. If the user implies exit/stop/goodbye, output exactly the word: [EXIT]
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

# --- 5. Speech & Audio Functions (ללא שינוי, עובדות מושלם) ---
def contains_hebrew(text):
    return bool(re.search(r'[\u0590-\u05FF]', text))

def speak(text, porcupine=None, pa=None):
    clean_text = re.sub(r'<[^>]+>', '', text).replace("*", "").strip()
    if not clean_text: return False
    
    print(f"\n[Jarvis]: {clean_text}")

    try:
        voice = "he-IL-AvriNeural" if contains_hebrew(clean_text) else "en-GB-RyanNeural"
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


# --- 6. The V2 Conversation Loop (תראה איזה נקי זה!) ---
def run_conversation_session(porcupine, pa):
    silence_count = 0
    
    while True:
        try:
            user_input = listen()
            
            # ניהול שתיקות
            if not user_input:
                silence_count += 1
                if silence_count == 1:
                    was_interrupted = speak("תרצה עוד משהו?", porcupine, pa)
                    if was_interrupted: silence_count = 0 
                    continue
                else:
                    speak("Back to standbye", porcupine, pa)
                    break
            
            silence_count = 0
            print(f"\n[You]: {user_input}")
            user_text = user_input.lower()
            
            # יציאה מהירה
            exit_words = ["בטל", "עזוב", "לא משנה", "מספיק", "תודה", "זהו", "ביי", "stop", "exit"]
            if any(word in user_text for word in exit_words) or user_text.strip() == "לא":
                speak("בסדר גמור, אני כאן אם תצטרך.", porcupine, pa)
                break
            
            # אינדיקציה קולית - בודקים אם יש צורך לפנות לכלים
            if any(word in user_text for word in ["מייל", "הודעות", "חפש", "מה", "מי", "מזג אוויר"]):
                speak("בודק את זה...", porcupine, pa)

            # הקסם: מעבירים את המשפט כמות שהוא למוח. ג'מיני כבר יחליט איזה כלי להפעיל!
            response = chat.send_message(user_input)
            
            if "[EXIT]" in response.text:
                speak("Goodbye sir. ", porcupine, pa)
                break
            else:
                speak(response.text, porcupine, pa)
            
        except Exception as e:
            print(f"[Error] V2 Loop Exception: {e}")
            speak("היתה לי תקלה קטנה במוח המרכזי. חוזר להמתנה.", porcupine, pa)
            break

# --- 7. Main Engine (Wake Word) ---
def run_jarvis():
    try:
        porcupine = pvporcupine.create(access_key=PORCUPINE_KEY, keywords=['jarvis'])
    except Exception as e:
        print(f"Porcupine Error: {e}")
        return

    pa = pyaudio.PyAudio()
    audio_stream = pa.open(rate=porcupine.sample_rate, channels=1, format=pyaudio.paInt16, input=True, frames_per_buffer=porcupine.frame_length)

    os.system('clear')
    speak("Jarvis V2 Core is online. Awaiting command.")
    print("\n[INFO] Listening for wake word 'Jarvis'...")

    try:
        while True:
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

            if porcupine.process(pcm) >= 0:
                print("\n[WAKE SAME WORD DETECTED]")
                # שינינו כאן ל-wake.mp3
                subprocess.run(['mpv', '/home/kido1/Smartroom/wake.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
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