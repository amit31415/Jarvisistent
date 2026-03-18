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
import google_api 
from dotenv import load_dotenv
from ctypes import *
from google import genai
from google.genai import types
import local_memory

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

# --- 2. Load Keys ---
load_dotenv()
GEMINI_KEY = os.getenv("GEMINI_KEY")
PORCUPINE_KEY = os.getenv("PORCUPINE_KEY")

if not GEMINI_KEY or not PORCUPINE_KEY:
    print("\n[Error] Missing API Keys in .env")
    sys.exit(1)

# --- 3. Init Gemini Brain ---
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
    print(f"\n[Error] Brain offline: {e}")
    sys.exit(1)

# --- API Quota Tracker ---
DAILY_API_LIMIT = 1500
QUOTA_FILE = "api_quota.json"

def log_api_call():
    today = datetime.date.today().isoformat()
    try:
        with open(QUOTA_FILE, "r") as f:
            data = json.load(f)
    except:
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

# --- Telemetry ---
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

# --- Speech & Audio ---
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

def ask_brain(text):
    now = datetime.datetime.now().strftime("%H:%M, %A, %d/%m/%Y")
    enriched_text = f"[System Time: {now}]. User says: {text}"
    log_api_call() 
    try:
        response = chat.send_message(enriched_text)
        return response.text.strip()
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return "הגעתי למגבלת הפניות. נסה שוב בעוד רגע."
        return "יש לי תקלה בחיבור לרשת."

# --- Conversation Loop & Dialog Manager (State Machine) ---
def run_conversation_session(porcupine, pa):
    silence_count = 0
    active_intent = None
    slots = {"type": None, "name": None, "folder": None, "content": None, "search_term": None}
    awaiting_slot = None
    
    while True:
        try:
            user_input = listen()
            
            if not user_input:
                if active_intent and awaiting_slot:
                    silence_count += 1
                    if silence_count == 1:
                        speak("אני עדיין מקשיב. לא שמעתי את התשובה.", porcupine, pa)
                        continue
                    else:
                        speak("ביטלתי את הפעולה עקב חוסר תגובה. חוזר להמתנה.", porcupine, pa)
                        active_intent = None
                        slots = {"type": None, "name": None, "folder": None, "content": None, "search_term": None}
                        awaiting_slot = None
                        silence_count = 0
                        break 
                else:
                    silence_count += 1
                    if silence_count == 1:
                        was_interrupted = speak("תרצה עוד משהו?", porcupine, pa)
                        if was_interrupted: silence_count = 0 
                        continue
                    else:
                        speak("חוזר למצב המתנה.", porcupine, pa)
                        break
            
            silence_count = 0
            print(f"\n[You]: {user_input}")
            user_text = user_input.lower()
            
            exit_words = ["בטל", "תבטל", "עזוב", "לא משנה", "לא", "מספיק", "תודה", "זהו", "ביי", "stop", "exit"]
            if any(word in user_text for word in exit_words) or user_text.strip() == "לא":
                if active_intent:
                    speak("בוטל.", porcupine, pa)
                    active_intent = None
                    slots = {"type": None, "name": None, "folder": None, "content": None, "search_term": None}
                    awaiting_slot = None
                    continue
                else:
                    speak("בסדר גמור, אני כאן אם תצטרך.", porcupine, pa)
                    break
                    
            if "מה השעה" in user_text or "זמן" in user_text:
                now = datetime.datetime.now().strftime("%H:%M")
                speak(f"השעה עכשיו היא {now}.", porcupine, pa)
                continue
                
            # --- System Power Control ---
            if "כיבוי" in user_text and ("מערכת" in user_text or "רסברי" in user_text):
                speak("מכבה את הרסברי פאי. לילה טוב אדוני.", porcupine, pa)
                time.sleep(1) # נותן לו שנייה לסיים לדבר
                os.system("sudo shutdown -h now")
                sys.exit(0)

# --- Mail Integration ---
            specific_email_match = re.search(r'(?:מייל|הודעה|מיילים|הודעות).*?(?:מ|של|מאת|בנושא) (.*)', user_text)
            
            if specific_email_match:
                search_term = specific_email_match.group(1).strip()
                speak(f"מחפש את המייל הקשור ל{search_term}, רק רגע...", porcupine, pa)
                print(f"[INFO] Searching specific email for: {search_term}")
                
                raw_emails = google_api.get_specific_email(search_term)
                
                if "לא מצאתי" in raw_emails:
                    speak(raw_emails, porcupine, pa)
                else:
                    prompt = f"אתה ג'ארוויס. הבוס ביקש פרטים על מייל שקשור ל'{search_term}'. הנה התוצאות המלאות מהתיבה שלו:\n{raw_emails}\n\nקרא את התוכן וספק לו סיכום קולי מלא, מפורט וענייני של מה שכתוב שם."
                    response = ask_brain(prompt)
                    speak(response, porcupine, pa)
                continue

            elif "מייל" in user_text or "הודעות" in user_text:
                speak("אני סורק את תיבת הדואר שלך, אדוני. מיד אעדכן.", porcupine, pa)
                print("[INFO] Fetching emails...")
                raw_emails = google_api.get_unread_emails(max_results=40)
                
                if "אין לך הודעות חדשות" in raw_emails:
                    response = "בדקתי את התיבה אדוני, אין לך הודעות חדשות משלושת הימים האחרונים."
                else:
                    email_prompt = f"""
אתה העוזר האישי ג'ארוויס. קיבלת רשימת מיילים שלא נקראו מ-3 הימים האחרונים של הבוס (עמית).
עליך לתת לו עדכון קולי חכם, קצר וטבעי, לפי החוקים הבאים:

חלק 1: רשת ביטחון (פספוסים מאתמול ושלשום):
סרוק את המיילים מהימים הקודמים. אם יש מייל מאדם אמיתי (לא מערכת), פתח ואמור: "אדוני, יש מייל שפספסת מ[שם] בנושא [נושא]". אם אין, דלג.

חלק 2: עדכוני היום:
- אנשים אמיתיים: פרט מי שלח, מה הנושא ובמשפט אחד מה כתוב.
- מערכות אוניברסיטה (appeals, heshbons): תן משפט עדכון קצר.

חלק 3: השתקה:
מיילים מ-BguAnnouncements או הודעות אגודה - אסור לך להקריא את התוכן! בסוף הדיווח ציין משפט אחד: "בנוסף, יש לך עוד X הודעות מערכת מהאוניברסיטה, תרצה שאעבור עליהן?".

הנה המיילים הגולמיים:
{raw_emails}
"""
                    response = ask_brain(email_prompt) 
                
                speak(response, porcupine, pa) 
                continue

            if active_intent and awaiting_slot:
                if awaiting_slot == "type":
                    if "תיקי" in user_text: slots["type"] = "folder"
                    elif "קובץ" in user_text or "פתק" in user_text: slots["type"] = "file"
                elif awaiting_slot == "name":
                    clean_name = re.sub(r'בשם|לקובץ|לתיקייה', '', user_text).strip()
                    if clean_name: slots["name"] = clean_name.split()[0]
                elif awaiting_slot == "content":
                    slots["content"] = user_text.strip()
                elif awaiting_slot == "search_term":
                    slots["search_term"] = user_text.strip()
                awaiting_slot = None 
            
            name_match = re.search(r'בשם ([א-תa-zA-Z0-9_]+)', user_text)
            if name_match: slots["name"] = name_match.group(1)
            
            folder_match = re.search(r'בתיקיית ([א-תa-zA-Z0-9_]+)', user_text)
            if folder_match: slots["folder"] = folder_match.group(1)

            if not active_intent:
                if any(w in user_text for w in ["צור", "ליצור", "תיצור", "תייצר"]):
                    active_intent = "CREATE"
                    if "תיקי" in user_text: slots["type"] = "folder"
                    elif "קובץ" in user_text: slots["type"] = "file"
                elif any(w in user_text for w in ["תוסיף", "תכתוב"]):
                    active_intent = "ADD_NOTE"
                    content_match = re.search(r'(?:תוסיף|תכתוב|הערה|משימה) (.*?)(?:לקובץ|בשם|בתיקיית|$)', user_text)
                    if content_match and content_match.group(1).strip():
                        clean_content = content_match.group(1).strip()
                        if clean_content not in ["הערה", "משימה", "את", "ל"]:
                            slots["content"] = clean_content
                elif any(w in user_text for w in ["תקריא", "מה כתוב"]):
                    active_intent = "READ"
                elif "חפש" in user_text or ("מה " in user_text and " שלי" in user_text):
                    active_intent = "SEARCH"
                    if "מה " in user_text:
                        term_match = re.search(r'מה (.*?) שלי', user_text)
                        if term_match: slots["search_term"] = term_match.group(1).strip()
                    elif "חפש" in user_text:
                        term_match = re.search(r'חפש (.*?)(?:בקובץ|בשם|בתיקיית|$)', user_text)
                        if term_match: slots["search_term"] = term_match.group(1).strip()

            if active_intent:
                if active_intent == "CREATE":
                    if not slots["type"]:
                        awaiting_slot = "type"
                        speak("מה ליצור? תיקייה או קובץ?", porcupine, pa)
                        continue
                    if not slots["name"]:
                        awaiting_slot = "name"
                        tipo = "תיקייה" if slots["type"] == "folder" else "קובץ"
                        speak(f"באיזה שם לקרוא ל{tipo}?", porcupine, pa)
                        continue
                    speak(f"מייצר {slots['type']} בשם {slots['name']}...", porcupine, pa)
                    if slots["type"] == "folder":
                        local_memory.create_folder(slots["name"])
                    else:
                        local_memory.save_note(slots["folder"], slots["name"], "נוצר בהצלחה.")
                    speak("בוצע.", porcupine, pa)
                    
                elif active_intent == "ADD_NOTE":
                    if not slots["content"]:
                        awaiting_slot = "content"
                        speak("מה להוסיף?", porcupine, pa)
                        continue
                    if not slots["name"]:
                        awaiting_slot = "name"
                        speak("לאיזה קובץ? תגיד 'בשם' ואז את השם.", porcupine, pa)
                        continue
                    speak(f"מעדכן את קובץ {slots['name']}...", porcupine, pa)
                    local_memory.save_note(slots["folder"], slots["name"], slots["content"])
                    speak("הוספתי בהצלחה.", porcupine, pa)
                    
                elif active_intent == "READ":
                    if not slots["name"]:
                        awaiting_slot = "name"
                        speak("איזה קובץ להקריא? תגיד 'בשם' ואז את השם.", porcupine, pa)
                        continue
                    speak(f"פותח את קובץ {slots['name']}...", porcupine, pa)
                    success, content = local_memory.read_full_file(slots["folder"], slots["name"])
                    if success:
                        speak(f"הנה מה שכתוב שם. {content}", porcupine, pa)
                    else:
                        speak("לא מצאתי את הקובץ הזה.", porcupine, pa)
                        
                elif active_intent == "SEARCH":
                    if not slots["search_term"]:
                        awaiting_slot = "search_term"
                        speak("מה לחפש?", porcupine, pa)
                        continue
                    if not slots["name"]:
                        awaiting_slot = "name"
                        speak("באיזה קובץ לחפש? תגיד 'בשם' ואז את השם.", porcupine, pa)
                        continue
                    speak(f"מחפש את המידע בקובץ {slots['name']}...", porcupine, pa)
                    success, content = local_memory.search_in_file(slots["folder"], slots["name"], slots["search_term"])
                    if success:
                        speak(f"מצאתי: {content}", porcupine, pa)
                    else:
                        speak("לא מצאתי את המידע הזה בקובץ.", porcupine, pa)

                active_intent = None
                slots = {"type": None, "name": None, "folder": None, "content": None, "search_term": None}
                continue

            if not active_intent:
                # אינדיקציה קולית לחיפושים כלליים או שאלות שלוקחות זמן
                internet_keywords = ["חפש", "מי זה", "מה זה", "מזג אוויר", "חדשות", "אינטרנט", "למה", "איך"]
                if any(word in user_text for word in internet_keywords):
                    speak("אני בודק את זה עבורך, אדוני...", porcupine, pa)
                    
                response = ask_brain(user_input)
                if "[EXIT]" in response:
                    speak(response, porcupine, pa)
                    break
                else:
                    speak(response, porcupine, pa)
            
        except Exception as e:
            print(f"[Error] Loop Exception: {e}")
            speak("היתה לי תקלה קטנה בלולאה. חוזר להמתנה.", porcupine, pa)
            break

def get_specific_email(search_query, max_results=3):
    """מחפש מייל ספציפי לפי מילת חיפוש (שם שולח, נושא) מ-14 הימים האחרונים"""
    try:
        service = get_gmail_service()
        # מחפש את המילה שביקשת בשבועיים האחרונים
        query = f"{search_query} newer_than:14d"
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"לא מצאתי מיילים התואמים לחיפוש '{search_query}' בשבועיים האחרונים."

        email_data = []
        for index, msg in enumerate(messages, 1):
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message.get('payload', {})
            headers = payload.get('headers', [])

            subject = "ללא נושא"
            sender = "לא ידוע"
            date_sent = "לא ידוע"

            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                if header['name'] == 'From':
                    sender = header['value'].split('<')[0].strip()
                if header['name'] == 'Date':
                    date_sent = header['value']

            full_body = get_email_body(payload)
            if not full_body.strip():
                full_body = message.get('snippet', '')

            # כאן אנחנו שולחים לג'מיני את כל התוכן בלי לחתוך, כי הבוס רוצה ניתוח מלא
            email_data.append(f"מייל {index}:\nתאריך: {date_sent}\nמאת: {sender}\nנושא: {subject}\nתוכן מלא:\n{full_body.strip()}")

        return "\n\n====================\n\n".join(email_data)

    except Exception as e:
        return f"[ERROR] Failed to fetch specific email: {e}"

# --- Main Engine (Wake Word) ---
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