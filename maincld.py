import requests
import time
import threading
import http.server
import socketserver
import os
import sys
import socket

# ==========================================
# CONFIGURATION
# ==========================================
PORT = 8080
SOURCE_URL = "https://cloudtvplaylist.noobmaster.xyz/?download=m3u_playlist"
UPDATE_INTERVAL = 3600  # 1 Hour in seconds

# Headers to trick the server
HEADERS = {
    "User-Agent": "okhttp/4.12.1",
    "X-Requested-With": "com.blaze.sportzfy",
    "Accept-Encoding": "gzip",
    "Connection": "Keep-Alive",
    "Referer": "https://akashgo.noobmaster.xyz/"
}

# ==========================================
# HELPER: GET LOCAL WIFI IP
# ==========================================
def get_ip_address():
    try:
        # Connect to a public DNS (doesn't send data) just to find our own IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# ==========================================
# 1. PLAYLIST GENERATOR FUNCTION
# ==========================================
def generate_playlist():
    print(f"\n[🔄] Fetching fresh playlist from server...")
    try:
        response = requests.get(SOURCE_URL, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            # Save the file LOCALLY (Raw save, no link editing)
            with open("playlist.m3u", "w", encoding="utf-8") as f:
                f.write(response.text)
            
            print(f"[✅] Playlist updated successfully!")
            print(f"[📢] Credit: From @extendermaxtg") 
        else:
            print(f"[❌] Failed to fetch. Status: {response.status_code}")
    except Exception as e:
        print(f"[❌] Error fetching playlist: {e}")

# ==========================================
# 2. LOCAL SERVER (Background Thread)
# ==========================================
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Hide server logs to keep the countdown clean

def start_server():
    # Change directory to where the script is running
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    my_ip = get_ip_address()
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"\n==============================================")
        print(f"🚀 SERVER RUNNING")
        print(f"----------------------------------------------")
        print(f"📲 For THIS device (Termux):")
        print(f"   http://127.0.0.1:{PORT}/playlist.m3u")
        print(f"----------------------------------------------")
        print(f"📺 For TV / Other devices on same Router:")
        print(f"   http://{my_ip}:{PORT}/playlist.m3u")
        print(f"==============================================")
        httpd.serve_forever()

# ==========================================
# 3. MAIN LOOP & COUNTDOWN
# ==========================================
if __name__ == "__main__":
    # Start the server in a separate thread
    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()

    # Main Loop
    while True:
        generate_playlist()
        
        # Countdown Timer
        print(f"\n[⏳] Next update in:")
        try:
            for remaining in range(UPDATE_INTERVAL, 0, -1):
                mins, secs = divmod(remaining, 60)
                timer = '{:02d}:{:02d}'.format(mins, secs)
                # Overwrite the current line with the timer
                sys.stdout.write(f"\r     {timer} remaining... ")
                sys.stdout.flush()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[🛑] Stopping...")
            sys.exit()
