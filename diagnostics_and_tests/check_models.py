import google.generativeai as genai
import os

# --- שים את המפתח שלך כאן ---
API_KEY = "AIzaSyChruYPFeRl44zPuvzyo6GopTtbJyXi4L8"
genai.configure(api_key=API_KEY)

print("--- Testing Models for Free Tier Compatibility ---\n")

# משיג את כל המודלים
for m in genai.list_models():
    # בודק רק מודלים שיודעים לייצר טקסט (ולא רק הטמעת וקטורים)
    if 'generateContent' in m.supported_generation_methods:
        model_name = m.name
        print(f"Testing {model_name}...", end=" ", flush=True)
        
        try:
            # מנסה לייצר מודל ולשלוח הודעה קצרה
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Hi", request_options={"timeout": 5})
            
            # אם הגענו לפה - זה עבד!
            print("✅ SUCCESS (Available)")
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "Quota" in error_msg:
                print("❌ FAILED (Quota/Paid Only)")
            elif "404" in error_msg:
                print("❌ FAILED (Not Found/Deprecated)")
            else:
                print(f"⚠️ ERROR: {error_msg[:50]}...")

print("\n--- Done ---")
