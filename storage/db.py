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


def is_task_already_solved(user_id: str, task_text: str, db_path: str = DB_NAME ) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT 1 FROM task_history
        WHERE user_id = ? AND task_text = ? AND is_correct = 1
        LIMIT 1
        """, (user_id, task_text))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_or_create_user(max_user_id: str, role: str = "student", db_path: str = DB_NAME) -> dict:
    """Регистрация или получение пользователя из базы."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE max_user_id = ?", (max_user_id,))
    row = cursor.fetchone()
    if row is not None:
        user_data = dict(row)
        conn.close()
        return user_data

    cursor.execute("INSERT INTO users (max_user_id, role) VALUES (?, ?)", (max_user_id, role))
    conn.commit()

    cursor.execute("SELECT * FROM users WHERE max_user_id = ?", (max_user_id,))
    new_row = cursor.fetchone()
    user_data = dict(new_row) if new_row else {}
    conn.close()
    return user_data


def save_task_issue(user_id: str, template_id: int, task_text: str, expected_answer: str, db_path: str = DB_NAME,
) -> int:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO task_history (user_id, template_id, task_text, expected_answer)
        VALUES (?, ?, ?, ?)
    """, (user_id, template_id, task_text, expected_answer))

    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return task_id


def save_task_result( task_id: int, user_answer: str, is_correct: bool, db_path: str = DB_NAME) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE task_history
        SET user_answer = ?, is_correct = ?
        WHERE id = ?
    """, (user_answer, int(is_correct), task_id))

    conn.commit()
    conn.close()


def get_user_statistics(user_id: str, db_path: str = DB_NAME) -> dict:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            COUNT(*) AS total,
            SUM(is_correct) AS correct
        FROM task_history
        WHERE user_id = ? AND user_answer IS NOT NULL
    """, (user_id,))

    row = cursor.fetchone()
    conn.close()

    total = row["total"] or 0
    correct = row["correct"] or 0
    accuracy = round((correct / total) * 100, 1) if total > 0 else 0.0

    return {
        "total_solved": total,
        "correct_answers": correct,
        "accuracy_percent": accuracy,
    }


def save_lesson_plan(user_id: str, topic: str, grade: int, markdown: str, db_path: str = DB_NAME) -> int:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO lesson_plans (author_user_id, topic, grade, content_markdown)
        VALUES (?, ?, ?, ?)
    """, (user_id, topic, grade, markdown))

    conn.commit()
    plan_id = cursor.lastrowid
    conn.close()
    return plan_id
