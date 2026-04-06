import pyaudio

p = pyaudio.PyAudio()

print("\n--- Scanning Audio Devices ---")
print(f"Default Input Device Index: {p.get_default_input_device_info()['index']}")

for i in range(p.get_device_count()):
    try:
        info = p.get_device_info_by_index(i)
        # מסננים רק התקנים שיש להם יכולת הקלטה (מיקרופונים)
        if info['maxInputChannels'] > 0:
            print(f"Index {i}: {info['name']} (Max Channels: {info['maxInputChannels']}, Rate: {int(info['defaultSampleRate'])})")
    except:
        continue

print("------------------------------\n")
