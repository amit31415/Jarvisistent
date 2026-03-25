import time
import threading

class StudyManager:
    def __init__(self):
        self.state = "IDLE"  # מצבים: IDLE, STUDYING, WAITING_FOR_BREAK, ON_BREAK
        self.end_time = 0
        self.nag_thread = None

    def process_command(self, command):
        """הפונקציה שמקבלת את הטקסט שג'ארוויס שמע מהמיקרופון"""
        if "כנס למצב למידה" in command:
            self.start_study()
            return "נכנסנו למצב למידה. יש לך 50 דקות, בהצלחה הבוס."

        elif "חכה רגע" in command or "אני באמצע" in command:
            if self.state == "WAITING_FOR_BREAK" or self.state == "STUDYING":
                self.add_time(5)
                return "הוספתי חמש דקות. תגיד לי כשתצא להפסקה."

        elif "יצאתי להפסקה" in command or "אני בהפסקה" in command:
            self.start_break()
            return "עשר דקות הפסקה התחילו מעכשיו. קום להתרענן."

        elif "חזרתי" in command:
            if self.state in ["ON_BREAK", "NAGGING"]:
                self.start_study()
                return "שמח שחזרת. מאפס את הטיימר ל-50 דקות. צא לדרך."
        
        return None # לא פקודת למידה

    def start_study(self):
        self.state = "STUDYING"
        self.end_time = time.time() + (50 * 60) # 50 דקות מהעכשיו
        self._start_monitor_thread()

    def add_time(self, minutes):
        self.state = "WAITING_FOR_BREAK"
        self.end_time = time.time() + (minutes * 60)
        self._start_monitor_thread()

    def start_break(self):
        self.state = "ON_BREAK"
        self.end_time = time.time() + (10 * 60) # 10 דקות
        self._start_monitor_thread()

    def _start_monitor_thread(self):
        # מפעיל תהליך ברקע שבודק את השעון כדי לא לתקוע את התוכנית הראשית
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _monitor_loop(self):
        while self.state in ["STUDYING", "WAITING_FOR_BREAK", "ON_BREAK"]:
            time.sleep(1) # בודק כל שנייה
            if time.time() >= self.end_time:
                self._trigger_action()
                break

    def _trigger_action(self):
        if self.state == "STUDYING":
            self.state = "WAITING_FOR_BREAK"
            print("\n[ג'ארוויס ברמקול]: הבוס, עברו 50 דקות. קום לעשות סיבוב!")
            # פה תכניס את הפונקציה שמשמיעה סאונד בחדר
            
        elif self.state == "WAITING_FOR_BREAK":
            print("\n[ג'ארוויס ברמקול]: תזכורת! אתה חייב לקום מהכיסא.")
            # אם הוא אמר חכה רגע ועברו ה-5 דקות, ננדנד לו שוב בחדר
            
        elif self.state == "ON_BREAK":
            self.state = "NAGGING"
            self._nag_loop()

    def _nag_loop(self):
        """לולאת הנדנוד לטלפון כל דקה עד שתגיד 'חזרתי'"""
        print("\n[שולח הודעה ראשונה לטלפון]: נגמרה ההפסקה, תחזור למקום!")
        self.send_phone_notification("נגמרה ההפסקה! תחזור ללמוד.")
        
        while self.state == "NAGGING":
            time.sleep(60) # מחכה דקה
            if self.state == "NAGGING":
                print("\n[שולח הודעה נודנת לטלפון]: נו, חזרת??")
                self.send_phone_notification("נו, חזרת למקום? אני מחכה שתגיד 'חזרתי'.")

    import requests

def send_phone_notification(self, message):
    bot_token = "8584437543:AAH3ASvdpl1xFQXyH32zDfa_Omxy3t4g84o"
    chat_id = "5653235254" # תכף אסביר איך מוצאים אותו
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"שגיאה בשליחת הודעה לטלגרם: {e}")