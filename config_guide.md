# Руководство: Конфигурация в Python (`pathlib`, `os`, `python-dotenv`)

> **Цель руководства:** Разобрать концепцию управления конфигурацией и переменными окружения в Python, освоить синтаксис библиотек `pathlib`, `os` и `python-dotenv`, чтобы ты мог уверенно написать чистый и надежный `config.py`.

---

## 1. Зачем нужен отдельный `config.py`?

В коммерческой разработке действует принцип **12-Factor App**: настройки и секреты (токены, пароли к БД, пути) отделяются от исходного кода.

### Проблемы хардкода:
* Если ты запишешь токен бота прямо в коде: `TOKEN = "12345:ABCDEF"`, при первом же `git push` твой токен утечет в публичный репозиторий.
* Если прописать жесткий путь вроде `C:\Users\Danis\project\data\templates.json`, код упадет у любого коллеги (например, у Муслима на Linux или macOS).

### Решение:
1. **Секреты** хранятся в файле `.env` (который **никогда не коммитится** в Git).
2. **Пути** вычисляются динамически относительно корня проекта с помощью `pathlib.Path`.
3. **`config.py`** собирает все это в одном месте и экспортирует удобные константы.

---

## 2. Модуль `pathlib` (Современная работа с файловой системой)

В старом Python использовали `os.path.join()`, `os.path.dirname()`. В современном Python стандартом стал объектно-ориентированный модуль `pathlib`.

### Ментальная модель (если знаком с C++):
В C++17 появился `std::filesystem::path`. В Python `pathlib.Path` работает точно так же: путь — это не просто строка, а умный объект с методами и перегруженными операторами.

### Основной синтаксис:

```python
from pathlib import Path

# __file__ — встроенная переменная Python, содержащая путь к текущему исполняемому файлу
current_file = Path(__file__)
print(current_file)  
# Выведет, например: /Users/danis/MAX-BOT/config.py

# .resolve() превращает путь в абсолютный канонический
abs_file = current_file.resolve()

# .parent возвращает директорию, в которой лежит файл (на уровень выше)
base_dir = abs_file.parent
print(base_dir)  
# Выведет: /Users/danis/MAX-BOT
```

### Главная фишка: перегрузка оператора `/`
Вместо склеивания строк `base_dir + "/" + "data"` в `pathlib` перегружен оператор деления `/`:

```python
data_dir = base_dir / "data"
# Автоматически поставит правильный слэш: / на Linux/macOS или \ на Windows!

file_path = data_dir / "templates.json"
print(file_path)
# /Users/danis/MAX-BOT/data/templates.json
```

### Полезные методы `Path`:
* `path.exists()` — проверяет, существует ли файл или папка (`bool`).
* `path.is_file()` / `path.is_dir()` — проверка типа объекта.
* `str(path)` — приведение объекта пути к обычной строке (если сторонней библиотеке требуется именно `str`).

---

## 3. Переменные окружения и `os.getenv`

Переменные окружения (Environment Variables) — это глобальные пары «ключ-значение», хранящиеся в операционной системе процесса.

### Синтаксис:

```python
import os

# Способ 1: через словарь os.environ (ОПАСНЫЙ)
token = os.environ["BOT_TOKEN"]  
# Если переменной нет в системе -> упадет с ошибкой KeyError!

# Способ 2: через метод os.getenv() (РЕКОМЕНДУЕМЫЙ)
token = os.getenv("BOT_TOKEN")  
# Если переменной нет -> вернет None, программа не упадет.

# Способ 3: os.getenv() со значением по умолчанию (дефолт)
db_name = os.getenv("DB_NAME", "default_store.db")
# Если переменной DB_NAME нет -> вернет "default_store.db"
```

---

## 4. Библиотека `python-dotenv`

При локальной разработке неудобно каждый раз задавать переменные в терминале (`export BOT_TOKEN=...`). Для этого используют файл `.env` в корне проекта.

Библиотека `python-dotenv` считывает файл `.env` и автоматически загружает его содержимое в `os.environ`.

### Как устроен файл `.env`:
```env
# Комментарии начинаются с решетки
MAX_BOT_TOKEN=my_secret_token_12345
DB_PATH=math_bot.db
DEBUG=True
```
> ⚠️ **Важно:** Вокруг знака `=` не должно быть пробелов! Строки без пробелов кавычек не требуют.

### Синтаксис в Python:

```python
from dotenv import load_dotenv

# load_dotenv() ищет файл .env в текущей папке или выше по дереву и загружает переменные
load_dotenv()

# Можно явно указать путь к .env файлу:
# load_dotenv(dotenv_path=BASE_DIR / ".env")
```

---

## 5. Параллельный пример: Конфиг для игрового сервера

Посмотрим, как все три инструмента собираются в один модуль на примере проекта **GameServer**:

```python
"""
Пример: game_config.py
Модуль конфигурации игрового сервера.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 1. Вычисляем ключевые пути проекта
# BASE_DIR — корень проекта (где лежит данный файл)
BASE_DIR = Path(__file__).resolve().parent

# Папки ресурсов и логов
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"

# 2. Загружаем переменные из .env файла
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

# 3. Считываем параметры конфигурации
SERVER_PORT: int = int(os.getenv("SERVER_PORT", 8080))
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev_secret_key_change_in_prod")
DATABASE_URL: str = os.getenv("DATABASE_URL", str(BASE_DIR / "game.db"))
```

### Как это потом используется в других файлах проекта:
```python
# main.py
from game_config import SERVER_PORT, DATABASE_URL, ASSETS_DIR

print(f"Запуск сервера на порту {SERVER_PORT}")
print(f"База данных: {DATABASE_URL}")
```

---

## 6. Зачем нужны `.env` и `.env.example`?

1. **`.env`**:
   * Содержит настоящие токены и пароли.
   * **Обязательно добавлен в `.gitignore`** (проверь: в файле `.gitignore` должна быть строчка `.env`).
   * У каждого разработчика на компьютере свой `.env`.

2. **`.env.example`**:
   * Шаблон (образец) для новых разработчиков.
   * **Коммитится в Git**.
   * Содержит имена всех необходимых переменных, но вместо секретов — подсказки:
     ```env
     MAX_BOT_TOKEN=вставь_сюда_токен_из_личного_кабинета
     DB_PATH=math_bot.db
     ```

---

## 7. Чеклист для твоего `config.py`

Когда будешь писать [config.py](file:///Users/danis/MAX-BOT/config.py), убедись, что:
1. [x] Импортированы `os`, `pathlib.Path`, `load_dotenv`.
2. [x] Рассчитан `BASE_DIR` через `Path(__file__).resolve().parent`.
3. [x] Вызван `load_dotenv()`.
4. [x] Заданы константы путей (`DATA_DIR`, `TEMPLATES_FILE`).
5. [x] Считаны переменные окружения через `os.getenv(...)` с дефолтными значениями (`MAX_BOT_TOKEN`, `DB_PATH`).
