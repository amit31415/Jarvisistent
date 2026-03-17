from gtts import gTTS
import os
import subprocess

def speak(text):
    print(f"Room says: {text}")
    
    # 1. שליחת הטקסט לגוגל וקבלת קובץ אודיו
    # lang='en' לאנגלית, lang='iw' לעברית!
    tts = gTTS(text=text, lang='en') 
    
    # 2. שמירה זמנית לדיסק
    filename = "speech.mp3"
    tts.save(filename)
    
    # 3. ניגון הקובץ באמצעות mpg123
    # הפקודה מריצה נגן MP3 קליל דרך הטרמינל
    subprocess.run(['mpg123', '-q', filename])

if __name__ == "__main__":
    print("--- Starting HD Audio Check ---")
    
    # בדיקה באנגלית
    speak("System online. Updating audio drivers to High Definition.")
    speak("Welcome to your smart room via Bluetooth.")
    
    # רוצה לנסות עברית? שנה למעלה ל-lang='iw' ותכתוב כאן בעברית
    # speak("שלום, החדר החכם מוכן") 
    
    print("--- Check Complete ---")
