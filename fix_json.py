import json
path = '/home/kido1/Smartroom/config/oauth.json'
with open(path, 'r') as f:
    data = json.load(f)

# מושך את הנתונים מאיפה שהם לא מתחבאים כרגע
core = data.get('oauth_credentials') if 'oauth_credentials' in data and 'access_token' in data.get('oauth_credentials', {}) else data

perfect_json = {
    "access_token": core.get("access_token"),
    "refresh_token": core.get("refresh_token"),
    "expires_at": core.get("expires_at", 0),
    "expires_in": core.get("expires_in", 3599),
    "oauth_credentials": {
        "client_id": core.get("client_id", ""),
        "client_secret": core.get("client_secret", "")
    }
}

with open(path, 'w') as f:
    json.dump(perfect_json, f, indent=4)
print("[V] הקובץ oauth.json סודר והוא כעת במבנה המושלם!")
