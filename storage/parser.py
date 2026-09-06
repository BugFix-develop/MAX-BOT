import json
from pathlib import Path

from config import TEMPLATES_PATH


def load_templates(filepath: Path = TEMPLATES_PATH) -> list[dict]:
    if not filepath.exists():
        raise FileNotFoundError(f"Файл заданий не найден: {filepath}")

    with open(filepath, "r", encoding="utf-8") as file:
        try:
            tasks = json.load(file)
        except json.JSONDecodeError as e:
            raise ValueError(f"Ошибка синтаксиса JSON в файле {filepath}: {e}")

    if not isinstance(tasks, list):
        raise ValueError("Файл должен содержать список заданий [ ... ]")

    if len(tasks) != 30:
        raise ValueError(f"Ожидалось 30 шаблонов, но загружено {len(tasks)}")

    required_fields = {"id", "question", "answer"}
    for task in tasks:
        for field in required_fields:
            if field not in task:
                raise ValueError(
                    f"Шаблон id={task.get('id', '?')} не содержит обязательного поля '{field}'"
                )

    return tasks
