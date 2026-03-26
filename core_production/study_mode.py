import time
import threading
import requests
import os
from dotenv import load_dotenv

load_dotenv() 

class StudyManager:
    def __init__(self):
        self.state = "IDLE"  # IDLE, STUDYING, WAITING_FOR_BREAK, ON_BREAK, NAGGING, PAUSED
        self.end_time = 0
        self.remaining_paused_time = 0 # שומר את הזמן שנותר כשאנחנו בפאוזה
        self.previous_state = "IDLE"   # זוכר מה עשינו לפני הפאוזה
        self.last_update_id = 0 

        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_BOT_ID")

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
        self.state = "STUDYING"
        self.end_time = time.time() + (50 * 60)
        self.send_phone_notification("🚀 סשן למידה התחיל! 50 דקות על השעון.")
        self._start_monitor_thread()
        return "מצב למידה הופעל לחמישים דקות."

    def pause_study(self):
        """מקפיא את הטיימר"""
        if self.state in ["STUDYING", "ON_BREAK", "WAITING_FOR_BREAK"]:
            self.remaining_paused_time = self.end_time - time.time()
            self.previous_state = self.state
            self.state = "PAUSED"
            self.send_phone_notification("⏸️ הזמן הוקפא. כשאתה מוכן לחזור, לחץ 'המשך'.")
            return "הטיימר הושהה."
        elif self.state == "PAUSED":
            return "הטיימר כבר מושהה."
        return "אין טיימר פעיל כרגע."

    def resume_study(self):
        """ממשיך את הטיימר מהנקודה שעצר"""
        if self.state == "PAUSED":
            self.state = self.previous_state
            self.end_time = time.time() + self.remaining_paused_time
            self.send_phone_notification("▶️ חזרנו לעניינים! הטיימר ממשיך מאיפה שעצרנו.")
            self._start_monitor_thread()
            return "הטיימר ממשיך מאיפה שעצרנו."
        elif self.state == "IDLE":
            return self.start_study() # אם הכל כבוי ולחץ המשך, פשוט נתחיל חדש
        return "הטיימר כבר רץ."

    def stop_study(self):
        """מבטל את הטיימר לחלוטין"""
        self.state = "IDLE"
        self.end_time = 0
        self.send_phone_notification("🛑 סשן הלמידה בוטל. אנחנו בסטנדביי.")
        return "מצב למידה נעצר לחלוטין. הטיימר בוטל."

    def start_break(self):
        self.state = "ON_BREAK"
        self.end_time = time.time() + (10 * 60)
        self.send_phone_notification("☕ הפסקה של 10 דקות התחילה. קום להתרענן!")
        self._start_monitor_thread()
        return "הפסקה של עשר דקות החלה."

    def get_time_left(self):
        if self.state == "IDLE":
            return "אין טיימר פעיל כרגע."
        elif self.state == "PAUSED":
            mins = int(self.remaining_paused_time / 60)
            return f"הטיימר מושהה. נשארו {mins} דקות כשנחזור."
        elif self.state == "NAGGING":
            return "ההפסקה נגמרה, אתה אמור להיות בחזרה בספרים."
        
        remaining_minutes = int((self.end_time - time.time()) / 60)
        if remaining_minutes <= 0:
            return "הזמן עומד להיגמר שניות אחרונות."
            
        if self.state == "STUDYING":
            return f"נשארו לך עוד {remaining_minutes} דקות ללמוד."
        elif self.state == "ON_BREAK":
            return f"נשארו לך עוד {remaining_minutes} דקות להפסקה."

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
        elif self.state == "ON_BREAK":
            self.state = "NAGGING"
            self._nag_loop()

    def _nag_loop(self):
        self.send_phone_notification("🔔 נגמרה ההפסקה! תלחץ על 'המשך' כדי להתחיל ללמוד שוב.")
        while self.state == "NAGGING":
            time.sleep(60)
            if self.state == "NAGGING":
                self.send_phone_notification("😡 נו, חזרת למקום?")

    def send_phone_notification(self, message):
        if not self.bot_token or not self.chat_id: return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        
        # ==========================================
        # הקסם החדש: מקלדת שליטה קבועה בטלגרם!
        # ==========================================
        keyboard = {
            "keyboard": [
                [{"text": "⏱️ סטטוס זמן"}, {"text": "🛑 סיום סשן"}],
                [{"text": "⏸️ השהה"}, {"text": "▶️ המשך / התחל"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }
        
        payload = {
            "chat_id": self.chat_id, 
            "text": message,
            "reply_markup": keyboard
        }
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
                                # עכשיו אנחנו בודקים בדיוק איזה כפתור נלחץ
                                if "השהה" in text:
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