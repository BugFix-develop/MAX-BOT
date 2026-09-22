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

DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "math_bot.db"))
