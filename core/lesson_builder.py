from dataclasses import dataclass
import datetime
import re
import textwrap


try:
    from engine.generator import TaskGenerator
    generator_instance = TaskGenerator()
except (ImportError, Exception):
    generator_instance = None



try:
    from storage.db import save_lesson_plan
    DB_AVAILABLE = True
except (ImportError, Exception):
    DB_AVAILABLE = False


@dataclass
class LessonTask:
    template_id: int
    question: str
    expected_answer: str
    hint: str = ""


# Каталог-заглушка на случай, если engine.generator еще не готов
FALLBACK_CATALOG = {
    1: ("(x - 6)(x + 6)", "x^2-36", "Разность квадратов: (a - b)(a + b) = a^2 - b^2"),
    3: ("(3x - 5)(3x + 5)", "9x^2-25", "Возведите коэффициент при x в квадрат: (3x)^2 = 9x^2"),
    5: ("(4x - 3y)(4x + 3y)", "16x^2-9y^2", "Две переменные с коэффициентами"),
    8: ("(x + 7)^2", "x^2+14x+49", "Квадрат суммы: (a + b)^2 = a^2 + 2ab + b^2"),
    10: ("(2x + 5)^2", "4x^2+20x+25", "Удвоенное произведение: 2 * 2x * 5 = 20x"),
    14: ("(x - 8)^2", "x^2-16x+64", "Квадрат разности: (a - b)^2 = a^2 - 2ab + b^2"),
    16: ("(3x - 4y)^2", "9x^2-24xy+16y^2", "Две переменные: удвоенное произведение со знаком минус"),
    20: ("(-x - 6)^2", "x^2+12x+36", "Ловушка знаков: (-a - b)^2 = (a + b)^2 = a^2 + 2ab + b^2!"),
    23: ("(2x + 1)^3", "8x^3+12x^2+6x+1", "Куб суммы: a^3 + 3a^2b + 3ab^2 + b^3"),
}


def _clean_question(text: str) -> str:
    """Очищает условие от типовых префиксов ('Раскройте скобки: ', и т.д.) для краткости."""
    prefixes = [
        "Раскройте скобки:",
        "Разложите на множители:",
        "Представьте в виде многочлена:",
        "Выполните умножение:",
        "Упростите выражение:",
    ]
    cleaned = text.strip()
    for p in prefixes:
        if cleaned.lower().startswith(p.lower()):
            cleaned = cleaned[len(p):].strip()
    return cleaned


def _format_math(expr: str) -> str:
    """Делает формулу красивой для отображения: степени в виде ², ³, нормализация пробелов."""
    if not expr:
        return expr
    text = expr.strip()
    # Заменяем степени на юникод
    text = text.replace("^2", "²").replace("**2", "²")
    text = text.replace("^3", "³").replace("**3", "³")
    # Нормализуем пробелы вокруг + и - (но не в начале отрицательного числа)
    text = re.sub(r'(?<![+\-*/^(\s])\s*([+\-])\s*', r' \1 ', text)
    # Убираем двойные пробелы
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _get_task(template_id: int) -> LessonTask:
    """Получает задачу из генератора Даниса или из автономного каталога-заглушки."""
    if generator_instance is not None:
        try:
            raw = generator_instance.generate_task(template_id)
            if hasattr(raw, "question_text"):
                q = raw.question_text
                a = raw.reference_answer
                h = getattr(raw, "hint", "")
            elif isinstance(raw, dict):
                q = raw.get("question", raw.get("task_text", ""))
                a = raw.get("answer", raw.get("expected_answer", ""))
                h = raw.get("hint", "")
            else:
                q, a, h = str(raw), "", ""
            return LessonTask(
                template_id=template_id,
                question=_clean_question(q),
                expected_answer=a,
                hint=h
            )
        except Exception:
            pass

    q, a, h = FALLBACK_CATALOG.get(
        template_id,
        (f"Задача по шаблону #{template_id}", "ответ", "подсказка")
    )
    return LessonTask(template_id=template_id, question=_clean_question(q), expected_answer=a, hint=h)


def build_lesson_plan(
    topic: str = "ФСУ (7 класс)",
    grade: int = 7,
    author_id: str = "system",
    save_to_db: bool = True,
    db_path: str = "math_bot.db",
) -> str:
    # Генерирует 45-минутный методический план урока:
    
    warmup_tasks = [_get_task(1), _get_task(8), _get_task(14)]
    board_tasks = [_get_task(3), _get_task(5), _get_task(10), _get_task(16)]
    hard_tasks = [_get_task(20), _get_task(23)]
    hw_tasks = [_get_task(1), _get_task(8), _get_task(10)]

    sections = []

    today_str = datetime.date.today().strftime("%d.%m.%Y")
    header = textwrap.dedent(f"""
    # 📋 Методический план урока: {topic}
    **Класс:** {grade} | **Продолжительность:** 45 минут | **Дата:** {today_str}
    **Цель урока:** Сформировать и закрепить навык практического применения формул сокращенного умножения (разность квадратов, квадрат суммы и разности) при преобразовании алгебраических выражений.

    ### ⏱ Тайминг урока (хронометраж 45 минут):
    1. **Организационный момент и устная разминка** — 5 минут
    2. **Актуализация знаний и теоретический блок** — 15 минут
    3. **Закрепление навыков у доски и в тетрадях** — 20 минут
    4. **Подведение итогов и инструктаж по домашнему заданию** — 5 минут
    *(Резерв: задачи повышенной сложности для сильных учеников)*
    """).strip()
    sections.append(header)

    # Разминка
    warmup_text = "### ⚡ Этап 1. Устная фронтальная разминка (5 минут)\n\n"
    warmup_text += "*Форма работы:* устный экспресс-опрос класса (без записи в тетрадь).\n\n"
    for i, t in enumerate(warmup_tasks, 1):
        q_fmt = _format_math(t.question)
        warmup_text += f"{i}. Вычислите устно: `{q_fmt}`\n"
    warmup_text += "\n💡 *Методический акцент: обратите внимание на быстроту счета с помощью формул.*"
    sections.append(warmup_text)

    # Теория
    theory_text = textwrap.dedent("""
    ### 📖 Этап 2. Теоретическая актуализация (15 минут)
    *Повторение ключевых формул и разбор типичных ошибок 7 класса:*

    1. **Разность квадратов:**
       `(a - b)(a + b) = a² - b²`
       *Типичная ошибка:* Путаница с `(a - b)²`. Напоминаем: в разности квадратов **нет** удвоенного произведения!

    2. **Квадрат суммы и квадрат разности:**
       `(a + b)² = a² + 2ab + b²`
       `(a - b)² = a² - 2ab + b²`
       *Критическая точка:* При возведении выражения с коэффициентом в квадрат возводится и коэффициент, и переменная: `(3x)² = 9x²`, а не `3x²`!

    3. **Ловушка знака «минус»:**
       `(-a - b)² = (-(a + b))² = (a + b)²`
       Минусы под четной степенью взаимно уничтожаются!
    """).strip()
    sections.append(theory_text)

    # Работа у доски 
    board_text = "### ✍️ Этап 3. Закрепление материала у доски (20 минут)\n\n"
    board_text += "*Форма работы:* решение задач у доски с подробным комментированием каждого шага.\n\n"
    for i, t in enumerate(board_tasks, 1):
        q_fmt = _format_math(t.question)
        board_text += f"**Задание {i}** (Шаблон #{t.template_id}):\n"
        board_text += f"👉 Раскройте скобки: `{q_fmt}`\n\n"
    sections.append(board_text.strip())

    # Задачи повышенной сложности
    hard_text = "### 🌟 Задачи повышенной сложности (Дифференцированная работа)\n\n"
    hard_text += "*Для успевающих учеников и индивидуальной работы:*\n\n"
    for i, t in enumerate(hard_tasks, 1):
        q_fmt = _format_math(t.question)
        hint_suffix = f" *(Подсказка: {_format_math(t.hint)})*" if t.hint else ""
        hard_text += f"{i}. Преобразуйте выражение: `{q_fmt}`{hint_suffix}\n"
    sections.append(hard_text)

    # ДЗ и итоги
    hw_items = "\n".join([f"{i}. `{_format_math(t.question)}`" for i, t in enumerate(hw_tasks, 1)])
    summary_text = (
        "### 🎯 Этап 4. Подведение итогов и Домашнее задание (5 минут)\n\n"
        "**Вопросы для экспресс-рефлексии:**\n"
        "• В чем главное отличие между «разностью квадратов» и «квадратом разности»?\n"
        "• Чему равно удвоенное произведение в выражении `(3x - 4y)²`?\n\n"
        "**Домашнее задание (на следующий урок):**\n"
        f"{hw_items}"
    )
    sections.append(summary_text)

    # Шпаргалка для учителя (удобный мобильный формат: условие и ответ на отдельных строках)
    answers_text = "### 🔑 Шпаргалка с ответами (для учителя)\n\n"

    answers_text += "⚡ **Разминка:**\n"
    for i, t in enumerate(warmup_tasks, 1):
        q_fmt = _format_math(t.question)
        ans_fmt = _format_math(t.expected_answer)
        answers_text += f"{i}. `{q_fmt}`\n   👉 `{ans_fmt}`\n\n"

    answers_text += "✍️ **У доски:**\n"
    start_num = len(warmup_tasks) + 1
    for i, t in enumerate(board_tasks, start_num):
        q_fmt = _format_math(t.question)
        ans_fmt = _format_math(t.expected_answer)
        answers_text += f"{i}. `{q_fmt}`\n   👉 `{ans_fmt}`\n\n"

    answers_text += "🌟 **Повышенная сложность:**\n"
    start_num += len(board_tasks)
    for i, t in enumerate(hard_tasks, start_num):
        q_fmt = _format_math(t.question)
        ans_fmt = _format_math(t.expected_answer)
        answers_text += f"{i}. `{q_fmt}`\n   👉 `{ans_fmt}`\n\n"

    answers_text += "🏠 **Домашнее задание:**\n"
    start_num += len(hard_tasks)
    for i, t in enumerate(hw_tasks, start_num):
        q_fmt = _format_math(t.question)
        ans_fmt = _format_math(t.expected_answer)
        answers_text += f"{i}. `{q_fmt}`\n   👉 `{ans_fmt}`\n\n"

    sections.append(answers_text.strip())

    full_markdown = "\n\n\n".join(sections)

    # Сохранение плана в базу данных SQLite 
    if save_to_db and DB_AVAILABLE:
        try:
            save_lesson_plan(
                user_id=author_id,
                topic=topic,
                grade=grade,
                markdown=full_markdown,
                db_path=db_path
            )
        except Exception as e:
            print(f"[WARN] Не удалось сохранить план в БД: {e}")

    return full_markdown


def build_teacher_variant(grade: int = 7, count: int = 15) -> str:
    """Генерация подборки из N задач с эталонными ответами для самостоятельной работы или контрольного среза."""
    selected_template_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 21]
    if count != 15:
        selected_template_ids = (selected_template_ids * (count // len(selected_template_ids) + 1))[:count]

    tasks = [_get_task(tid) for tid in selected_template_ids]

    doc = [
        f"# 📝 Вариант для самостоятельной работы: {len(tasks)} задач (ФСУ {grade} класс)\n",
        "**Инструкция:** Раскройте скобки или преобразуйте выражение, используя формулы сокращенного умножения.\n",
        "### 🎯 Задания:\n"
    ]

    for i, t in enumerate(tasks, 1):
        q_fmt = _format_math(t.question)
        doc.append(f"{i}. `{q_fmt}`")

    doc.append("\n────────────────────────\n### 🔑 Ответы для учителя:\n")
    answers_row = []
    for i, t in enumerate(tasks, 1):
        ans_fmt = _format_math(t.expected_answer)
        answers_row.append(f"**{i}:** `{ans_fmt}`")

    # Форматируем ответы блоками по 3 в строке
    for chunk_start in range(0, len(answers_row), 3):
        chunk = answers_row[chunk_start:chunk_start + 3]
        doc.append("  |  ".join(chunk))

    return "\n".join(doc)