import os
import re
import subprocess
import threading
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLOUDFLARED_EXE = os.path.join(SCRIPT_DIR, "cloudflared.exe")
TUNNEL_URL_FILE = os.path.join(SCRIPT_DIR, "seller_hub_data", "tunnel_url.txt")

_tunnel_process = None
_tunnel_url = None
_lock = threading.Lock()


def get_current_tunnel_url():
    """Returns the current Cloudflare tunnel URL if active."""
    global _tunnel_url
    if _tunnel_url:
        return _tunnel_url
    if os.path.exists(TUNNEL_URL_FILE):
        try:
            with open(TUNNEL_URL_FILE, "r", encoding="utf-8") as f:
                url = f.read().strip()
                if url.startswith("https://") and "trycloudflare.com" in url:
                    _tunnel_url = url
                    return url
        except Exception:
            pass
    return None


def _monitor_tunnel(proc):
    global _tunnel_url
    url_pattern = re.compile(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com")
    try:
        for line in iter(proc.stderr.readline, ""):
            if not line:
                break
            match = url_pattern.search(line)
            if match:
                found_url = match.group(0)
                _tunnel_url = found_url
                os.makedirs(os.path.dirname(TUNNEL_URL_FILE), exist_ok=True)
                with open(TUNNEL_URL_FILE, "w", encoding="utf-8") as f:
                    f.write(found_url)
                print(f"[Cloudflare Tunnel Ready] {found_url}")
    except Exception as e:
        print(f"[Cloudflare Monitor Error] {e}")


def start_tunnel_background(port=8501):
    """Starts the Cloudflare tunnel in the background if not already running."""
    global _tunnel_process, _tunnel_url
    with _lock:
        existing_url = get_current_tunnel_url()
        if existing_url:
            return existing_url

        if not os.path.exists(CLOUDFLARED_EXE):
            return None

        try:
            # Run cloudflared tunnel
            proc = subprocess.Popen(
                [CLOUDFLARED_EXE, "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            _tunnel_process = proc

            thread = threading.Thread(target=_monitor_tunnel, args=(proc,), daemon=True)
            thread.start()

            # Wait up to 10 seconds for URL to appear
            for _ in range(20):
                time.sleep(0.5)
                cur = get_current_tunnel_url()
                if cur:
                    return cur
        except Exception as e:
            print(f"[Start Tunnel Failed] {e}")
            return None
    return get_current_tunnel_url()


def stop_tunnel():
    """Stops the tunnel process."""
    global _tunnel_process, _tunnel_url
    with _lock:
        if _tunnel_process:
            try:
                _tunnel_process.terminate()
            except Exception:
                pass
            _tunnel_process = None
        _tunnel_url = None
        if os.path.exists(TUNNEL_URL_FILE):
            try:
                os.remove(TUNNEL_URL_FILE)
            except Exception:
                pass


if __name__ == "__main__":
    print("Testing tunnel startup...")
    url = start_tunnel_background(8501)
    print(f"Result URL: {url}")
