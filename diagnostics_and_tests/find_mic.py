import speech_recognition as sr

print("--- Searching for Microphones ---")
mics = sr.Microphone.list_microphone_names()

for i, name in enumerate(mics):
    print(f"Index {i}: {name}")
