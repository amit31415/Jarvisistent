import time
import datetime
import threading
import subprocess
import os
import json
from dotenv import load_dotenv
from google import genai

load_dotenv()

ALARMS_FILE = 'alarms_memory.json'

class AlarmManager:
    def __init__(self):
        self.state = "IDLE" 
        self.question = ""
        self.gemini_key = os.getenv("GEMINI_KEY")
        self.gemini_client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None
        
        # מוודא שקובץ הג'ייסון קיים בעלייה
        if not os.path.exists(ALARMS_FILE):
            self._save_alarms([])

        # האוזן שבודקת את השעות רצה תמיד ברקע
        threading.Thread(target=self._wait_loop, daemon=True).start()

    def _load_alarms(self):
        try:
            with open(ALARMS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []

    def _save_alarms(self, alarms):
        with open(ALARMS_FILE, 'w') as f:
            json.dump(alarms, f, indent=4)

    def set_alarm(self, time_str):
        alarms = self._load_alarms()
        if time_str not in alarms:
            alarms.append(time_str)
            self._save_alarms(alarms)
            return f"הוספתי שעון מעורר לשעה {time_str}. הוא נשמר בזיכרון."
        return f"כבר יש לך שעון מכוון לשעה {time_str}."

    def cancel_alarm(self, time_str=None):
        # אם השעון מצלצל עכשיו ואמרת לבטל, נשתיק אותו ישר
        if self.state in ["RINGING", "TRIVIA"]:
            self.state = "IDLE"
            return "השתקתי את השעון שפועל עכשיו."
            
        alarms = self._load_alarms()
        if not alarms:
            return "אין לך שעונים מעוררים במערכת."
            
        if time_str and time_str in alarms:
            alarms.remove(time_str)
            self._save_alarms(alarms)
            return f"השעון של שעה {time_str} בוטל ונמחק מהזיכרון."
        elif time_str == "all" or not time_str:
            self._save_alarms([])
            return "כל השעונים המעוררים נמחקו."
            
        return f"לא מצאתי שעון לשעה {time_str}."

    def get_alarms(self):
        alarms = self._load_alarms()
        if not alarms:
            return "אין שעונים מעוררים מכוונים כרגע."
        return "השעונים המכוונים כרגע הם לשעות: " + ", ".join(alarms)

    def _wait_loop(self):
        last_printed_min = ""
        while True:
            if self.state == "IDLE":
                now = datetime.datetime.now().strftime("%H:%M")
                alarms = self._load_alarms()
                
                if now != last_printed_min:
                    # הוספנו flush=True כדי שזה בטוח יופיע בלוגים שלך
                    print(f"\n[DEBUG ALARM] Python Time: {now} | Loaded Alarms: {alarms}", flush=True)
                    last_printed_min = now
                
                if now in alarms:
                    print(f"\n[ALARM TRIGGERED] Waking up the boss! Time is {now}!", flush=True)
                    self.state = "RINGING"
                    
                    try:
                        alarms.remove(now)
                        self._save_alarms(alarms)
                    except:
                        pass
                    
                    threading.Thread(target=self._noise_loop, daemon=True).start()
            
            time.sleep(10)

    def _noise_loop(self):
        print("\n[ALARM] Noise loop started! Playing sound...", flush=True)
        # שמנו נתיב מוחלט כדי ש-MPV לא ילך לאיבוד ברקע
        alert_path = '/home/kido1/Smartroom/YaFat3.mp3'
        
        while self.state == "RINGING":
            try:
                subprocess.run(['mpv', alert_path, '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[ALARM ERROR] MPV failed: {e}", flush=True)
            
            time.sleep(2)

    def process_voice_command(self, text):
        if self.state == "RINGING":
            if any(word in text for word in ["סתום", "די", "תפסיק", "כבה", "עצור", "מספיק"]):
                self.state = "TRIVIA"
                prompt = "תמציא שאלת ידע כללי קשה שדורשת מחשבה (למשל על חלל, פיזיקה, היסטוריה). תחזיר רק את השאלה בעברית, ללא התשובה וללא מרכאות."
                try:
                    self.question = self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
                except:
                    self.question = "מה גורם לכוכב להפוך לסופרנובה?" 
                    
                return f"אני לא סותם אם אתה לא קם! בוא נראה שהמוח שלך פועל. הנה השאלה של הבוקר: {self.question}"
            return None 
            
        elif self.state == "TRIVIA":
            prompt = f"השאלה הייתה: '{self.question}'. המשתמש ענה עכשיו: '{text}'. האם התשובה שלו נכונה או קרובה מספיק כדי להוכיח שהוא מפעיל את המוח? תחזיר רק מילה אחת: 'כן' או 'לא'."
            try:
                res = self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
                if "כן" in res.lower() or "yes" in res.lower():
                    self.state = "IDLE"
                    return "תשובה נכונה. בוקר טוב עמית, השעון כובה."
                else:
                    return "טעות! תחשוב שוב או שהצפצופים יחזרו. מה התשובה?"
            except:
                self.state = "IDLE"
                return "אני לא מצליח לבדוק את התשובה, אבל נניח שצדקת. בוקר טוב."
                
        return None