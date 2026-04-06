import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# הנתיבים
CONFIG_DIR = '/home/kido1/Smartroom/config'
CREDS_FILE = os.path.join(CONFIG_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(CONFIG_DIR, 'token.json')
OAUTH_FILE = os.path.join(CONFIG_DIR, 'oauth.json')

# פיצול הרשאות
SCOPES_UNI = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

SCOPES_MUSIC = [
    'https://www.googleapis.com/auth/youtube'
]

print("\n==================================================")
print("   [1] חתימה על חשבון אוניברסיטה (מייל, יומן, דרייב)")
print("==================================================")
input("לחץ Enter כדי לפתוח דפדפן. **בחר את חשבון האוניברסיטה שלך!**")

try:
    flow_uni = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES_UNI)
    creds_uni = flow_uni.run_local_server(port=0)
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds_uni.to_json())
    print("[V] token.json נשמר בהצלחה לחשבון האקדמי.\n")

    print("==================================================")
    print("   [2] חתימה על חשבון פרטי (YouTube Music)")
    print("==================================================")
    input("לחץ Enter לפתיחת דפדפן. **בחר את החשבון האישי שלך!** (אם הוא מתחבר אוטומטית, בחר 'החלף חשבון')")
    
    flow_music = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES_MUSIC)
    creds_music = flow_music.run_local_server(port=0)

    # המרה לפורמט ש-YTMusic אוהב
    yt_oauth = {
        "access_token": creds_music.token,
        "refresh_token": creds_music.refresh_token,
        "expires_at": int(creds_music.expiry.timestamp()) if creds_music.expiry else 0,
        "expires_in": 3599,
        "client_id": creds_music.client_id,
        "client_secret": creds_music.client_secret
    }
    
    with open(OAUTH_FILE, 'w') as yt_token:
        json.dump(yt_oauth, yt_token, indent=4)
    print("[V] oauth.json נשמר בהצלחה לחשבון הפרטי.\n")

    print("[SUCCESS] ג'ארוויס מחובר בהצלחה לשני העולמות שלך!")

except Exception as e:
    print(f"\n[ERROR] Authentication failed: {e}")