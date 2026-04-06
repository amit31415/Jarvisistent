import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, 'config')
CREDS_FILE = os.path.join(CONFIG_DIR, 'credentials.json')

# We now use two separate token files!
UNI_TOKEN = os.path.join(CONFIG_DIR, 'uni_token.json')
PERSONAL_TOKEN = os.path.join(CONFIG_DIR, 'personal_token.json')
OAUTH_FILE = os.path.join(CONFIG_DIR, 'oauth.json')

# University: ONLY Gmail
SCOPES_UNI = [
    'https://www.googleapis.com/auth/gmail.readonly'
]

# Personal: Tasks, Drive, Calendar, YouTube
SCOPES_PERSONAL = [
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/youtube'
]

def authenticate_uni():
    print("\n--- [Step 1] University Account (GMAIL ONLY) ---")
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES_UNI)
    creds = flow.run_local_server(port=0, prompt='consent') 
    with open(UNI_TOKEN, 'w') as token:
        token.write(creds.to_json())
    print("\n[V] SUCCESS! uni_token.json created.\n")

def authenticate_personal():
    print("\n--- [Step 2] Personal Account (Tasks, Drive, Calendar, YT Music) ---")
    flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES_PERSONAL)
    creds = flow.run_local_server(port=0, prompt='consent')
    
    # Save standard token for personal stuff (Drive, Tasks, Calendar)
    with open(PERSONAL_TOKEN, 'w') as token:
        token.write(creds.to_json())
        
    # Save oauth.json specially for YT Music
    yt_oauth = {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expires_at": int(creds.expiry.timestamp()) if creds.expiry else 0,
        "expires_in": 3599,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret
    }
    with open(OAUTH_FILE, 'w') as yt_token:
        json.dump(yt_oauth, yt_token, indent=4)
        
    print("\n[V] SUCCESS! personal_token.json and oauth.json created.\n")

if __name__ == '__main__':
    print("=======================================")
    print("        JARVIS AUTH MANAGER            ")
    print("=======================================")
    print("1. University Account (Gmail only)")
    print("2. Personal Account (Tasks, Drive, Calendar, Music)")
    print("=======================================")
    choice = input("Choose 1 or 2: ")
    
    if choice == '1':
        authenticate_uni()
    elif choice == '2':
        authenticate_personal()
    else:
        print("Invalid choice. Exiting.")