import os
from pathlib import Path
BASE_DIR: Path = Path(__file__).resolve().parent
DATA_DIR: Path = BASE_DIR / "data"
TEMPLATES_PATH: Path = DATA_DIR / "templates.json"
ENV_FILE: Path = BASE_DIR / ".env"

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=ENV_FILE)
except ImportError:
    if ENV_FILE.exists():
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

MAX_BOT_TOKEN: str = os.getenv("MAX_BOT_TOKEN", "")
MAX_API_BASE_URL: str = os.getenv("MAX_API_BASE_URL", "https://platform-api2.max.ru")

DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "math_bot.db"))

def get_local_ip() -> str:
    try:
        import subprocess
        # Check standard LAN IP using ip route or hostname -I
        out = subprocess.check_output(["hostname", "-I"], text=True).strip()
        for ip in out.split():
            if ip.startswith("192.168.") or ip.startswith("10.") or (ip.startswith("172.") and not ip.startswith("172.18.")):
                return ip
        # Fallback to socket
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LOCAL_IP: str = get_local_ip()
WEBAPP_PORT: int = int(os.getenv("WEBAPP_PORT", "8080"))
WEBAPP_HOST: str = os.getenv("WEBAPP_HOST", "0.0.0.0")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "t594_hakaton_max_bot")

# Default WEBAPP_URL:
# 1. Use os.getenv("WEBAPP_URL") if user explicitly specified it in .env (and not containing '?startapp' which causes 'такого нет' error).
# 2. Otherwise default to http://{LOCAL_IP}:{WEBAPP_PORT} (will be dynamically updated if auto-tunnel is active).
_raw_webapp_url = os.getenv("WEBAPP_URL", "")
if _raw_webapp_url and "?startapp" not in _raw_webapp_url:
    WEBAPP_URL: str = _raw_webapp_url
else:
    WEBAPP_URL: str = f"http://{LOCAL_IP}:{WEBAPP_PORT}"

ENABLE_TUNNEL: bool = os.getenv("ENABLE_TUNNEL", "true").lower() in ("1", "true", "yes")


