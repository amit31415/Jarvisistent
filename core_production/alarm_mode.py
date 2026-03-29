import time
import datetime
import threading
import subprocess
import os
import json
import random
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
        
        if not os.path.exists(ALARMS_FILE):
            self._save_alarms([])

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
        print("\n[ALARM] Noise loop started! Picking a random sound...", flush=True)
        alarms_dir = '/home/kido1/Smartroom/alarms'
        fallback_alarm = '/home/kido1/Smartroom/alert.mp3'
        
        available_alarms = []
        if os.path.exists(alarms_dir):
            available_alarms = [f for f in os.listdir(alarms_dir) if f.endswith('.mp3')]
        
        if available_alarms:
            chosen_file = random.choice(available_alarms)
            alert_path = os.path.join(alarms_dir, chosen_file)
            print(f"[ALARM] Playing: {chosen_file}", flush=True)
        else:
            alert_path = fallback_alarm
            print("[ALARM] No custom alarms found. Using fallback alert.", flush=True)
            
        while self.state == "RINGING":
            try:
                # "timeout 3" מבטיח שהנגן ייהרג בוודאות אחרי 3 שניות, לא משנה מה אורך הקובץ
                subprocess.run(['timeout', '3', 'mpv', alert_path, '--volume=70', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"[ALARM ERROR] MPV failed: {e}", flush=True)
            
            # חלון שקט מורחב: 4 שניות של דממה כדי שהג'אברה יפתח את המיקרופון חזרה
            time.sleep(4)

    def _trivia_timeout(self):
        """גלאי הירדמות: אם הבוס מתעלם 45 שניות, האזעקה חוזרת"""
        time_left = 45
        while time_left > 0 and self.state == "TRIVIA":
            time.sleep(1)
            time_left -= 1
            
        if self.state == "TRIVIA":
            print("\n[ALARM] User ignored the question! Resuming noise...", flush=True)
            self.state = "RINGING"
            threading.Thread(target=self._noise_loop, daemon=True).start()

    def process_voice_command(self, text):
        if self.state == "RINGING":
            if any(word in text for word in ["סתום", "די", "תפסיק", "כבה", "עצור", "מספיק"]):
                self.state = "TRIVIA"
                
                # ההוראה עודכנה לשאלות הגיוניות יותר
                prompt = "תמציא שאלת ידע כללי קלילה עד בינונית. משהו שרוב האנשים יודעים אבל דורש חצי דקה של ריכוז על הבוקר (למשל: כמה ימים יש בשנה מעוברת, מה בירת צרפת, איזה כוכב לכת הכי קרוב לשמש). תחזיר רק את השאלה בעברית, ללא התשובה וללא מרכאות."
                try:
                    self.question = self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
                except:
                    self.question = "כמה ימים יש בשנה מעוברת?" 
                    
                # מפעיל את טיימר ההירדמות (45 שניות)
                threading.Thread(target=self._trivia_timeout, daemon=True).start()
                    
                return f"אני לא סותם. בוא נראה שהמוח שלך פועל. הנה השאלה של הבוקר: {self.question}"
            return None 
            
        elif self.state == "TRIVIA":
            # טיפול בבקשה לחזור על השאלה
            if any(word in text for word in ["מה", "שוב", "תחזור", "לא הבנתי", "לא שמעתי", "איזה"]):
                # מחזיר את השאלה אבל מאפס להם שוב את שעון ה-45 שניות מחדש ע"י קריאה חוזרת לפונקציה
                threading.Thread(target=self._trivia_timeout, daemon=True).start()
                return f"אני חוזר על השאלה: {self.question}"
                
            # בודק אם התשובה נכונה
            prompt = f"השאלה הייתה: '{self.question}'. המשתמש ענה עכשיו: '{text}'. האם התשובה שלו נכונה או קרובה מספיק? תחזיר רק מילה אחת: 'כן' או 'לא'."
            try:
                res = self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
                if "כן" in res.lower() or "yes" in res.lower():
                    self.state = "IDLE"
                    return "תשובה נכונה. בוקר טוב עמית, השעון כובה."
                else:
                    # עונש על תשובה שגויה: חוזר לצפצף!
                    self.state = "RINGING"
                    threading.Thread(target=self._noise_loop, daemon=True).start()
                    return "טעות! חוזר לצפצף. תגיד לי לעצור כשתרצה לנסות שוב."
            except:
                self.state = "IDLE"
                return "אני לא מצליח לבדוק את התשובה, אבל נניח שצדקת. בוקר טוב."
                
        return None