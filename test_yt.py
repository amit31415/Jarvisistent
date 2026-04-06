import json
from ytmusicapi import YTMusic

auth_path = '/home/kido1/Smartroom/config/oauth.json'
try:
    with open(auth_path, 'r') as f:
        data = json.load(f)
    print("[V] File loaded. Keys:", list(data.keys()))
    
    yt = YTMusic(auth_path)
    print("[V] YTMusic init SUCCESS.")
    
    playlists = yt.get_library_playlists()
    print(f"[V] Playlists SUCCESS. Found: {len(playlists)}")
    for p in playlists[:3]:
        print(f" - {p.get('title')}")
except Exception as e:
    print(f"\n[ERROR] {type(e).__name__}: {str(e)}")
