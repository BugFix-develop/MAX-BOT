# Чат-бот «Образовательные решения» (MAX Messenger)

Интеллектуальный помощник для школьников 7 класса и учителей математики.
Генерирует задачи по 30 формулам сокращенного умножения (ФСУ), автоматически проверяет ответы с учетом опечаток и вариативности ввода, а также формирует методические 45-минутные планы уроков.

---

## 📋 Требования к окружению

* **Python:** версия `3.10` или выше
* **СУБД:** SQLite3 (встроена в Python, установка отдельного сервера не требуется)
* **ОС:** Linux / macOS / Windows

---

## 🚀 Быстрый старт и запуск

### 1. Клонирование репозитория
```bash
git clone git@github.com:BugFix-develop/MAX-BOT.git
cd MAX-BOT
```

### 2. Создание и активация виртуального окружения (`venv`)

* **Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

* **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения
Создайте файл `.env` в корне проекта (по умолчанию берётся база данных `math_bot.db`):
```env
MAX_BOT_TOKEN=your_bot_token_here
DB_PATH=math_bot.db
```

---

## 🧪 Запуск проверок и тестов

### Запуск Unit-тестов валидатора ответов
```bash
python3 -m unittest -v tests/test_math.py
```

### Проверка загрузки 30 математических шаблонов
```bash
python3 -c "from storage.parser import load_templates; print(f'Загружено шаблонов: {len(load_templates())}')"
```

### Инициализация таблиц базы данных
```bash
python3 -c "from storage.db import init_db; init_db(); print('База данных успешно инициализирована!')"
```

---

## 📂 Структура проекта

```text
├── bot/               # Логика взаимодействия с API мессенджера MAX
├── core/              # Бизнес-логика ядра:
│   ├── models.py      # Модели данных (User, Task, TaskResult, LessonPlan)
│   ├── validator.py   # Нормализация и проверка ответов учеников
│   └── lesson_builder.py # Генератор методических планов уроков (45 мин)
├── data/              # Шаблоны задач (templates.json)
├── docs/              # Технические руководства и гайды по модулям
├── engine/            # Генератор задач и формул
├── storage/           # Слой хранения данных:
│   ├── db.py          # SQLite база данных (пользователи, история, конспекты)
│   └── parser.py      # Валидация и загрузка шаблонов формул
├── tests/             # Модульные тесты (unittest)
├── config.py          # Конфигурация путей и токенов
└── requirements.txt   # Зависимости проекта
```
