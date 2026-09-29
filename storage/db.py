import sqlite3

DB_NAME = "math_bot.db"

def get_connection(db_path: str = DB_NAME) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn



def init_db(db_path: str = DB_NAME):
    conn = get_connection(db_path)
    try:
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
        except Exception:
            pass
        cursor = conn.cursor()

        cursor.execute(""" 
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                max_user_id TEXT UNIQUE NOT NULL,
                role TEXT DEFAULT 'student',
                chat_id TEXT,
                first_seen TIMESTAMP default CURRENT_TIMESTAMP
            )
        """)
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN chat_id TEXT")
        except Exception:
            pass

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

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            user_id TEXT PRIMARY KEY,
            state TEXT NOT NULL DEFAULT 'STATE_ONBOARDING',
            role TEXT DEFAULT 'student',
            grade INTEGER DEFAULT 7,
            topic TEXT DEFAULT 'ФСУ',
            format TEXT,
            current_task_idx INTEGER DEFAULT 0,
            total_tasks INTEGER DEFAULT 5,
            correct_count INTEGER DEFAULT 0,
            current_task_text TEXT,
            current_expected_answer TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
    finally:
        conn.close()


def is_task_already_solved(user_id: str, task_text: str, db_path: str = DB_NAME) -> bool:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM task_history
            WHERE user_id = ? AND task_text = ? AND is_correct = 1
            LIMIT 1
            """, (user_id, task_text))
        row = cursor.fetchone()
        return row is not None
    finally:
        conn.close()


def get_or_create_user(max_user_id: str, role: str = "student", chat_id: str | int | None = None, db_path: str = DB_NAME) -> dict:
    """Регистрация или получение пользователя из базы с сохранением chat_id."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE max_user_id = ?", (str(max_user_id),))
        row = cursor.fetchone()
        if row is not None:
            user_data = dict(row)
            if chat_id is not None and str(user_data.get("chat_id") or "") != str(chat_id):
                cursor.execute("UPDATE users SET chat_id = ? WHERE max_user_id = ?", (str(chat_id), str(max_user_id)))
                conn.commit()
                user_data["chat_id"] = str(chat_id)
            return user_data

        try:
            cursor.execute(
                "INSERT INTO users (max_user_id, role, chat_id) VALUES (?, ?, ?)",
                (str(max_user_id), role, str(chat_id) if chat_id else None)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()

        cursor.execute("SELECT * FROM users WHERE max_user_id = ?", (str(max_user_id),))
        new_row = cursor.fetchone()
        return dict(new_row) if new_row else {}
    finally:
        conn.close()


def get_all_active_users(db_path: str = DB_NAME) -> list[dict]:
    """Возвращает список всех зарегистрированных пользователей."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE max_user_id IS NOT NULL")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def save_task_issue(user_id: str, template_id: int, task_text: str, expected_answer: str, db_path: str = DB_NAME) -> int:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO task_history (user_id, template_id, task_text, expected_answer)
            VALUES (?, ?, ?, ?)
        """, (user_id, template_id, task_text, expected_answer))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def save_task_result(task_id: int, user_answer: str, is_correct: bool, db_path: str = DB_NAME) -> None:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE task_history
            SET user_answer = ?, is_correct = ?
            WHERE id = ?
        """, (user_answer, int(is_correct), task_id))
        conn.commit()
    finally:
        conn.close()


def get_user_statistics(user_id: str, db_path: str = DB_NAME) -> dict:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                COUNT(*) AS total,
                SUM(is_correct) AS correct
            FROM task_history
            WHERE user_id = ? AND user_answer IS NOT NULL
        """, (user_id,))
        row = cursor.fetchone()

        total = row["total"] or 0
        correct = row["correct"] or 0
        accuracy = round((correct / total) * 100, 1) if total > 0 else 0.0

        return {
            "total_solved": total,
            "correct_answers": correct,
            "accuracy_percent": accuracy,
        }
    finally:
        conn.close()


def save_lesson_plan(user_id: str, topic: str, grade: int, markdown: str, db_path: str = DB_NAME) -> int:
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lesson_plans (author_user_id, topic, grade, content_markdown)
            VALUES (?, ?, ?, ?)
        """, (user_id, topic, grade, markdown))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

