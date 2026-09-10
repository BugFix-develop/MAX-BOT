# Руководство: Реализация слоя работы с БД в Python после C++ (Qt SQL)

> **Цель руководства:** Объяснить ментальные модели и синтаксические паттерны Python `sqlite3` на параллельном примере (сервис онлайн-библиотеки / игрового магазина **GameStore**), чтобы ты мог самостоятельно написать все функции для `storage/db.py`.

---

## Ментальная карта: Qt (C++) против Python (`sqlite3`)

| Концепция | В C++ (Qt SQL) | В Python (`sqlite3`) |
| :--- | :--- | :--- |
| **Соединение** | `QSqlDatabase db = QSqlDatabase::addDatabase("QSQLITE");` | `conn = sqlite3.connect("file.db")` |
| **Указатель / Запрос** | `QSqlQuery query(db);` | `cursor = conn.cursor()` |
| **Биндинг параметров** | `query.bindValue(":param", val);` или `query.addBindValue(val);` | Кортеж параметров во второй аргумент `execute("... ?", (val,))` |
| **Проверка наличия строки** | `if (query.next())` | `row = cursor.fetchone()` $\to$ `if row is not None:` |
| **ID созданной строки** | `query.lastInsertId().toInt()` | `cursor.lastrowid` |
| **Доступ к полям** | `query.value("name").toString()` | `row["name"]` (если включен `row_factory = sqlite3.Row`) |
| **Фиксация на диске** | `db.commit()` | `conn.commit()` |
| **Закрытие соединения** | `db.close()` | `conn.close()` |

---

## Паттерн 1: `get_connection()` и `init_db()` (Подключение и создание таблиц)

### Как это устроено в Qt (C++):
```cpp
// C++ / Qt
QSqlDatabase createConnection(const QString& path) {
    QSqlDatabase db = QSqlDatabase::addDatabase("QSQLITE");
    db.setDatabaseName(path);
    db.open();
    return db;
}

void initDatabase(const QString& path) {
    QSqlDatabase db = createConnection(path);
    QSqlQuery query(db);
    query.exec(R"(
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE NOT NULL
        );
    )");
    db.commit();
}
```

### Как это пишется в Python:
```python
import sqlite3

DEFAULT_DB = "app.db"

def get_connection(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    # Позволяет обращаться row["column_name"] вместо row[0]
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DEFAULT_DB) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # В одном cursor.executescript() или нескольких cursor.execute()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT UNIQUE NOT NULL
    );
    """)

    conn.commit()  # Записать изменения на диск
    conn.close()   # Освободить дескриптор файла
```

---

## Паттерн 2: `get_or_create` (Получить запись или создать, если её нет)

**Задача:** Пользователь нажал кнопку. Если он уже есть в базе — вернуть его данные. Если его нет — зарегистрировать и вернуть созданную запись.

### Концепция алгоритма:
1. Делаем `SELECT` по уникальному полю (`WHERE user_id = ?`).
2. Вызываем `cursor.fetchone()`.
3. Если результат **не пустой** (`if row:`), превращаем его в словарь (`dict(row)`) и возвращаем.
4. Если результат **пустой** (`else:`), делаем `INSERT INTO ...`.
5. Делаем `conn.commit()`.
6. Делаем повторный `SELECT` или возвращаем сформированный словарь.

### Пример на игровой платформе:
```python
def get_or_create_player(player_tag: str, role: str = "guest", db_path: str = DEFAULT_DB) -> dict:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Проверяем, существует ли уже игрок
    # ВАЖНО: (player_tag,) — запятая обязательна, чтобы Python понял, что это кортеж (tuple)!
    cursor.execute("SELECT * FROM players WHERE player_tag = ?", (player_tag,))
    row = cursor.fetchone()

    if row is not None:
        conn.close()
        return dict(row)  # Превращаем Row в обычный словарь Python {'id': 1, ...}

    # 2. Игрока нет — создаем новую запись
    cursor.execute(
        "INSERT INTO players (player_tag, role) VALUES (?, ?)",
        (player_tag, role)
    )
    conn.commit()

    # 3. Достаем только что созданного игрока
    cursor.execute("SELECT * FROM players WHERE player_tag = ?", (player_tag,))
    new_row = cursor.fetchone()
    conn.close()

    return dict(new_row)
```

---

## Паттерн 3: `is_record_exists` (Быстрая булева проверка)

**Задача:** Быстро проверить, совершал ли пользователь действие ранее (возвращает строго `True` или `False`).

### В C++ (Qt):
```cpp
bool isItemPurchased(int userId, int itemId) {
    QSqlQuery q;
    q.prepare("SELECT 1 FROM purchases WHERE user_id = ? AND item_id = ? LIMIT 1");
    q.addBindValue(userId);
    q.addBindValue(itemId);
    q.exec();
    return q.next(); // true если найдена хоть одна запись
}
```

### В Python:
Вместо `SELECT *` (который тянет все колонки в память) используется легковесный трюк: `SELECT 1 FROM table WHERE ... LIMIT 1`:
```python
def is_item_purchased(user_id: str, item_title: str, db_path: str = DEFAULT_DB) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT 1 FROM purchases WHERE user_id = ? AND item_title = ? LIMIT 1",
        (user_id, item_title)
    )
    result = cursor.fetchone()
    conn.close()

    # Если запись найдена, result будет равен (1,), иначе None
    return result is not None
```

---

## Паттерн 4: `save_issue` (Вставка и получение `last_insert_id`)

**Задача:** Создать запись о выданном элементе/задаче и вернуть её числовой `id` для дальнейшего обновления.

### В C++ (Qt):
```cpp
int addOrder(int userId, const QString& title) {
    QSqlQuery q;
    q.prepare("INSERT INTO orders (user_id, title) VALUES (?, ?)");
    // bind...
    q.exec();
    return q.lastInsertId().toInt();
}
```

### В Python:
У объекта `cursor` есть специальное поле **`cursor.lastrowid`**:
```python
def save_quest_issue(player_id: str, quest_id: int, quest_text: str, answer: str, db_path: str = DEFAULT_DB) -> int:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO quests_log (player_id, quest_id, quest_text, expected_answer)
        VALUES (?, ?, ?, ?)
    """, (player_id, quest_id, quest_text, answer))

    conn.commit()
    assigned_id = cursor.lastrowid  # Получаем автоинкрементный id созданной строки!
    conn.close()

    return assigned_id
```

---

## Паттерн 5: `save_result` (Обновление существующей записи: `UPDATE`)

**Задача:** Когда пользователь ответил, найти запись по `id` и сохранить его ответ и статус (`is_correct`).

### В Python:
```python
def save_quest_result(log_id: int, player_answer: str, is_passed: bool, db_path: str = DEFAULT_DB) -> None:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # В SQLite тип BOOLEAN сохраняется как 1 (True) или 0 (False)
    cursor.execute("""
        UPDATE quests_log 
        SET user_answer = ?, is_passed = ?
        WHERE id = ?
    """, (player_answer, int(is_passed), log_id))

    conn.commit()
    conn.close()
```

---

## Паттерн 6: `get_user_statistics` (Агрегация в SQL: `COUNT`, `SUM`, `%`)

**Задача:** Посчитать:
1. Сколько всего задач решил пользователь.
2. Сколько из них решено верно.
3. Процент успешности (% accuracy).

### Мощь SQL против циклов в Python:
*Не нужно* доставать 1000 строк в Python и крутить цикл `for`. База данных SQLite умеет считать всё на уровне C-ядра мгновенно с помощью функций `COUNT()` и `SUM()`!

### Пример аналитического запроса:
```sql
SELECT 
    COUNT(*) AS total_count,
    SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct_count
FROM task_history 
WHERE user_id = ? AND user_answer IS NOT NULL;
```

### Как это обрабатывается в коде:
```python
def get_player_stats(player_id: str, db_path: str = DEFAULT_DB) -> dict:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            COUNT(*) AS total_tasks,
            SUM(CASE WHEN is_passed = 1 THEN 1 ELSE 0 END) AS correct_tasks
        FROM quests_log
        WHERE player_id = ? AND user_answer IS NOT NULL
    """, (player_id,))

    row = cursor.fetchone()
    conn.close()

    total = row["total_tasks"] or 0
    # Если total == 0, SUM() в SQL вернет NULL (в Python это None)
    correct = row["correct_tasks"] or 0

    # Защита от деления на 0 (DivisionByZero)
    accuracy_percent = round((correct / total * 100), 1) if total > 0 else 0.0

    return {
        "total_solved": total,
        "correct_answers": correct,
        "accuracy_percent": accuracy_percent
    }
```

---

## Паттерн 7: `save_lesson_plan` (Сохранение длинного текста / Markdown)

**Задача:** Сохранить большой многострочный Markdown-конспект учителя.

В SQLite тип `TEXT` не имеет ограничений по длине (в отличие от некоторых СУБД с `VARCHAR(255)`). Ты можешь передавать строку в мегабайт размером, используя всё тот же параметризованный запрос `?`:

```python
def save_document(user_id: str, title: str, category: int, raw_markdown: str, db_path: str = DEFAULT_DB) -> int:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO documents (author_id, title, category_id, body_markdown)
        VALUES (?, ?, ?, ?)
    """, (user_id, title, category, raw_markdown))

    conn.commit()
    doc_id = cursor.lastrowid
    conn.close()

    return doc_id
```

---

## Чек-лист правил безопасности и чистоты кода:

1. **Всегда кортеж в аргументах:** если параметр один, пиши `(user_id,)` с запятой. Без запятой `(user_id)` интерпретируется как простое выражение в скобках, а не кортеж!
2. **Всегда `conn.commit()`:** для любых запросов на изменение (`INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE`). Иначе данные останутся только в оперативной памяти и исчезнут после завершения процесса.
3. **Всегда `conn.close()`:** не оставляй дескрипторы открытыми, чтобы SQLite не выдавала ошибку `database is locked`.
4. **Никакой конкатенации:** никогда не пиши `f"SELECT ... WHERE id = '{uid}'"`. Только плейсхолдеры `?`.
