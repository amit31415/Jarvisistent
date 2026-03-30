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
import google_api 
import local_memory
from dotenv import load_dotenv
from ctypes import *
from google import genai
from google.genai import types
from study_mode import StudyManager
from alarm_mode import AlarmManager
alarm_manager = AlarmManager()

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
    """מחפש וקורא מייל ספציפי לפי שם שולח או נושא."""
    print(f"[INFO] AI executing: search_specific_email(search_term='{search_term}')")
    try:
        result = google_api.get_specific_email(search_term)
        print(f"\n[DEBUG RAW OUTPUT]: {result}\n")
        return result
    except Exception as e:
        print(f"\n[CRITICAL ERROR]: {str(e)}")
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
    """מכבה את הרסברי פאי לחלוטין. השתמש אך ורק כשהבוס מבקש במפורש לכבות את המערכת או את הרסברי פאי. ןמשממש מפורשות במילה shutdown"""
    print("[INFO] AI executing: shutdown_system()")
    os.system("sudo shutdown -h now")
    return "מכבה את המערכת."

def search_web(query: str) -> str:
    """מחפש מידע בזמן אמת באינטרנט. השתמש בזה כשהבוס מבקש לדעת משהו על העולם, חדשות, או להסביר מושג."""
    print(f"[INFO] AI executing: search_web('{query}')")
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        html = urllib.request.urlopen(req).read().decode('utf-8')
        
        # חילוץ התוצאות מהקוד של האתר
        snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
        if not snippets:
            return "לא מצאתי תוצאות ברשת."
        
        # ניקוי תגיות והחזרת 3 התוצאות הראשונות
        clean_snippets = [re.sub(r'<[^>]+>', '', s).strip() for s in snippets[:3]]
        return "תוצאות חיפוש מהאינטרנט:\n" + "\n".join(clean_snippets)
    except Exception as e:
        return f"שגיאת תקשורת בחיפוש: {e}"

def check_calendar(query: str) -> str:
    """מושך את האירועים והפגישות הקרובות מהיומן (Google Calendar) של הבוס. השתמש בזה כששואלים על לו"ז, פגישות, או מה מתוכנן.
    
    Args:
        query: פשוט תעביר לכאן את מילת החיפוש או בקשת המשתמש (למשל 'לוז')
    """
    print("\n[INFO] AI executing: check_calendar()")
    try:
        result = google_api.get_upcoming_events()
        print(f"[DEBUG CALENDAR RAW]: {result}\n")
        return result
    except Exception as e:
        return f"שגיאה בקריאת היומן: {str(e)}"

def manage_study_mode(action: str, minutes: int = 0) -> str:
    """
    מנהל את מצב הלמידה (Pomodoro Timer) של הבוס.
    השתמש בכלי זה כאשר הבוס מבקש:
    1. להתחיל ללמוד ('start')
    2. לעצור ולבטל לחלוטין ('stop')
    3. להשהות/לעשות פאוזה לטיימר ('pause')
    4. להמשיך טיימר שהושהה ('resume')
    5. לצאת להפסקה ('break')
    6. לשאול כמה זמן נשאר ('status')
    7. להוסיף, להאריך, להוריד או לקצר את הזמן ('add_time'). 
       * חובה להעביר את כמות הדקות בפרמטר minutes. (מספר חיובי כדי להוסיף, ומספר שלילי כדי לקצר/להוריד).
    
    Args:
        action: חובה לבחור: 'start', 'stop', 'pause', 'resume', 'break', 'status', 'add_time'.
        minutes: מספר הדקות להוסיף או להוריד (רלוונטי רק לפעולת add_time).
    """
    print(f"[INFO] AI executing: manage_study_mode(action='{action}', minutes={minutes})")
    
    if action == 'start':
        return study_manager.start_study()
    elif action == 'stop':
        return study_manager.stop_study()
    elif action == 'pause':
        return study_manager.pause_study()
    elif action == 'resume':
        return study_manager.resume_study()
    elif action == 'break':
        return study_manager.start_break()
    elif action == 'status':
        return study_manager.get_time_left()
    elif action == 'add_time':
        return study_manager.add_time(minutes)
        
    return "פעולה לא חוקית."

def manage_alarm_clock(action: str, time_str: str = "") -> str:
    """
    מנהל את השעונים המעוררים של הבוס. כל השעונים נשמרים בקובץ זיכרון.
    פעולות אפשריות (action):
    1. 'set' - כיוון שעון מעורר חדש. 
       * חובה להעביר את השעה בפרמטר time_str בפורמט 24 שעות (HH:MM). המר את המילים של הבוס לפורמט זה.
    2. 'cancel' - ביטול שעון. העבר את השעה (HH:MM) ב-time_str כדי למחוק שעון ספציפי, או השאר ריק/העבר 'all' כדי למחוק הכל.
    3. 'list' - כשהבוס שואל אילו שעונים מכוונים לו או מתי הוא צריך לקום.
    """
    print(f"[INFO] AI executing: manage_alarm_clock(action='{action}', time_str='{time_str}')")
    
    if action == 'set':
        if not time_str:
            return "חובה לציין שעה בפורמט HH:MM."
        return alarm_manager.set_alarm(time_str)
    elif action == 'cancel':
        return alarm_manager.cancel_alarm(time_str)
    elif action == 'list':
        return alarm_manager.get_alarms()
        
    return "פעולה לא חוקית."

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
    remember_fact,
    search_web,
    check_calendar,
    manage_study_mode,
    manage_alarm_clock
]

study_manager = StudyManager()


# --- 4. Init Gemini Brain ---
print("Initializing Gemini V2 Brain...", end='', flush=True)
try:
    client = genai.Client(api_key=GEMINI_KEY)
    
    # -- שאיבת הזיכרון לתוך התת-מודע --
    memory_context = ""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            try:
                memories = json.load(f)
                if memories:
                    memory_context = "\nCRITICAL CONTEXT - HERE ARE IMPORTANT FACTS YOU MUST REMEMBER ABOUT THE USER AND THE ROOM:\n"
                    for i, fact in enumerate(memories):
                        memory_context += f"{i+1}. {fact}\n"
            except:
                pass

    # הוראת העל - עכשיו כוללת גם את הזיכרונות!
    sys_prompt = f"""You are Jarvis, a highly advanced, intelligent AI voice assistant for your boss (Amit).
Your main superpower is the ability to USE TOOLS. You have tools to check emails, manage notes/files, check the time, search the web, and even shutdown the system.
Whenever the user asks you to do something, THINK if you have a tool for it. If you do, USE IT. Do not guess.

{memory_context}

CRITICAL DETECTIVE MODE & HONESTY RULE: You are a brilliant analytical thinker. You can cross-reference facts from your memory to make logical deductions.
HOWEVER, YOU MUST NEVER INVENT FACTS. If you do not know something for sure, or if you are making an educated guess/deduction based on facts, you MUST explicitly state that it is a guess. 
Use phrases like "אני מניח ש...", "אם אני צריך לנחש...", or "אני לא יודע בוודאות, אבל אני מסיק ש...". 
Never present a deduction or a guess as an absolute fact.

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

def get_audio_stream(pa, sample_rate, frame_length):
    """מחפש ספציפית את המיקרופון של הג'אברה או USB כדי למנוע קריסות של לינוקס"""
    device_index = None
    
    # סורק את כל ההתקנים ומחפש ספציפית את הג'אברה
    for i in range(pa.get_device_count()):
        dev_info = pa.get_device_info_by_index(i)
        if dev_info.get('maxInputChannels', 0) > 0:
            name = dev_info.get('name', '')
            if "Jabra" in name or "USB" in name:
                device_index = i
                print(f"[INFO] 🎯 Locked on Jabra/USB Mic at Index {i}")
                break
                
    # אם משום מה הג'אברה נותק, ננסה לקחת את הראשון שעובד כגיבוי אחרון
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

def speak(text, porcupine=None, pa=None):
    clean_text = re.sub(r'<[^>]+>', '', text).replace("*", "").strip()
    if not clean_text: return False
    
    print(f"\n[Jarvis]: {clean_text}", flush=True)

    try:
        voice = "he-IL-AvriNeural" if contains_hebrew(clean_text) else "en-GB-RyanNeural"
        edge_tts_cmd = '/home/kido1/Smartroom/.venv/bin/edge-tts'

        # 1. מייצרים את קובץ הקול
        subprocess.run([
            edge_tts_cmd, '--text', clean_text, '--write-media', 'response.mp3',
            '--voice', voice, '--rate=+15%'
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. פקודה חוסמת: ג'ארוויס מדבר ואוטם אוזניים. פייתון לא מתקדם שורה עד שהדיבור מסתיים!
        subprocess.run(['mpv', 'response.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 3. מרווח נשימה: נותנים לכרטיס הקול של הג'אברה חצי שנייה להתאפס לפני שהמיקרופון נפתח שוב
        import time
        time.sleep(0.5)
        
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
            audio = r.listen(source, timeout=2, phrase_time_limit=10)
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
            #if not user_input:
            #    silence_count += 1
            #    if silence_count == 1:
            #        was_interrupted = speak("is there sonthing else sir?", porcupine, pa)
            #        if was_interrupted: silence_count = 0 
            #        continue
            #    else:
            #        speak("very well. Back to standbye", porcupine, pa)
            #        break
            # ניהול שתיקות חכם - יודע להישאר ער כשיש נדנוד פעיל
            if not user_input:
                silence_count += 1
                
                # האם מנהל הלמידה חופר לו כרגע?
                if study_manager.is_nagging():
                    # אם כן, אל תשאל שאלות מנומסות ואל תחזור לסטנדביי!
                    # פשוט תאפס את השתיקה ותמשיך להאזין לו בשקט כדי שיוכל לצעוק "קמתי"
                    silence_count = 0
                    continue
                
                if silence_count == 1:
                    was_interrupted = speak("is there sonthing else sir?", porcupine, pa)
                    if was_interrupted: silence_count = 0 
                    continue
                else:
                    speak("very well. Back to standbye", porcupine, pa)
                    break
            
            silence_count = 0
            print(f"\n[You]: {user_input}")
            user_text = user_input.lower()

            # --- השתלת מוח: שעון מעורר טריוויה ---
            alarm_response = alarm_manager.process_voice_command(user_text)
            if alarm_response:
                speak(alarm_response, porcupine, pa)
                continue
            # --------------------------------------
            
            # יציאה מהירה
            exit_words = ["בטל", "עזוב", "לא משנה", "מספיק", "תודה", "זהו", "ביי", "stop", "exit"]
            if any(word in user_text for word in exit_words) or user_text.strip() == "לא":
                speak("בסדר גמור, אני כאן אם תצטרך.", porcupine, pa)
                break
            
            
            # אינדיקציה קולית - בודקים אם יש צורך לפנות לכלים
            # אינדיקציה קולית דינמית וחכמה
            if any(word in user_text for word in ["מייל", "מיילים", "הודעות"]):
                feedback = random.choice(["פותח תיבת דואר...", "מציץ במיילים...", "שנייה, שולף הודעות..."])
                speak(feedback, porcupine, pa)
            elif any(word in user_text for word in ["חפש", "אינטרנט", "מזג אוויר", "חדשות"]):
                feedback = random.choice(["מחפש ברשת...", "מריץ חיפוש...", "בודק אונליין..."])
                speak(feedback, porcupine, pa)
            elif any(word in user_text for word in ["קובץ", "תיקייה", "פתק", "תזכור", "שמור"]):
                feedback = random.choice(["ניגש לקבצים...", "מעדכן את הזיכרון...", "רושם..."])
                speak(feedback, porcupine, pa)
            elif any(word in user_text for word in ["למה", "איך", "מי", "מה", "מתי", "איפה"]):
                feedback = random.choice(["מעבד...", "רק רגע...", "תן לי לחשוב על זה..."])
                speak(feedback, porcupine, pa)

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
                try:
                    audio_stream.close()
                except:
                    pass
                time.sleep(2)
                try:
                    audio_stream = get_audio_stream(pa, porcupine.sample_rate, porcupine.frame_length)
                except:
                    pass
                continue

            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

            if porcupine.process(pcm) >= 0:
                print("\n[WAKE SAME WORD DETECTED]")
                subprocess.run(['mpv', '/home/kido1/Smartroom/wake.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                audio_stream.stop_stream()
                audio_stream.close()

                run_conversation_session(porcupine, pa)

                while True:
                    try:
                        audio_stream = get_audio_stream(pa, porcupine.sample_rate, porcupine.frame_length)
                        break
                    except Exception as e:
                        print(f"[WARNING] Waiting for microphone to become available... ({e})")
                        time.sleep(3)

                print("\n[INFO] Standing by...")

    except KeyboardInterrupt:
        print("\n[INFO] Shutting down Jarvis.")
    finally:
        if porcupine: porcupine.delete()
        if 'audio_stream' in locals() and audio_stream: audio_stream.close()
        if pa: pa.terminate()

if __name__ == "__main__":
    run_jarvis()
