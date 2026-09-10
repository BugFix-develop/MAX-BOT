import random
import re
from pathlib import Path
from typing import Callable, Optional

from config import TEMPLATES_PATH
from core.models import Task
from storage.parser import load_templates

try:
    from storage.db import is_task_already_solved
except (ImportError, AttributeError):
    is_task_already_solved = None


class TaskGenerator:
    def __init__(self, templates_path: Path = TEMPLATES_PATH):
        self.templates = load_templates(templates_path)
        self.templates_by_id = {t["id"]: t for t in self.templates}

    def generate_task(self, template_id: Optional[int] = None) -> Task:
        if template_id is None:
            template = random.choice(self.templates)
        else:
            if template_id not in self.templates_by_id:
                raise ValueError(f"Шаблон с ID {template_id} не найден")
            template = self.templates_by_id[template_id]

        context = {}
        for name, rule in template["params"].items():
            if "choices" in rule:
                context[name] = random.choice(rule["choices"])
            else:
                context[name] = random.randint(rule["min"], rule["max"])

        logic_code = re.sub(r',\s*(?=[a-zA-Z_]\w*\s*=)', '\n', template["logic"])
        exec(logic_code, {}, context)

        question_text = template["question"].format(**context)
        reference_answer = template["answer"].format(**context)
        return Task(
            template_id=template["id"],
            question_text=question_text,
            reference_answer=reference_answer
        )

    def get_unique_task(
        self,
        user_id: str,
        template_id: Optional[int] = None,
        max_attempts: int = 10,
        checker: Optional[Callable[[str, str], bool]] = None
    ) -> Task:
        task = None
        check_func = checker if checker is not None else is_task_already_solved

        for _ in range(max_attempts):
            task = self.generate_task(template_id)
            if check_func is None:
                return task
            if not check_func(user_id, task.question_text):
                return task

        return task
