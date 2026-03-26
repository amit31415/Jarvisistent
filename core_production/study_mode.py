import time
import threading
import requests
import os
import subprocess
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv() 

class StudyManager:
    def __init__(self):
        self.state = "IDLE"  
        self.end_time = 0
        self.remaining_paused_time = 0 
        self.previous_state = "IDLE"   
        self.last_update_id = 0 
        self.extra_break_time = 0

        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_BOT_ID")
        self.gemini_key = os.getenv("GEMINI_KEY")

        if self.gemini_key:
            self.gemini_client = genai.Client(api_key=self.gemini_key)
        else:
            self.gemini_client = None

        if self.bot_token and self.chat_id:
            self._flush_old_messages() 
            threading.Thread(target=self._telegram_listener_loop, daemon=True).start()

    def is_nagging(self):
        """פונקציית עזר ללולאה הראשית - האם אנחנו באמצע לחפור לבוס?"""
        return self.state in ["NAGGING_TO_BREAK", "NAGGING_TO_STUDY"]

    def _generate_nag_message(self, stage, context):
        """מבקש מג'מיני להמציא משפט נדנוד קריאייטיבי בזמן אמת"""
        if not self.gemini_client:
            return "קום כבר."
            
        bribe_text = ""
        if self.extra_break_time > 0:
            bribe_text = f"המערכת אישרה לך עכשיו אקסטרה {self.extra_break_time} דקות בונוס להפסקה. ציין את זה בפרומפט שלך כשאתה משחד אותו לקום."

        prompt = f"""
        אתה ג'ארוויס, העוזר האישי של עמית.
        המצב: {context}
        רמת הנדנוד: שלב {stage} (1 זה תזכורת חצופה, 5 זה עצבני, סרקסטי וחסר סבלנות).
        {bribe_text}
        
        המשימה שלך: תכתוב משפט קצר אחד, בעברית. אל תהיה מנומס. תהיה עוקצני, חצוף, שנון, כמו חבר שמתעצבן שאתה לא קם.
        דבר ישירות אליו. אל תוסיף מרכאות. אל תוסיף כוכביות. פשוט המשפט שיגרום לו להזיז את התחת.
        """
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text.strip()
        except Exception:
            return "יאללה עמית, כמה אפשר לשבת? תזיז את עצמך."

    def _speak_aloud(self, text):
        try:
            print(f"\n[Jarvis Active Voice]: {text}")
            edge_tts_cmd = '/home/kido1/Smartroom/.venv/bin/edge-tts'
            subprocess.run([
                edge_tts_cmd, '--text', text, '--write-media', 'study_alert.mp3',
                '--voice', 'he-IL-AvriNeural', '--rate=+15%'
            ], check=True)
            subprocess.Popen(['mpv', 'study_alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            pass

    def _flush_old_messages(self):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, timeout=5).json()
            if response.get("ok") and response.get("result"):
                self.last_update_id = response["result"][-1]["update_id"]
        except Exception:
            pass

    def start_study(self):
        self.state = "STUDYING"
        self.end_time = time.time() + (50 * 60)
        self.extra_break_time = 0
        msg = "סשן למידה התחיל. חמישים דקות על השעון. בהצלחה!"
        self.send_phone_notification("🚀 " + msg)
        self._speak_aloud(msg)
        self._start_monitor_thread()
        return "מצב למידה הופעל."

    def pause_study(self):
        if self.state in ["STUDYING", "ON_BREAK", "WAITING_FOR_BREAK"]:
            self.remaining_paused_time = self.end_time - time.time()
            self.previous_state = self.state
            self.state = "PAUSED"
            self.send_phone_notification("⏸️ הזמן הוקפא.")
            self._speak_aloud("הטיימר הוקפא.")
            return "הטיימר הושהה."
        return "אין טיימר פעיל כרגע."

    def resume_study(self):
        if self.state == "PAUSED":
            self.state = self.previous_state
            self.end_time = time.time() + self.remaining_paused_time
            mode_name = "ללמוד" if self.state == "STUDYING" else "להפסקה"
            self.send_phone_notification(f"▶️ חזרנו לעניינים! הטיימר ממשיך.")
            self._speak_aloud(f"ממשיכים. חזרנו {mode_name}.")
            self._start_monitor_thread()
            return "הטיימר ממשיך."
        elif self.state == "IDLE":
            return self.start_study() 
        return "הטיימר כבר רץ."

    def stop_study(self):
        self.state = "IDLE"
        self.end_time = 0
        self.send_phone_notification("🛑 סשן הלמידה בוטל.")
        self._speak_aloud("ביטלתי את הטיימרים. חזרנו לשגרה.")
        return "מצב למידה נעצר לחלוטין."

    def start_break(self):
        self.state = "ON_BREAK"
        total_break = 10 + self.extra_break_time
        self.end_time = time.time() + (total_break * 60)
        
        msg = f"הפסקה של {total_break} דקות התחילה. קום להתרענן!"
        if self.extra_break_time > 0:
            msg = f"קיבלת שתי דקות בונוס! " + msg
            
        self.extra_break_time = 0 
        self.send_phone_notification("☕ " + msg)
        self._speak_aloud(msg)
        self._start_monitor_thread()
        return f"הפסקה של {total_break} דקות החלה."

    def add_time(self, minutes):
        if self.state == "NAGGING_TO_BREAK":
            self.state = "WAITING_FOR_BREAK"
            self.end_time = time.time() + (minutes * 60)
            self._start_monitor_thread()
        elif self.state == "NAGGING_TO_STUDY":
            self.state = "ON_BREAK"
            self.end_time = time.time() + (minutes * 60)
            self._start_monitor_thread()
        elif self.state in ["STUDYING", "ON_BREAK", "WAITING_FOR_BREAK"]:
            self.end_time += (minutes * 60)
        elif self.state == "PAUSED":
            self.remaining_paused_time += (minutes * 60)
        else:
            return "אין טיימר פעיל לשנות לו את הזמן."

        word = "הוספתי" if minutes > 0 else "הורדתי"
        self.send_phone_notification(f"⏳ {word} לך {abs(minutes)} דקות לטיימר.")
        return f"{word} {abs(minutes)} דקות."

    def get_time_left(self):
        if self.state == "IDLE":
            return "אין טיימר פעיל כרגע."
        elif self.state == "PAUSED":
            mins = int(self.remaining_paused_time // 60)
            return f"הטיימר מושהה. נשארו {mins} דקות כשנחזור."
        elif self.state == "NAGGING_TO_BREAK":
            return "זמן הלמידה נגמר, אתה אמור להיות על הרגליים!"
        elif self.state == "NAGGING_TO_STUDY":
            return "ההפסקה נגמרה, תלמד כבר!"
        
        rem_time = self.end_time - time.time()
        
        if rem_time <= 0:
            return "הזמן עבר, עובר למצב נדנוד."
            
        mins = int(rem_time // 60)
        secs = int(rem_time % 60)
        time_str = f"{mins} דקות" if mins > 0 else f"{secs} שניות"
        
        if self.state in ["STUDYING", "WAITING_FOR_BREAK"]:
            return f"נשארו לך עוד {time_str} ללמוד."
        elif self.state == "ON_BREAK":
            return f"נשארו לך עוד {time_str} להפסקה."

    def _start_monitor_thread(self):
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _monitor_loop(self):
        while self.state in ["STUDYING", "WAITING_FOR_BREAK", "ON_BREAK"]:
            time.sleep(1)
            if time.time() >= self.end_time:
                self._trigger_action()
                break

    def _trigger_action(self):
        if self.state in ["STUDYING", "WAITING_FOR_BREAK"]:
            self.state = "NAGGING_TO_BREAK"
            msg = "עמית, הזמן נגמר! הגיע הזמן לקום."
            self.send_phone_notification("🚨 " + msg)
            self._speak_aloud(msg)
            threading.Thread(target=self._nag_to_break_loop, daemon=True).start()
            
        elif self.state == "ON_BREAK":
            self.state = "NAGGING_TO_STUDY"
            msg = "נגמרה ההפסקה! קדימה לחזור."
            self.send_phone_notification("🔔 " + msg)
            self._speak_aloud(msg)
            threading.Thread(target=self._nag_to_study_loop, daemon=True).start()

    def _nag_to_break_loop(self):
        delays = [60, 30, 15] 
        stage = 1
        
        while self.state == "NAGGING_TO_BREAK":
            current_delay = delays[stage-1] if stage <= len(delays) else 10
            
            for _ in range(current_delay):
                if self.state != "NAGGING_TO_BREAK":
                    return
                time.sleep(1)
            
            if stage == 3:
                self.extra_break_time = 2 
            
            msg = self._generate_nag_message(stage, "הוא יושב כבר יותר מדי זמן ולא קם להפסקה.")
            self.send_phone_notification("🚨 " + msg)
            self._speak_aloud(msg)
            
            stage += 1

    def _nag_to_study_loop(self):
        delays = [60, 30, 15]
        stage = 1
        
        while self.state == "NAGGING_TO_STUDY":
            current_delay = delays[stage-1] if stage <= len(delays) else 10
            
            for _ in range(current_delay):
                if self.state != "NAGGING_TO_STUDY":
                    return
                time.sleep(1)
            
            msg = self._generate_nag_message(stage, "ההפסקה שלו נגמרה והוא צריך לחזור ללמוד עכשיו.")
            self.send_phone_notification("🔔 " + msg)
            self._speak_aloud(msg)
            
            stage += 1

    def send_phone_notification(self, message):
        if not self.bot_token or not self.chat_id: return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        keyboard = {
            "keyboard": [
                [{"text": "🏃‍♂️ יצאתי להפסקה"}, {"text": "📚 חזרתי ללמוד"}],
                [{"text": "⏱️ סטטוס זמן"}, {"text": "🛑 סיום סשן"}]
            ],
            "resize_keyboard": True
        }
        
        payload = {"chat_id": self.chat_id, "text": message, "reply_markup": keyboard}
        try:
            requests.post(url, json=payload)
        except Exception:
            pass

    def _telegram_listener_loop(self):
        while True:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
                response = requests.get(url, timeout=15).json()
                
                if response.get("ok") and response.get("result"):
                    for update in response["result"]:
                        self.last_update_id = update["update_id"]
                        
                        if "message" in update and "text" in update["message"]:
                            text = update["message"]["text"]
                            sender_id = str(update["message"]["chat"]["id"])
                            
                            if sender_id == self.chat_id:
                                if any(word in text for word in ["קמתי", "יצאתי", "הפסקה"]):
                                    self.start_break()
                                elif any(word in text for word in ["חזרתי", "פה", "ללמוד", "שולחן"]):
                                    self.start_study()
                                elif "השהה" in text:
                                    self.pause_study()
                                elif "המשך" in text:
                                    self.resume_study()
                                elif "סיום" in text:
                                    self.stop_study()
                                elif "זמן" in text:
                                    self.send_phone_notification(self.get_time_left())
            except Exception:
                pass 
            time.sleep(1)