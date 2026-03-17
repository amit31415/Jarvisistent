import google.generativeai as genai

API_KEY = "AIzaSyChruYPFeRl44zPuvzyo6GopTtbJyXi4L8"  # <--- שים את המפתח שלך כאן
genai.configure(api_key=API_KEY)

print("--- Scanning for available models ---")
try:
    for m in genai.list_models():
        # אנחנו מחפשים רק מודלים שיודעים לייצר תוכן (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            print(f"Found: {m.name}")
except Exception as e:
    print(f"Error: {e}")
