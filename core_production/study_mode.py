import time
import threading
import requests
import os
import subprocess
import json
import datetime
from dotenv import load_dotenv
from google import genai

load_dotenv() 

STATS_FILE = '/home/kido1/Smartroom/study_stats.json'

# ==========================================
# קופסה שחורה - מעקב וסטטיסטיקות למידה
# ==========================================
class StudyTracker:
    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.end_time = None
        
        self.pause_count = 0
        self.extra_study_minutes = 0
        self.extra_break_minutes = 0
        self.study_cycles = 0
        
        self.timeline = []
        self.current_phase = None
        self.phase_start = None

    def start_phase(self, phase_name):
        self._close_current_phase()
        self.current_phase = phase_name
        self.phase_start = datetime.datetime.now()
        if phase_name == "study":
            self.study_cycles += 1

    def _close_current_phase(self):
        if self.current_phase and self.phase_start:
            now = datetime.datetime.now()
            duration_sec = (now - self.phase_start).total_seconds()
            duration_min = round(duration_sec / 60, 2)
            self.timeline.append({
                "phase": self.current_phase,
                "duration_minutes": duration_min
            })
            
    def add_extra_time(self, phase, minutes):
        if phase == "study":
            self.extra_study_minutes += minutes
        elif phase == "break":
            self.extra_break_minutes += minutes

    def add_pause(self):
        self.pause_count += 1
        self.start_phase("pause")

    def end_session(self):
        self._close_current_phase()
        self.end_time = datetime.datetime.now()
        total_elapsed = (self.end_time - self.start_time).total_seconds() / 60
        total_study = sum(item['duration_minutes'] for item in self.timeline if item['phase'] == 'study')
        total_break = sum(item['duration_minutes'] for item in self.timeline if item['phase'] == 'break')
        
        session_data = {
            "session_date": self.start_time.strftime("%Y-%m-%d"),
            "start_time": self.start_time.strftime("%H:%M:%S"),
            "end_time": self.end_time.strftime("%H:%M:%S"),
            "total_session_minutes": round(total_elapsed, 2),
            "total_study_minutes": round(total_study, 2),
            "total_break_minutes": round(total_break, 2),
            "study_cycles": self.study_cycles,
            "pause_count": self.pause_count,
            "extra_study_added": self.extra_study_minutes,
            "extra_break_added": self.extra_break_minutes,
            "timeline": self.timeline
        }
        self._save_to_json(session_data)
        return session_data

    def _save_to_json(self, data):
        all_sessions = []
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r', encoding='utf-8') as f:
                    all_sessions = json.load(f)
            except json.JSONDecodeError:
                pass
        all_sessions.append(data)
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_sessions, f, indent=4, ensure_ascii=False)


# ==========================================
# מנהל הלמידה הראשי (כולל טלגרם וג'ארוויס)
# ==========================================
class StudyManager:
    def __init__(self):
        self.state = "IDLE"  
        self.end_time = 0
        self.remaining_paused_time = 0 
        self.previous_state = "IDLE"   
        self.last_update_id = 0 
        self.extra_break_time = 0
        self.tracker = None # שילוב האנליטיקה

        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_BOT_ID")
        self.gemini_key = os.getenv("GEMINI_KEY")

        self.gemini_client = genai.Client(api_key=self.gemini_key) if self.gemini_key else None

        if self.bot_token and self.chat_id:
            self._flush_old_messages() 
            self.send_phone_notification("ג'ארוויס מערכת למידה מוכנה. מחכה לפקודה.")
            threading.Thread(target=self._telegram_listener_loop, daemon=True).start()

    def is_nagging(self):
        return self.state in ["NAGGING_TO_BREAK", "NAGGING_TO_STUDY"]

    # ------------------ TELEGRAM UI ------------------
    def _get_dynamic_keyboard(self):
        """מייצר כפתורים לטלגרם בהתאם לסטטוס הנוכחי"""
        if self.state == "IDLE":
            return {"keyboard": [[{"text": "🚀 התחל סשן למידה"}]], "resize_keyboard": True}
        
        elif self.state in ["STUDYING", "WAITING_FOR_BREAK", "NAGGING_TO_BREAK"]:
            return {"keyboard": [
                [{"text": "⏸️ השהה למידה"}, {"text": "☕ יצאתי להפסקה"}],
                [{"text": "⏱️ סטטוס זמן"}, {"text": "🛑 סיום סשן"}]
            ], "resize_keyboard": True}
            
        elif self.state in ["ON_BREAK", "NAGGING_TO_STUDY"]:
            return {"keyboard": [
                [{"text": "⏸️ השהה הפסקה"}, {"text": "📚 חזרתי ללמוד"}],
                [{"text": "⏱️ סטטוס זמן"}, {"text": "🛑 סיום סשן"}]
            ], "resize_keyboard": True}
            
        elif self.state == "PAUSED":
            return {"keyboard": [
                [{"text": "▶️ המשך טיימר"}],
                [{"text": "⏱️ סטטוס זמן"}, {"text": "🛑 סיום סשן"}]
            ], "resize_keyboard": True}
            
        return {"remove_keyboard": True}

    def send_phone_notification(self, message):
        if not self.bot_token or not self.chat_id: return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id, 
            "text": message, 
            "reply_markup": self._get_dynamic_keyboard()
        }
        try:
            requests.post(url, json=payload)
        except Exception:
            pass

    # ------------------ CORE LOGIC ------------------
    def start_study(self):
        if self.state == "IDLE":
            self.tracker = StudyTracker() # מתחיל סשן חדש רק אם היינו ב-IDLE
            
        if self.tracker:
            self.tracker.start_phase("study")
            
        self.state = "STUDYING"
        self.end_time = time.time() + (50 * 60)
        self.extra_break_time = 0
        
        msg = "סשן למידה פעיל. 50 דקות על השעון."
        self.send_phone_notification("🚀 " + msg)
        self._speak_aloud(msg)
        self._start_monitor_thread()
        return "מצב למידה הופעל."

    def start_break(self):
        if self.tracker:
            self.tracker.start_phase("break")
            
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
        return msg

    def pause_study(self):
        if self.state in ["STUDYING", "ON_BREAK", "WAITING_FOR_BREAK"]:
            if self.tracker:
                self.tracker.add_pause()
                
            self.remaining_paused_time = self.end_time - time.time()
            self.previous_state = self.state
            self.state = "PAUSED"
            self.send_phone_notification("⏸️ הטיימר הוקפא.")
            self._speak_aloud("הטיימר הוקפא.")
            return "הטיימר הושהה."
        return "אין טיימר פעיל כרגע."

    def resume_study(self):
        if self.state == "PAUSED":
            self.state = self.previous_state
            self.end_time = time.time() + self.remaining_paused_time
            
            mode_name = "ללמוד" if self.state == "STUDYING" else "להפסקה"
            phase_name = "study" if self.state == "STUDYING" else "break"
            
            if self.tracker:
                self.tracker.start_phase(phase_name)
                
            self.send_phone_notification(f"▶️ ממשיכים! חזרנו {mode_name}.")
            self._speak_aloud(f"ממשיכים. חזרנו {mode_name}.")
            self._start_monitor_thread()
            return "הטיימר ממשיך."
        elif self.state == "IDLE":
            return self.start_study() 
        return "הטיימר כבר רץ."

    def stop_study(self):
        if self.state == "IDLE": return "לא רץ שום סשן."
        
        # סגירת המעקב ושליחת דוח
        stats_msg = "🛑 סשן הלמידה בוטל.\n"
        if self.tracker:
            data = self.tracker.end_session()
            stats_msg += f"\n📊 **סיכום סשן:**\n"
            stats_msg += f"📚 סך הכל למידה נטו: {data['total_study_minutes']} דקות\n"
            stats_msg += f"☕ סך הכל הפסקות: {data['total_break_minutes']} דקות\n"
            stats_msg += f"🔄 מחזורי למידה הושלמו: {data['study_cycles']}"
            self.tracker = None
            
        self.state = "IDLE"
        self.end_time = 0
        self.send_phone_notification(stats_msg)
        self._speak_aloud("סיימנו להיום. סיכום הסשן נשלח אליך לטלגרם.")
        return "מצב למידה נעצר לחלוטין."

    def add_time(self, minutes):
        if self.state == "NAGGING_TO_BREAK":
            self.state = "WAITING_FOR_BREAK"
            self.end_time = time.time() + (minutes * 60)
            self._start_monitor_thread()
            if self.tracker: self.tracker.add_extra_time("study", minutes)
            
        elif self.state == "NAGGING_TO_STUDY":
            self.state = "ON_BREAK"
            self.end_time = time.time() + (minutes * 60)
            self._start_monitor_thread()
            if self.tracker: self.tracker.add_extra_time("break", minutes)
            
        elif self.state in ["STUDYING", "WAITING_FOR_BREAK"]:
            self.end_time += (minutes * 60)
            if self.tracker: self.tracker.add_extra_time("study", minutes)
            
        elif self.state == "ON_BREAK":
            self.end_time += (minutes * 60)
            if self.tracker: self.tracker.add_extra_time("break", minutes)
            
        elif self.state == "PAUSED":
            self.remaining_paused_time += (minutes * 60)
            
        else:
            return "אין טיימר פעיל לשנות לו את הזמן."

        word = "הוספתי" if minutes > 0 else "הורדתי"
        self.send_phone_notification(f"⏳ {word} לך {abs(minutes)} דקות לטיימר.")
        return f"{word} {abs(minutes)} דקות."

    def get_time_left(self):
        if self.state == "IDLE": return "אין טיימר פעיל כרגע."
        if self.state == "PAUSED":
            mins = int(self.remaining_paused_time // 60)
            return f"הטיימר מושהה. נשארו {mins} דקות כשנחזור."
        if self.state == "NAGGING_TO_BREAK": return "זמן הלמידה נגמר, אתה אמור להיות על הרגליים!"
        if self.state == "NAGGING_TO_STUDY": return "ההפסקה נגמרה, תלמד כבר!"
        
        rem_time = self.end_time - time.time()
        if rem_time <= 0: return "הזמן עבר, עובר למצב נדנוד."
            
        mins, secs = int(rem_time // 60), int(rem_time % 60)
        time_str = f"{mins} דקות" if mins > 0 else f"{secs} שניות"
        
        if self.state in ["STUDYING", "WAITING_FOR_BREAK"]: return f"נשארו לך עוד {time_str} ללמוד."
        elif self.state == "ON_BREAK": return f"נשארו לך עוד {time_str} להפסקה."

    # ------------------ BACKGROUND LOOPS & ALERTS ------------------
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
                if self.state != "NAGGING_TO_BREAK": return
                time.sleep(1)
            
            if stage == 3: self.extra_break_time = 2 
            
            msg = self._generate_nag_message(stage, "יושב יותר מדי זמן ולא קם להפסקה.")
            self.send_phone_notification("🚨 " + msg)
            self._speak_aloud(msg)
            stage += 1

    def _nag_to_study_loop(self):
        delays = [60, 30, 15]
        stage = 1
        while self.state == "NAGGING_TO_STUDY":
            current_delay = delays[stage-1] if stage <= len(delays) else 10
            for _ in range(current_delay):
                if self.state != "NAGGING_TO_STUDY": return
                time.sleep(1)
            
            msg = self._generate_nag_message(stage, "ההפסקה נגמרה והוא צריך לחזור ללמוד.")
            self.send_phone_notification("🔔 " + msg)
            self._speak_aloud(msg)
            stage += 1

    def _generate_nag_message(self, stage, context):
        if not self.gemini_client: return "קום כבר."
        bribe = f"אישרתי לו עכשיו אקסטרה {self.extra_break_time} דקות בונוס." if self.extra_break_time > 0 else ""
        prompt = f"אתה ג'ארוויס. המצב: {context}. רמת נדנוד: {stage}/5. {bribe} תכתוב משפט חצוף אחד בעברית בלי מרכאות שיגרום לו להזיז את התחת."
        try:
            return self.gemini_client.models.generate_content(model='gemini-2.5-flash', contents=prompt).text.strip()
        except:
            return "יאללה עמית, כמה אפשר לשבת? תזיז את עצמך."

    def _speak_aloud(self, text):
        try:
            print(f"\n[Jarvis]: {text}")
            edge_tts_cmd = '/home/kido1/Smartroom/.venv/bin/edge-tts'
            subprocess.run([edge_tts_cmd, '--text', text, '--write-media', 'study_alert.mp3', '--voice', 'he-IL-AvriNeural', '--rate=+15%'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['mpv', 'study_alert.mp3', '--no-terminal'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass

    # ------------------ TELEGRAM POLLING ------------------
    def _flush_old_messages(self):
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
            res = requests.get(url, timeout=5).json()
            if res.get("ok") and res.get("result"):
                self.last_update_id = res["result"][-1]["update_id"]
        except: pass

    def _telegram_listener_loop(self):
        while True:
            try:
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates?offset={self.last_update_id + 1}&timeout=10"
                res = requests.get(url, timeout=15).json()
                if res.get("ok") and res.get("result"):
                    for update in res["result"]:
                        self.last_update_id = update["update_id"]
                        if "message" in update and "text" in update["message"]:
                            text = update["message"]["text"]
                            if str(update["message"]["chat"]["id"]) == self.chat_id:
                                # זיהוי פקודות מכפתורים וטקסט
                                if any(word in text for word in ["הפסקה", "יצאתי"]): self.start_break()
                                elif any(word in text for word in ["ללמוד", "חזרתי", "התחל"]): self.start_study()
                                elif "השהה" in text: self.pause_study()
                                elif "המשך" in text: self.resume_study()
                                elif "סיום" in text: self.stop_study()
                                elif "זמן" in text: self.send_phone_notification(self.get_time_left())
            except: pass 
            time.sleep(1)