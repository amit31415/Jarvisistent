import subprocess
import os
import json
import time
from ytmusicapi import YTMusic

class MusicManager:
    def __init__(self):
        self.auth_path = '/home/kido1/Smartroom/config/oauth.json'
        self.socket_path = '/tmp/mpv-music-socket'
        self.yt = None
        
        if os.path.exists(self.auth_path):
            try:
                # קריאה נקייה בלבד - בלי לשנות את הקובץ!
                with open(self.auth_path, 'r') as f:
                    data = json.load(f)
                
                # שולפים את המפתחות (אם קיימים)
                client_id = data.get("client_id")
                client_secret = data.get("client_secret")
                
                custom_creds = None
                if client_id and client_secret:
                    custom_creds = {
                        "client_id": client_id,
                        "client_secret": client_secret
                    }
                
                # מפעילים את YTMusic
                self.yt = YTMusic(auth=self.auth_path, oauth_credentials=custom_creds)
                print("[INFO] YouTube Music authenticated perfectly. ✅")
            except Exception as e:
                print(f"[WARNING] Music auth failed: {e}. Running in Guest mode.")
                self.yt = YTMusic()
        else:
            self.yt = YTMusic()
            print("[WARNING] Music running in Guest mode (no private playlists).")

    def _send_mpv_command(self, command_list):
        """שולח פקודות לנגן הרץ דרך ה-Socket"""
        payload = json.dumps({"command": command_list})
        try:
            subprocess.run(
                ['socat', '-', f'UNIX-CONNECT:{self.socket_path}'],
                input=payload.encode(),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
            return True
        except:
            return False

    def play(self, query):
        """מחפש שיר כללי ביוטיוב ומנגן"""
        print(f"[MUSIC] Searching for: {query}")
        search_results = self.yt.search(query, filter="songs")
        
        if not search_results:
            return "לא מצאתי את השיר שביקשת."

        video_id = search_results[0]['videoId']
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        self.stop()
        cmd = [
            'mpv', url,
            '--no-video',
            f'--input-ipc-server={self.socket_path}',
            '--volume=70',
            '--idle=yes'
        ]
        self.player_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"מנגן כעת: {search_results[0]['title']}"

    def play_my_playlist(self, playlist_name):
        """מחפש בפלייליסטים הפרטיים שלך ומנגן"""
        if not self.yt: return "אין גישה לחשבון הפרטי."
        
        playlists = self.yt.get_library_playlists()
        
        # חיפוש חכם: בודק אם השם שביקשת נמצא בתוך אחד משמות הפלייליסטים (ללא תלות באותיות גדולות/קטנות)
        target = next((p for p in playlists if playlist_name.lower() in p['title'].lower()), None)
        
        if target:
            url = f"https://www.youtube.com/watch?list={target['browseId']}"
            self.stop()
            cmd = [
                'mpv', url, 
                '--no-video', 
                f'--input-ipc-server={self.socket_path}',
                '--volume=70',
                '--idle=yes'
            ]
            self.player_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return f"מפעיל את הפלייליסט שלך: {target['title']}"
            
        return "לא מצאתי פלייליסט כזה בחשבון שלך."

    def pause(self):
        self._send_mpv_command(["set_property", "pause", True])
        return "המוזיקה הושהתה."

    def resume(self):
        self._send_mpv_command(["set_property", "pause", False])
        return "ממשיך לנגן."

    def skip(self):
        self._send_mpv_command(["playlist-next"])
        return "מדלג לשיר הבא."

    def stop(self):
        subprocess.run(['killall', '-9', 'mpv'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(self.socket_path):
            try: os.remove(self.socket_path)
            except: pass
        self.player_process = None

    def get_my_playlists(self):
        """מחזיר את שמות כל הפלייליסטים של המשתמש"""
        if not self.yt: return "אין גישה לחשבון הפרטי."
        try:
            playlists = self.yt.get_library_playlists(limit=20)
            if not playlists:
                return "לא מצאתי פלייליסטים שמורים בחשבון שלך."
            
            output = "הפלייליסטים שלך:\n"
            for i, p in enumerate(playlists, 1):
                output += f"{i}. {p.get('title', 'ללא שם')}\n"
            return output
        except Exception as e:
            return f"שגיאה בשליפת הפלייליסטים: {e}"

    def get_recent_songs(self, limit=10):
        """מחזיר את היסטוריית ההשמעות (השירים האחרונים ששמעת)"""
        if not self.yt: return "אין גישה לחשבון הפרטי."
        try:
            history = self.yt.get_history()
            if not history:
                return "היסטוריית ההשמעות שלך ריקה או לא זמינה."
            
            output = f"{limit} השירים האחרונים ששמעת:\n"
            for i, track in enumerate(history[:limit], 1):
                title = track.get('title', 'לא ידוע')
                # מוציא את שמות האמנים בצורה יפה
                artists = ", ".join([a['name'] for a in track.get('artists', [])]) if track.get('artists') else 'לא ידוע'
                output += f"{i}. {title} (מאת: {artists})\n"
            return output
        except Exception as e:
            return f"שגיאה בשליפת היסטוריית שירים: {e}"