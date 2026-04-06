from ytmusicapi import YTMusic
try:
    print("[*] מתחבר לחשבון היוטיוב שלך...")
    yt = YTMusic('/home/kido1/Smartroom/config/oauth.json')
    playlists = yt.get_library_playlists()
    print("\n[V] הצלחה! הפלייליסטים שלך:")
    for p in playlists:
        print(f" - {p['title']}")
except Exception as e:
    print(f"\n[X] שגיאה: {e}")
