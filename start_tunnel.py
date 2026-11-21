import os
import re
import subprocess
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED_EXE = os.path.join(SCRIPT_DIR, "cloudflared.exe")
TUNNEL_URL_FILE = os.path.join(SCRIPT_DIR, "seller_hub_data", "tunnel_url.txt")
os.makedirs(os.path.dirname(TUNNEL_URL_FILE), exist_ok=True)

print("Starting cloudflared tunnel daemon...")

while True:
    try:
        proc = subprocess.Popen(
            [CLOUDFLARED_EXE, "tunnel", "--url", "http://localhost:8501"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
        found = False

        for line in iter(proc.stderr.readline, ""):
            if not line:
                break
            match = url_pattern.search(line)
            if match and not found:
                found_url = match.group(0)
                with open(TUNNEL_URL_FILE, "w", encoding="utf-8") as f:
                    f.write(found_url)
                print(f"[ACTIVE TUNNEL] {found_url}", flush=True)
                found = True

        proc.wait()
        print("Tunnel process ended, restarting in 3 seconds...", flush=True)
        time.sleep(3)
    except Exception as e:
        print(f"Error in tunnel daemon: {e}", flush=True)
        time.sleep(5)
