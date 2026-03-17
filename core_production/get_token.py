from google_auth_oauthlib.flow import InstalledAppFlow

# הרשאות לקריאת מיילים (בדיוק מה שג'ארוויס צריך)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

print("Starting Google Authentication Flow...")
# קורא את ה-Credentials שהורדת הרגע
flow = InstalledAppFlow.from_client_secrets_file('core_production/credentials.json', SCOPES)

# פותח דפדפן או נותן לינק לאישור
creds = flow.run_local_server(port=0)

# שומר את הטוקן למקום הנכון!
with open('core_production/token.json', 'w') as token:
    token.write(creds.to_json())

print("SUCCESS! token.json has been created in core_production.")