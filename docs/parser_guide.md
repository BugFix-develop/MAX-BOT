# Руководство: Работа с файлами (`with open`) и `json` в Python

> **Цель руководства:** Освоить безопасное чтение файлов через контекстный менеджер `with`, работу с форматом JSON в Python и валидацию данных на практических примерах.

---

## 1. Контекстный менеджер `with open(...)`

### Проблема старого подхода:
В старых учебниках можно встретить:
```python
f = open("data.json", "r")
content = f.read()
f.close()
```
**Почему так писать плохо:** Если во время чтения `f.read()` произойдет ошибка (файл поврежден, не хватает памяти), строчка `f.close()` **не выполнится**. Файл останется заблокирован в операционной системе (утечка дескрипторов).

### Современный подход через `with` (паттерн RAII):
Конструкция `with` гарантирует, что файл **всегда закроется**, даже если внутри произойдет фатальная ошибка:

```python
with open(filepath, "r", encoding="utf-8") as f:
    # Здесь работаем с файлом f
    content = f.read()
# При выходе из блока with файл автоматически закрывается!
```

* `"r"` — режим чтения (read-only).
* `encoding="utf-8"` — обязательный параметр для корректной работы с русскими буквами на любой операционной системе (macOS, Windows, Linux).
* `as f` — псевдоним открытого файлового объекта (переменная `f`).

---

## 2. Модуль `json` в Python

Формат JSON напрямую отображается на стандартные типы Python:

| В файле JSON | В коде Python |
| :--- | :--- |
| `[...]` (массив) | `list` (список) |
| `{...}` (объект) | `dict` (словарь) |
| `"текст"` | `str` (строка) |
| `123` / `3.14` | `int` / `float` (числа) |
| `true` / `false` | `True` / `False` (булевы) |
| `null` | `None` (ничто) |

### 4 главные функции модуля `json` (запомни правило "буквы S"):

1. **Без буквы `s` — работают с файлом напрямую:**
   * `json.load(file)` — читает JSON **из файла**.
   * `json.dump(data, file)` — записывает Python-объект **в файл**.

2. **С буквой `s` (String) — работают со строкой в памяти:**
   * `json.loads(string)` — преобразует JSON-**строку** в Python-объект.
   * `json.dumps(data)` — превращает Python-объект в JSON-**строку**.

---

## 3. Как читать JSON из файла (Практический шаблон)

```python
import json
from pathlib import Path

def read_my_json(filepath: Path):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data
```

---

## 4. Валидация данных и защита от ошибок

Хороший код не просто считывает файл, а проверяет, что данные не повреждены.

### 1. Проверка существования файла:
```python
if not filepath.exists():
    raise FileNotFoundError(f"Файл шаблонов не найден по пути: {filepath}")
```

### 2. Проверка типов (`isinstance`):
```python
# Убеждаемся, что в JSON лежит именно список [ ... ], а не один словарь { ... }
if not isinstance(data, list):
    raise ValueError("Ожидался список шаблонов (list), но получен другой тип данных")
```

### 3. Проверка количества элементов:
```python
if len(data) != 30:
    raise ValueError(f"Ожидалось ровно 30 шаблонов, но загружено {len(data)}")
```

### 4. Проверка обязательных полей у каждого элемента:
```python
REQUIRED_FIELDS = {"id", "question", "answer"}

for index, item in enumerate(data, start=1):
    for field in REQUIRED_FIELDS:
        if field not in item:
            raise ValueError(f"Шаблон №{index} не содержит обязательного поля '{field}'")
```

---

## 5. Параллельный пример: Парсер каталога квестов в игре

Посмотрим, как выглядит законченный модуль парсера на стороннем примере:

```python
"""
Пример: storage/quest_parser.py
Чтение и валидация квестов игры из JSON.
"""

import json
from pathlib import Path

def load_quests(filepath: Path) -> list[dict]:
    """
    Загружает список игровых квестов из JSON-файла.
    
    :param filepath: Путь к файлу quests.json
    :return: Список словарей с квестами
    :raises FileNotFoundError: Если файл не существует
    :raises ValueError: Если структура данных нарушена
    """
    # 1. Проверяем наличие файла на диске
    if not filepath.exists():
        raise FileNotFoundError(f"Файл квестов не найден: {filepath}")

    # 2. Безопасно открываем и парсим JSON
    with open(filepath, "r", encoding="utf-8") as file:
        try:
            quests = json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка синтаксиса JSON в файле {filepath}: {e}")

    # 3. Валидируем данные
    if not isinstance(quests, list):
        raise ValueError("Файл должен содержать список квестов [ ... ]")

    if len(quests) == 0:
        raise ValueError("Список квестов пуст!")

    # 4. Проверяем ключи первого уровня
    for quest in quests:
        if "id" not in quest or "title" not in quest:
            raise ValueError(f"Квест {quest} не содержит обязательных полей id/title")

    return quests
```

---

## 6. Чеклист для твоего файла `storage/parser.py`

В файле [storage/parser.py](file:///Users/danis/MAX-BOT/storage/parser.py) напиши функцию:

```python
def load_templates(filepath: Path = TEMPLATES_PATH) -> list[dict]:
    ...
```

Она должна:
1. [x] Импортировать `json`, `Path` и `TEMPLATES_PATH` из твоего `config.py`.
2. [x] Проверять, что файл существует (`filepath.exists()`).
3. [x] Читать JSON через `with open(..., encoding="utf-8") as f:` и `json.load(f)`.
4. [x] Проверять, что загрузился `list` и его длина ровно 30 (`len(data) == 30`).
5. [x] Возвращать полученный список.
