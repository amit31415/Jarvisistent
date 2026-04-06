import speech_recognition as sr
import sys
import time

def monitor():
    print("--- RAW MICROPHONE MONITOR ---")
    print("Ignore the 'Threshold', look at the 'Energy'.")
    print("Ctrl+C to stop.")
    
    # חיבור כפוי להתקן 0 (ה-USB שלך)
    try:
        source = sr.Microphone(device_index=0)
    except:
        print("Could not find mic at index 0, trying default...")
        source = sr.Microphone()

    r = sr.Recognizer()
    r.dynamic_energy_threshold = False # אנחנו רוצים לראות את האמת, בלי תיקונים אוטומטיים

    with source:
        print("Calibrating background noise (1 sec)...")
        r.adjust_for_ambient_noise(source, duration=1)
        print(f"Base detected noise level: {r.energy_threshold}")
        print("-" * 40)
        
        while True:
            try:
                # קריאת 'בלוק' קטנטן של מידע
                buffer = source.stream.read(source.CHUNK)
                
                # חישוב מתמטי של העוצמה (RMS)
                energy = int(sum(abs(x) for x in buffer) / len(buffer))
                
                # יצירת בר גרפי
                bar_len = min(energy // 10, 50) # הגבלה שלא ישבור שורה
                bar = "#" * bar_len
                
                # הדפסה שמתעדכנת באותה שורה
                sys.stdout.write(f"\rEnergy: {energy:04d} | {bar}")
                sys.stdout.flush()
                
            except KeyboardInterrupt:
                print("\nStopped.")
                break
            except Exception as e:
                # התעלמות משגיאות קטנות כדי שהלופ לא ייעצר
                continue

if __name__ == "__main__":
    monitor()
