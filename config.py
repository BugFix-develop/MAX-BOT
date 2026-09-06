import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR: Path  = Path(__file__).resolve().parent

DATA_DIR: Path = BASE_DIR / "data"

TAMPLATES_PATH: Path  = DATA_DIR / "templates.json"

ENV_FILE: Path = BASE_DIR / ".env"

load_dotenv(dotenv_path = ENV_FILE)

MAX_BOT_TOKEN: str = os.getenv("MAX_BOT_TOKEN", "")

DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "math_bot.db"))
