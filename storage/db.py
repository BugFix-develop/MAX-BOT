import sqlite3

DB_NAME = "math_bot.db"

def get_connection(db_path: str = DB_NAME) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn



def init_db(db_path: str = DB_NAME):
    conn = get_connection(db_path)
    cursor = conn.cursor()


    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            max_user_id TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'student',
            first_seen TIMESTAMP default CURRENT_TIMESTAMP
        )
    """)


    cursor.execute("""CREATE TABLE IF NOT EXISTS task_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    template_id INTEGER NOT NULL,
    task_text TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    user_answer TEXT,
    is_correct BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lesson_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    author_user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    grade INTEGER NOT NULL,
    content_markdown TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)
    """)

    conn.commit()
    conn.close()

