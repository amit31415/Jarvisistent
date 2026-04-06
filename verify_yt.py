import json
import urllib.request
import urllib.error

auth_path = '/home/kido1/Smartroom/config/oauth.json'

print("\n--- מתחיל בדיקת אמת מול שרתי גוגל ---")
try:
    with open(auth_path, 'r') as f:
        data = json.load(f)

    # מחפש את הטוקן לא משנה איפה הוא מוחבא
    token = data.get('access_token') or data.get('oauth_credentials', {}).get('access_token')

    if not token:
        print("[X] כישלון: לא מצאתי access_token בתוך הקובץ. הקובץ כנראה פגום או ריק.")
        exit(1)

    print(f"[*] נמצא טוקן גישה. בודק זהות מול YouTube API...")
    
    req = urllib.request.Request(
        'https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
    )
    
    response = urllib.request.urlopen(req)
    res_data = json.loads(response.read().decode())
    
    if res_data.get('items'):
        channel_name = res_data['items'][0]['snippet']['title']
        print(f"\n[V] הצלחה מוחלטת! גוגל מאשרת את הטוקן.")
        print(f"[V] אתה מחובר רשמית לחשבון היוטיוב של: {channel_name}")
    else:
        print("\n[?] הטוקן תקין וגוגל מאשרת, אבל לא נמצא ערוץ יוטיוב פתוח תחת החשבון הזה.")

except urllib.error.HTTPError as e:
    print(f"\n[X] גוגל דחתה את הטוקן! (שגיאה {e.code})")
    print("המשמעות: הטוקן פג תוקף, נחסם, או שאישרת את החשבון הלא נכון (למשל האוניברסיטה במקום הפרטי).")
except Exception as e:
    print(f"\n[X] שגיאה פנימית: {e}")
