import time
import threading
import requests
import os
from dotenv import load_dotenv

# מכריח את הקובץ הזה לקרוא את משתני הסביבה בעצמו
load_dotenv()

class StudyManager:
    def __init__(self):
        self.state = "IDLE"
        self.end_time = 0
        self.last_update_id = 0 

        # הנה התיקון - עכשיו זה מושך בדיוק את השמות שיש לך ב-.env
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_BOT_ID")

        print(f"\n[DEBUG TELEGRAM] Token loaded: {'YES' if self.bot_token else 'NO (Check .env)'}")
        print(f"[DEBUG TELEGRAM] Chat ID loaded: {'YES' if self.chat_id else 'NO (Check .env)'}")

        if self.bot_token and self.chat_id:
            self._flush_old_messages() 
            threading.Thread(target=self._telegram_listener_loop, daemon=True).start()
        else:
            print("[CRITICAL] Telegram disabled! Could not find keys in .env")

    def _flush_old_messages(self):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            response = requests.get(url, timeout=5).json()
            if response.get("ok") and response.get("result"):
                self.last_update_id = response["result"][-1]["update_id"]
        except Exception:
            pass

    def start_study(self):
        is_new_session = (self.state == "IDLE")
        self.state = "STUDYING"
        self.end_time = time.time() + (50 * 60)
        
        if is_new_session:
            self.send_phone_notification("🚀 סשן למידה חדש התחיל! 50 דקות על השעון. בהצלחה הבוס.")
        else:
            self.send_phone_notification("▶️ חזרנו ללמידה. הטיימר אופס ל-50 דקות.")
            
        self._start_monitor_thread()
        return "מצב למידה הופעל לחמישים דקות."

    def stop_study(self):
        if self.state == "IDLE":
            return "הטיימר כבר כבוי."
            
        self.state = "IDLE"
        self.end_time = 0
        self.send_phone_notification("🛑 סשן הלמידה נעצר לחלוטין. אנחנו בסטנדביי.")
        return "מצב למידה נעצר לחלוטין. הטיימר בוטל."

    def reset_study(self):
        self.state = "STUDYING"
        self.end_time = time.time() + (50 * 60)
        self.send_phone_notification("🔄 הטיימר אופס מחדש. מתחילים 50 דקות מהתחלה.")
        self._start_monitor_thread()
        return "הטיימר אופס. חזרנו לחמישים דקות מהתחלה."

    def add_time(self, minutes):
        self.state = "WAITING_FOR_BREAK"
        self.end_time = time.time() + (minutes * 60)
        self.send_phone_notification(f"⏳ הוספתי לך עוד {minutes} דקות לפי בקשתך.")
        self._start_monitor_thread()
        return f"הוספתי {minutes} דקות."

    def start_break(self):
        self.state = "ON_BREAK"
        self.end_time = time.time() + (10 * 60)
        self.send_phone_notification("☕ הפסקה של 10 דקות התחילה. קום להתרענן!")
        self._start_monitor_thread()
        return "הפסקה של עשר דקות החלה."

    def get_time_left(self):
        if self.state == "IDLE":
            return "אנחנו לא במצב למידה כרגע הבוס."
        elif self.state == "NAGGING":
            return "ההפסקה נגמרה, אתה אמור להיות בחזרה בספרים."
        
        remaining_minutes = int((self.end_time - time.time()) / 60)
        if remaining_minutes <= 0:
            return "הזמן ממש עומד להיגמר, שניות אחרונות."
            
        if self.state == "STUDYING":
            return f"נשארו לך עוד {remaining_minutes} דקות ללמוד."
        elif self.state == "ON_BREAK":
            return f"נשארו לך עוד {remaining_minutes} דקות להפסקה."
        elif self.state == "WAITING_FOR_BREAK":
            return f"נשארו לך עוד {remaining_minutes} דקות עד שאציק לך שוב."

    def _start_monitor_thread(self):
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _monitor_loop(self):
        while self.state in ["STUDYING", "WAITING_FOR_BREAK", "ON_BREAK"]:
            time.sleep(1)
            if time.time() >= self.end_time:
                self._trigger_action()
                break

    def _trigger_action(self):
        if self.state == "STUDYING":
            self.state = "WAITING_FOR_BREAK"
            print("\n[מערכת]: עברו 50 דקות!")
            self.send_phone_notification("🚨 עברו 50 דקות הבוס, קום לעשות סיבוב!")
            
        elif self.state == "WAITING_FOR_BREAK":
            self.send_phone_notification("⚠️ תזכורת! אתה חייב לקום מהכיסא עכשיו.")
            
        elif self.state == "ON_BREAK":
            self.state = "NAGGING"
            self._nag_loop()

    def _nag_loop(self):
        self.send_phone_notification("🔔 נגמרה ההפסקה! קדימה לחזור. תגיד או תכתוב לי שחזרת.")
        while self.state == "NAGGING":
            time.sleep(60)
            if self.state == "NAGGING":
                self.send_phone_notification("😡 נו, חזרת למקום? תגיד 'חזרתי'.")

    def send_phone_notification(self, message):
        if not self.bot_token or not self.chat_id: 
            print(f"[DEBUG] Failed to send message (Missing API Keys): {message}")
            return
            
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message}
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                print(f"[DEBUG] Telegram API Error: {response.text}")
        except Exception as e:
            print(f"[DEBUG] Request Exception: {e}")

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
                                # מפענח פקודות בסיסיות מטלגרם
                                if any(word in text for word in ["עצור", "בטל", "תפסיק", "סיים", "צא"]):
                                    self.stop_study()
                                elif any(word in text for word in ["ריסט", "מחדש", "אפס"]):
                                    self.reset_study()
                                elif any(word in text for word in ["הפסקה", "יצאתי"]):
                                    self.start_break()
                                elif any(word in text for word in ["חזרתי", "פה", "מתחיל"]):
                                    self.start_study()
                                elif any(word in text for word in ["זמן", "נשאר", "מצב", "סטטוס", "כמה"]):
                                    self.send_phone_notification(self.get_time_left())
            except Exception:
                pass 
            
            time.sleep(2)