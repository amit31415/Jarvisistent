import os.path
import base64
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# נתיבים מפוצלים לפי הארכיטקטורה החדשה
BASE_DIR = '/home/kido1/Smartroom/config'
UNI_TOKEN = os.path.join(BASE_DIR, 'uni_token.json')
PERSONAL_TOKEN = os.path.join(BASE_DIR, 'personal_token.json')

def load_credentials(token_path):
    """טוען או מרענן את הטוקן לפי הנתיב המבוקש"""
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path)
    
    # חידוש אוטומטי של הטוקן אם פג תוקף
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        else:
            print(f"[ERROR] Token missing or invalid at: {token_path}")
            return None
    return creds


# --- שירותי גוגל מסווגים לפי חשבונות ---

def get_gmail_service():
    """מושך את שירות המייל מהחשבון האוניברסיטאי"""
    creds = load_credentials(UNI_TOKEN)
    if not creds:
        raise Exception("חסר אימות לחשבון האוניברסיטה (uni_token.json)")
    return build('gmail', 'v1', credentials=creds)

def get_calendar_service():
    """מושך את שירות היומן מהחשבון הפרטי"""
    creds = load_credentials(PERSONAL_TOKEN)
    if not creds:
        raise Exception("חסר אימות לחשבון הפרטי (personal_token.json)")
    return build('calendar', 'v3', credentials=creds)

def get_tasks_service():
    """מושך את שירות המשימות (Tasks) מהחשבון הפרטי"""
    creds = load_credentials(PERSONAL_TOKEN)
    if not creds:
        raise Exception("חסר אימות לחשבון הפרטי (personal_token.json)")
    return build('tasks', 'v1', credentials=creds)


# --- פעולות מבצעיות (הקוד המקורי שלך) ---

def get_email_body(payload):
    """פונקציה חכמה שמקלפת את קידוד ה-Base64 ושולפת את הטקסט הנקי של המייל"""
    body = ""
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    body += base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            elif 'parts' in part: 
                body += get_email_body(part)
    elif payload['mimeType'] == 'text/plain':
        data = payload['body'].get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    
    return body

def get_unread_emails(max_results=40):
    """שואב את המיילים מ-3 הימים האחרונים מהאוניברסיטה"""
    try:
        service = get_gmail_service()
        query = "is:unread newer_than:3d"
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            return "אין לך הודעות חדשות מ-3 הימים האחרונים, אדוני."

        email_data = []
        for index, msg in enumerate(messages, 1):
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message.get('payload', {})
            headers = payload.get('headers', [])

            subject = "ללא נושא"
            sender = "לא ידוע"
            date_sent = "לא ידוע"

            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                if header['name'] == 'From':
                    sender = header['value'].split('<')[0].strip()
                if header['name'] == 'Date':
                    date_sent = header['value']

            full_body = get_email_body(payload)
            
            if not full_body.strip():
                full_body = message.get('snippet', '')
            
            if len(full_body) > 1000:
                full_body = full_body[:1000] + "\n... [הטקסט ארוך ונחתך]"

            email_data.append(f"מייל {index}:\nתאריך: {date_sent}\nמאת: {sender}\nנושא: {subject}\nתוכן המייל:\n{full_body.strip()}")

        return "\n\n====================\n\n".join(email_data)

    except Exception as e:
        return f"[ERROR] Failed to fetch emails: {e}"

def get_specific_email(search_term, max_results=3):
    """מחפש מיילים ספציפיים בג'ימייל ומחזיר את התוכן המלא שלהם"""
    try:
        service = get_gmail_service()
        query = f"{search_term} newer_than:14d"
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"לא מצאתי מיילים התואמים לחיפוש '{search_term}' בשבועיים האחרונים."

        email_data = []
        for index, msg in enumerate(messages, 1):
            msg_id = msg['id']
            message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            payload = message.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = "ללא נושא"
            sender = "לא ידוע"
            date_sent = "לא ידוע"

            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                if header['name'] == 'From':
                    sender = header['value'].split('<')[0].strip()
                if header['name'] == 'Date':
                    date_sent = header['value']

            full_body = get_email_body(payload)
            if not full_body.strip():
                full_body = message.get('snippet', '')

            email_data.append(f"מייל {index}:\nתאריך: {date_sent}\nמאת: {sender}\nנושא: {subject}\nתוכן מלא:\n{full_body.strip()}")

        return "\n\n====================\n\n".join(email_data)

    except Exception as e:
        return f"[ERROR] Failed to fetch specific email: {e}"

def get_upcoming_events():
    """מושך את האירועים הקרובים מהיומן האישי של גוגל."""
    max_results = 5
    try:
        service = get_calendar_service()

        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=max_results, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            return "אין אירועים קרובים ביומן."

        output = "אירועים קרובים ביומן:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'ללא כותרת')
            output += f"- {summary} (מתחיל ב: {start})\n"

        return output

    except Exception as e:
        return f"שגיאה טכנית מול גוגל קלנדר: {str(e)}"

def get_open_tasks():
    """מושך את כל המשימות הפתוחות מ-Google Tasks"""
    try:
        service = get_tasks_service()
        # מביא את כל רשימות המשימות שלך
        results = service.tasklists().list(maxResults=10).execute()
        task_lists = results.get('items', [])

        if not task_lists:
            return "אין לך רשימות משימות בגוגל."

        output = "המשימות הפתוחות שלך:\n"
        found_tasks = False

        for t_list in task_lists:
            list_name = t_list['title']
            # מביא רק משימות שלא הושלמו
            tasks_result = service.tasks().list(tasklist=t_list['id'], showCompleted=False).execute()
            tasks = tasks_result.get('items', [])
            
            if tasks:
                found_tasks = True
                output += f"\n--- רשימה: {list_name} ---\n"
                for task in tasks:
                    output += f"• {task['title']}\n"
        
        if not found_tasks:
            return "אין לך משימות פתוחות כרגע. הכל נקי!"
            
        return output
    except Exception as e:
        return f"[ERROR] Failed to fetch tasks: {e}"

# טסט מקומי לבדיקת המערכת
if __name__ == '__main__':
    print("[INFO] Testing Jarvis Google Connections...")
    print("-" * 30)
    print("Testing Emails (University)...")
    unread_emails = get_unread_emails(max_results=3)
    print(unread_emails[:500] + "...\n")
    
    print("-" * 30)
    print("Testing Calendar (Personal)...")
    upcoming_events = get_upcoming_events()
    print(upcoming_events)
    print("-" * 30)