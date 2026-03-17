import speech_recognition as sr
import time

def check_levels():
    print("--- CONNECTING TO HARDWARE INDEX 0 ---")
    
    # חיבור ישיר לברזלים (בלי חיפושים)
    try:
        m = sr.Microphone(device_index=0)
    except Exception as e:
        print(f"Error connecting to mic: {e}")
        return

    r = sr.Recognizer()
    # אנחנו מכבים את הכיול האוטומטי כדי לראות את האמת
    r.dynamic_energy_threshold = False
    
    print("\n1. Please remain SILENT for 3 seconds...")
    with m as source:
        # כיול ראשוני קצר
        r.adjust_for_ambient_noise(source, duration=1)
        print(f"Base Noise Floor detected: {r.energy_threshold}")
        
    print("\n2. LIVE MONITORING (Start shouting!)")
    print("--------------------------------------")
    
    with m as source:
        while True:
            try:
                # קריאת דגימה מהמיקרופון
                audio_data = source.stream.read(source.CHUNK)
                # חישוב עוצמה מתמטי
                energy = int(abs(sum(audio_data) / len(audio_data)) * 2) 
                
                # תצוגה
                bars = "█" * (energy // 50)
                print(f"Volume: {energy:04d} | {bars}")
                time.sleep(0.05)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    check_levels()
