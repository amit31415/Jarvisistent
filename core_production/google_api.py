import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

def authenticate_google():
    """טוען את תעודת ההרשאה (token) של ג'ארוויס"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # אם הטוקן פג תוקף אבל אפשר לחדש אותו אוטומטית (ברקע)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # שומרים את הטוקן המחודש
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
        else:
            print("[ERROR] token.json is missing or invalid. Please re-authenticate.")
            return None
    return creds



# --- שירותי גוגל ---
def get_gmail_service():
    creds = authenticate_google()
    return build('gmail', 'v1', credentials=creds)

# --- פעולות מבצעיות ---

def get_email_body(payload):
    """פונקציה חכמה שמקלפת את קידוד ה-Base64 ושולפת את הטקסט הנקי של המייל"""
    body = ""
    # אם המייל מחולק לכמה חלקים (טקסט, תמונות, HTML)
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    body += base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            elif 'parts' in part: # רקורסיה למקרה של חלקים בתוך חלקים
                body += get_email_body(part)
    # אם המייל הוא רק חתיכת טקסט אחת
    elif payload['mimeType'] == 'text/plain':
        data = payload['body'].get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    
    return body

def get_unread_emails(max_results=40):
    """שואב את המיילים מ-3 הימים האחרונים, כולל התוכן המלא שלהם"""
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

            # חילוץ התוכן המלא בעזרת הפונקציה החדשה שלנו
            full_body = get_email_body(payload)
            
            # אם משום מה לא הצלחנו למשוך טקסט נקי (למשל מייל שהוא רק תמונה מ-HTML), נשתמש בתקציר כגיבוי
            if not full_body.strip():
                full_body = message.get('snippet', '')
            
            # חותכים את התוכן ל-1000 תווים כדי לא להעמיס על ג'מיני במיילים ארוכים מדי
            if len(full_body) > 1000:
                full_body = full_body[:1000] + "\n... [הטקסט ארוך ונחתך]"

            # אורזים הכל לג'מיני
            email_data.append(f"מייל {index}:\nתאריך: {date_sent}\nמאת: {sender}\nנושא: {subject}\nתוכן המייל:\n{full_body.strip()}")

        return "\n\n====================\n\n".join(email_data)

    except Exception as e:
        return f"[ERROR] Failed to fetch emails: {e}"


def get_specific_email(search_term):
    """מחפש מיילים ספציפיים בג'ימייל ומחזיר את התוכן והתקציר שלהם"""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import os

        # טעינת ההרשאות מקובץ הטוקן
        token_path = os.path.join(os.path.dirname(__file__), 'token.json')
        if not os.path.exists(token_path):
            return "שגיאה: קובץ token.json חסר."
        
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/gmail.readonly'])        
        service = build('gmail', 'v1', credentials=creds)

        # מחפש בג'ימייל (מביא את 3 התוצאות הכי רלוונטיות)
        results = service.users().messages().list(userId='me', q=search_term, maxResults=3).execute()
        messages = results.get('messages', [])

        if not messages:
            return f"לא מצאתי מיילים שקשורים ל: {search_term}"

        output = ""
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), "ללא נושא")
            sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), "לא ידוע")
            snippet = msg_data.get('snippet', '')

            output += f"מאת: {sender}\nנושא: {subject}\nתקציר: {snippet}\n\n"

        return output

    except Exception as e:
        return f"שגיאה טכנית מול גוגל במהלך החיפוש: {str(e)}"

def get_upcoming_events():
    """מושך את האירועים הקרובים מהיומן של גוגל."""
    max_results = 5
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import os
        import datetime

        token_path = os.path.join(os.path.dirname(__file__), 'token.json')
        if not os.path.exists(token_path):
            return "שגיאה: קובץ token.json חסר."
        
        # טוען את הטוקן עם כל ההרשאות
        SCOPES = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/tasks',
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        service = build('calendar', 'v3', credentials=creds)

        # לוקח את הזמן הנוכחי כדי להביא רק אירועים מעכשיו והלאה
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              maxResults=max_results, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            return "אין אירועים קרובים ביומן."

        output = "אירועים קרובים ביומן:\n"
        for event in events:
            # מנסה לקחת שעת התחלה (או תאריך אם זה אירוע של יום שלם)
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'ללא כותרת')
            output += f"- {summary} (מתחיל ב: {start})\n"

        return output

    except Exception as e:
        return f"שגיאה טכנית מול גוגל קלנדר: {str(e)}"

# טסט מקומי לבדיקת המערכת
if __name__ == '__main__':
    print("[INFO] Testing Jarvis Gmail Connection...")
    print("-" * 30)
    unread_emails = get_unread_emails(max_results=15)
    print(unread_emails)
    print("-" * 30)