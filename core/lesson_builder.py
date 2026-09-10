from dataclasses import dataclass
import datetime
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


def _get_task(template_id: int) -> LessonTask:
    """Получает задачу из генератора Даниса или из автономного каталога-заглушки."""
    if generator_instance is not None:
        try:
            raw = generator_instance.generate_task(template_id)
            return LessonTask(
                template_id=template_id,
                question=raw.get("question", raw.get("task_text", "")),
                expected_answer=raw.get("answer", raw.get("expected_answer", "")),
                hint=raw.get("hint", "")
            )
        except Exception:
            pass

    q, a, h = FALLBACK_CATALOG.get(
        template_id,
        (f"Задача по шаблону #{template_id}", "ответ", "подсказка")
    )
    return LessonTask(template_id=template_id, question=q, expected_answer=a, hint=h)


def build_lesson_plan(
    topic: str = "ФСУ (7 класс)",
    grade: int = 7,
    author_id: str = "system",
    save_to_db: bool = True,
    db_path: str = "math_bot.db",
) -> str:
    #Генерирует 45-минутный методический план урока :
    
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
    warmup_text = "### ⚡ Этап 1. Устная фронтальная разминка (5 минут)\n"
    warmup_text += "*Форма работы:* устный экспресс-опрос класса. Ученики отвечают с места без записи в тетрадь.\n\n"
    for i, t in enumerate(warmup_tasks, 1):
        warmup_text += f"{i}. Вычислите устно: `{t.question}`\n"
    warmup_text += "\n> 💡 **Методический акцент:** Обратите внимание класса на быстроту счета с помощью формул без умножения столбиком."
    sections.append(warmup_text)

    # Теория
    theory_text = textwrap.dedent("""
    ### 📖 Этап 2. Теоретическая актуализация (15 минут)
    *Повторение ключевых формул и разбор типичных ошибок 7 класса:*

    1. **Разность квадратов:**
       $$(a - b)(a + b) = a^2 - b^2$$
       *Типичная ошибка:* Путаница с $(a - b)^2$. Напоминаем: в разности квадратов **нет** удвоенного произведения!

    2. **Квадрат суммы и квадрат разности:**
       $$(a + b)^2 = a^2 + 2ab + b^2$$
       $$(a - b)^2 = a^2 - 2ab + b^2$$
       *Критическая точка:* При возведении выражения с коэффициентом $(3x)^2$ в квадрат возводится и коэффициент, и переменная: $(3x)^2 = 9x^2$, а не $3x^2$!

    3. **Ловушка знака «минус»:**
       $$(-a - b)^2 = (-(a + b))^2 = (a + b)^2$$
       Минусы под четной степенью взаимно уничтожаются!
    """).strip()
    sections.append(theory_text)

    # работа у доски 
    board_text = "### ✍️ Этап 3. Закрепление материала у доски (20 минут)\n"
    board_text += "*Форма работы:* решение задач у доски с подробным комментированием каждого шага.\n\n"
    for i, t in enumerate(board_tasks, 1):
        board_text += f"**Задание {i}** (Шаблон #{t.template_id}):\n"
        board_text += f"> Раскройте скобки: `{t.question}`\n\n"
    sections.append(board_text.strip())

    # Задачи повышенной сложности
    hard_text = "### 🌟 Задачи повышенной сложности (Дифференцированная работа)\n"
    hard_text += "*Для успевающих учеников и индивидуальной работы:*\n\n"
    for i, t in enumerate(hard_tasks, 1):
        hard_text += f"{i}. Преобразуйте выражение (Шаблон #{t.template_id}): `{t.question}` *(Подсказка: {t.hint})*\n"
    sections.append(hard_text)

    # ДЗ и итоги
    summary_text = textwrap.dedent(f"""
    ### 🎯 Этап 4. Подведение итогов и Домашнее задание (5 минут)
    **Вопросы для экспресс-рефлексии:**
    - В чем главное отличие между «разностью квадратов» и «квадратом разности»?
    - Чему равно удвоенное произведение в выражении $(3x - 4y)^2$?

    **Домашнее задание (на следующий урок):**
    1. `{hw_tasks[0].question}`
    2. `{hw_tasks[1].question}`
    3. `{hw_tasks[2].question}`
    """).strip()
    sections.append(summary_text)

    # Шпаргалка для учителя 
    answers_text = "### 🔑 Шпаргалка для учителя (Ответы ко всем задачам урока)\n"
    answers_text += "| Этап | № | Условие | Эталонный ответ |\n"
    answers_text += "| :--- | :---: | :--- | :--- |\n"

    num = 1
    for t in warmup_tasks:
        answers_text += f"| Разминка | #{num} | `{t.question}` | `{t.expected_answer}` |\n"
        num += 1
    for t in board_tasks:
        answers_text += f"| У доски | #{num} | `{t.question}` | `{t.expected_answer}` |\n"
        num += 1
    for t in hard_tasks:
        answers_text += f"| Со звездочкой | #{num} | `{t.question}` | `{t.expected_answer}` |\n"
        num += 1
    for t in hw_tasks:
        answers_text += f"| Домашнее задание | #{num} | `{t.question}` | `{t.expected_answer}` |\n"
        num += 1

    sections.append(answers_text.strip())

    full_markdown = "\n\n---\n\n".join(sections)

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