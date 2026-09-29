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

WEBAPP_PORT: int = int(os.getenv("WEBAPP_PORT", "8080"))
WEBAPP_HOST: str = os.getenv("WEBAPP_HOST", "0.0.0.0")
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "t594_hakaton_max_bot")
WEBAPP_URL: str = os.getenv("WEBAPP_URL", f"https://max.ru/{BOT_USERNAME}?startapp")

