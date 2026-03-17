import os
import google.generativeai as genai
from dotenv import load_dotenv

print("--- DIAGNOSTIC MODE ---")

# 1. בדיקת טעינת קובץ .env
print("1. Loading .env file...", end=" ")
loaded = load_dotenv()
if loaded:
    print("✅ Found.")
else:
    print("❌ NOT FOUND! Make sure '.env' is in the same folder.")

# 2. בדיקת תוכן המפתחות (בלי להדפיס אותם מלא)
gemini_key = os.getenv("GEMINI_KEY")
porcupine_key = os.getenv("PORCUPINE_KEY")

if gemini_key:
    print(f"2. Gemini Key loaded: ✅ (Starts with: {gemini_key[:5]}...)")
else:
    print("2. Gemini Key loaded: ❌ (Variable is empty)")

if porcupine_key:
    print(f"3. Porcupine Key loaded: ✅ (Starts with: {porcupine_key[:5]}...)")
else:
    print("3. Porcupine Key loaded: ❌ (Variable is empty)")

# 3. בדיקת חיבור בפועל לגוגל
if gemini_key:
    print("\n4. Testing connection to Google...", end=" ")
    try:
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-flash-latest')
        response = model.generate_content("Ping")
        print("✅ SUCCESS!")
        print(f"   Response received: {response.text}")
    except Exception as e:
        print(f"\n❌ CONNECTION FAILED: {e}")
        print("   -> Check if the API Key is valid.")
        print("   -> Check internet connection.")
        print("   -> Check Quota.")

print("\n--- END ---")
