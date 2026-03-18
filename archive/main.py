import time
from gpiozero import CPUTemperature, LoadAverage

# --- הגדרות מערכת ---
# כאן נגדיר בעתיד את הפינים של המנורות (למשל: LIGHT_PIN = 17)
# כרגע אנחנו עובדים במצב סימולציה (Dry Run)

def read_sensors():
    """
    פונקציה שאוספת נתונים מהחיישנים.
    כרגע קוראת את המדדים הפנימיים של המעבד.
    """
    cpu = CPUTemperature()
    load = LoadAverage()
    return cpu.temperature, load.load_average

def logic_cycle(temp, load):
    """
    המוח: מקבל נתונים ומחליט מה לעשות.
    """
    # לוגיקה לדוגמה: אם המעבד חם מדי - תדליק התראת חירום (בעתיד: מאוורר נוסף/אור אדום)
    alert_triggered = False
    
    if temp > 60.0:
        print(f"[ALERT] High Temperature Detected: {temp}°C")
        alert_triggered = True
    
    return alert_triggered

def main():
    print("--- Smart Room Core System Started ---")
    print("Initializing sensors...")
    
    try:
        # הלולאה האינסופית (The Heartbeat)
        while True:
            # 1. דגימה (Sensing)
            current_temp, current_load = read_sensors()
            
            # 2. עיבוד והחלטה (Processing)
            is_alert = logic_cycle(current_temp, current_load)
            
            # 3. דיווח סטטוס (Telemetry)
            # מדפיס רק כדי שנראה שהמערכת חיה
            print(f"Status | Temp: {current_temp:.1f}°C | Load: {current_load:.1f} | Alert: {is_alert}")
            
            # המתנה של 2 שניות בין דגימות (כדי לא להעמיס על המעבד סתם)
            time.sleep(2)
            
    except KeyboardInterrupt:
        # תופס את הלחיצה על Ctrl+C כדי לצאת יפה
        print("\n--- System Shutdown Request Received ---")
        print("Safety protocols engaged. Goodbye.")

if __name__ == "__main__":
    main()
