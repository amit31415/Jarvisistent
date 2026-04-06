import os
import requests
from dotenv import load_dotenv

print("\n--- מתחיל בדיקת תקשורת טלגרם ---")

# 1. טעינת הסודות
env_path = '/home/kido1/Smartroom/.env'
load_dotenv(env_path, override=True)

bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_BOT_ID")

print(f"[*] בודק קובץ .env...")
if not bot_token or not chat_id:
    print("[X] שגיאה קריטית: חסר טוקן או צ'אט ID בקובץ ה-.env שלך!")
    exit(1)

print(f"[V] מפתחות נמצאו (Chat ID: {chat_id})")

# 2. בדיקת זהות הבוט מול שרתי טלגרם
print("\n[*] בודק חיבור לשרתי טלגרם (מזהה בוט)...")
try:
    res = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10).json()
    if res.get("ok"):
        print(f"[V] התחברות לבוט הצליחה! שם הבוט: {res['result']['first_name']}")
    else:
        print(f"[X] הבוט לא זוהה! שגיאה מטלגרם: {res.get('description')}")
        print("    -> המשמעות: ה-TELEGRAM_BOT_TOKEN שלך שגוי או פג תוקף.")
        exit(1)
except Exception as e:
    print(f"[X] בעיית רשת כללית בגישה לאינטרנט/טלגרם: {e}")
    exit(1)

# 3. ניסיון שליחת הודעה אליך
print("\n[*] מנסה לשלוח אליך הודעת בדיקה...")
try:
    payload = {"chat_id": chat_id, "text": "🤖 בדיקת מערכות: ג'ארוויס מחובר ומשדר אליך בהצלחה!"}
    res = requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload, timeout=10).json()
    
    if res.get("ok"):
        print("[V] הצלחה מוחלטת! הודעה נשלחה. בדוק את הטלגרם שלך עכשיו.")
    else:
        print(f"[X] שגיאה בשליחת ההודעה אליך: {res.get('description')}")
        print("    -> המשמעות: ה-TELEGRAM_BOT_ID שגוי, או שמעולם לא שלחת הודעת /start לבוט הזה.")
except Exception as e:
    print(f"[X] שגיאה טכנית בשליחה: {e}")
