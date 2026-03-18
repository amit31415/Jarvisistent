import requests
import time

def test_local_model(model_name):
    print(f"\n[!] מריץ טסט למודל: {model_name}...")
    url = "http://localhost:11434/api/generate"
    
    # פרומפט שדורש הבנה והפקה בעברית
    prompt = "You are Jarvis. Reply strictly in Hebrew. Say exactly: 'שלום אדוני, אני המוח המקומי שלך וסיימתי לעלות.'"
    
    start_time = time.time()
    try:
        response = requests.post(url, json={
            "model": model_name,
            "prompt": prompt,
            "stream": False
        })
        text = response.json().get("response", "").strip()
        duration = time.time() - start_time
        
        print(f"⏱️ זמן תגובה: {duration:.2f} שניות")
        print(f"🤖 תשובת המודל: {text}")
        
    except Exception as e:
        print(f"❌ שגיאה בחיבור לשרת אולמה: {e}")

if __name__ == "__main__":
    print("מתחיל תחרות ביצועים על הברזלים של הרסברי פאי...")
    test_local_model("qwen2.5:1.5b")
    test_local_model("llama3.2:latest")
