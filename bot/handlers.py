
import random
from core.lesson_builder import build_lesson_plan
from core.validator import check_answer
from storage.db import (
    DB_NAME,
    get_or_create_user,
    get_user_statistics,
    is_task_already_solved,
    save_task_issue,
    save_task_result,
)

# Безопасный импорт генератора задач Даниса
try:
    from engine.generator import TaskGenerator
    generator_instance = TaskGenerator()
except (ImportError, Exception):
    generator_instance = None

# Хранилище сессий пользователей в памяти (FSM)
# { user_id: { "state": "SOLVING_TASK", "task_id": 1, "expected_answer": "x^2-4" } }
USER_SESSIONS: dict[str, dict] = {}

# Автономный каталог задач для режима решения, если генератор недоступен
FALLBACK_TASKS = [
    (1, "Раскройте скобки: (x - 3)(x + 3)", "x^2-9"),
    (2, "Раскройте скобки: (5 - x)(5 + x)", "25-x^2"),
    (3, "Раскройте скобки: (2x - 4)(2x + 4)", "4x^2-16"),
    (8, "Раскройте скобки: (x + 4)^2", "x^2+8x+16"),
    (10, "Раскройте скобки: (2x + 3)^2", "4x^2+12x+9"),
    (14, "Раскройте скобки: (x - 5)^2", "x^2-10x+25"),
    (16, "Раскройте скобки: (2x - 3y)^2", "4x^2-12xy+9y^2"),
    (20, "Раскройте скобки: (-x - 4)^2", "x^2+8x+16"),
]


def handle_start(user_id: str, client, db_path: str = DB_NAME) -> None:
    """
    Обработчик команды /start:
    - Регистрирует ученика в базе данных (если новый)
    - Сбрасывает текущее состояние в главное меню
    - Отправляет приветствие и знакомит с возможностями бота
    """
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU"}
    get_or_create_user(max_user_id=user_id, role="student", db_path=db_path)

    welcome_text = (
        "👋 Привет! Я чат-бот «Образовательные решения» по математике для 7 класса.\n\n"
        "🎯 Я помогу тебе легко освоить и отработать **Формулы сокращенного умножения (ФСУ)**:\n"
        "• Разность квадратов\n"
        "• Квадрат суммы и квадрат разности\n"
        "• Кубы и сложные выражения\n\n"
        "Доступные команды:\n"
        "• /task — получить математическую задачу\n"
        "• /stats — посмотреть свою статистику\n"
        "• /lesson — составить 45-минутный план урока\n"
        "• /help — правила ввода формул и степеней"
    )

    client.send_message(user_id=user_id, text=welcome_text)


def handle_help(user_id: str, client, *args, **kwargs) -> None:
    """
    Обработчик команды /help:
    - Отправляет ученику памятку по правилам ввода математических ответов
    - Объясняет, как писать степени, знаки умножения и переменные
    """
    help_text = (
        "📖 **Памятка: Как правильно вводить ответы**\n\n"
        "✨ Наш валидатор очень умный и понимает разные способы записи:\n\n"
        "1. **Степени (квадраты и кубы):**\n"
        "   • Стандартный вид: `x^2`, `y^3`\n"
        "   • В стиле Python: `x**2`, `x**3`\n"
        "   • Словами: `x во 2`, `x в квадрате`, `x в кубе`\n\n"
        "2. **Коэффициенты и умножение:**\n"
        "   • Можно писать слитно: `4x`, `12xy`\n"
        "   • Можно со знаком умножения: `4*x`, `12*x*y`\n\n"
        "3. **Раскладка клавиатуры:**\n"
        "   • Не переживай, если случайно напечатал русскую букву «х» вместо английской «x» — бот поймет оба варианта!\n\n"
        "💡 **Пример правильного ответа:**\n"
        "`x^2 + 4x + 4` или `x**2 + 4*x + 4`"
    )

    client.send_message(user_id=user_id, text=help_text)


def handle_stats(user_id: str, client, db_path: str = DB_NAME) -> None:
    """
    Обработчик команды /stats (кнопка «Моя статистика»):
    - Получает из БД статистику ученика (всего решено, верных, % точности)
    - Отправляет наглядный отчет с результатами
    """
    stats = get_user_statistics(user_id=user_id, db_path=db_path)

    total = stats.get("total_solved", 0)
    correct = stats.get("correct_answers", 0)
    accuracy = stats.get("accuracy_percent", 0.0)

    if total == 0:
        stats_text = (
            "📊 **Твоя статистика успеваемости**\n\n"
            "Ты еще не решил ни одной задачи!\n"
            "Самое время нажать /task и сделать первый шаг!"
        )
    else:
        stats_text = (
            "📊 **Твоя статистика успеваемости**\n\n"
            f"• Всего решено задач: `{total}`\n"
            f"• Верных ответов: `{correct}`\n"
            f"• Процент успешности: `{accuracy}%`\n\n"
        )
        if accuracy >= 80.0:
            stats_text += "🔥 **Великолепный результат!** Ты отлично знаешь формулы!"
        elif accuracy >= 50.0:
            stats_text += "👍 **Хороший темп!** Ещё немного практики, и будет 100%!"
        else:
            stats_text += "💡 **Рекомендуется повторить формулы.** Напиши /help для подсказки!"

    client.send_message(user_id=user_id, text=stats_text)


def handle_lesson_plan(user_id: str, client, topic: str = "ФСУ (7 класс)", db_path: str = DB_NAME) -> None:
    """
    Обработчик команды /lesson (кнопка «План урока»):
    - Генерирует 45-минутный конспект урока через core.lesson_builder
    - Сохраняет план в базу данных
    - Отправляет конспект в формате Markdown учителю
    """
    client.send_message(user_id=user_id, text="⏳ Формирую методический план урока на 45 минут...")
    plan_markdown = build_lesson_plan(
        topic=topic,
        grade=7,
        author_id=user_id,
        save_to_db=True,
        db_path=db_path
    )
    client.send_message(user_id=user_id, text=plan_markdown)


def handle_task(user_id: str, client, template_id: int = None, db_path: str = DB_NAME) -> None:
    """
    Обработчик команды /task (кнопка «🎯 Решать задачи»):
    - Генерирует уникальную задачу (проверяет отсутствие повторов через is_task_already_solved)
    - Фиксирует выдачу в БД через save_task_issue
    - Переводит пользователя в состояние FSM: SOLVING_TASK
    - Отправляет условие задачи ученику
    """
    t_id, question, answer = None, None, None

    if generator_instance is not None:
        try:
            checker = lambda uid, qtext: is_task_already_solved(uid, qtext, db_path=db_path)
            task_obj = generator_instance.get_unique_task(user_id=user_id, template_id=template_id, checker=checker)
            t_id = task_obj.template_id
            question = task_obj.question_text
            answer = task_obj.reference_answer
        except Exception:
            pass

    if question is None:
        # Автономный выбор из каталога:
        chosen = random.choice(FALLBACK_TASKS)
        t_id, question, answer = chosen[0], chosen[1], chosen[2]

    # 1. Запись выдачи задачи в SQLite:
    task_db_id = save_task_issue(
        user_id=user_id,
        template_id=t_id,
        task_text=question,
        expected_answer=answer,
        db_path=db_path
    )

    # 2. Фиксация FSM-состояния в сессии:
    USER_SESSIONS[user_id] = {
        "state": "SOLVING_TASK",
        "task_id": task_db_id,
        "template_id": t_id,
        "expected_answer": answer,
        "question": question
    }

    # 3. Отправка задания ученику:
    task_message = (
        f"🎯 **Задание (Шаблон #{t_id}):**\n"
        f"> {question}\n\n"
        f"✍️ Напиши свой ответ в чат (или /help для справки):"
    )
    client.send_message(user_id=user_id, text=task_message)


def handle_answer(user_id: str, text: str, client, db_path: str = DB_NAME) -> bool:
    """
    Обработка ответа ученика в состоянии решения задачи (SOLVING_TASK):
    - Вызывает валидатор check_answer()
    - Сохраняет результат в SQLite через save_task_result()
    - Сбрасывает состояние в MAIN_MENU
    - Отправляет обратную связь ученику
    """
    session = USER_SESSIONS.get(user_id)
    if not session or session.get("state") != "SOLVING_TASK":
        return False

    task_id = session["task_id"]
    expected_answer = session["expected_answer"]

    # 1. Валидация ответа ученика:
    is_correct, feedback = check_answer(user_input=text, expected_answer=expected_answer)

    # 2. Фиксация результата в базе данных:
    save_task_result(task_id=task_id, user_answer=text, is_correct=is_correct, db_path=db_path)

    # 3. Сброс состояния:
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU"}

    # 4. Формирование ответа:
    if is_correct:
        response = f"🎉 **{feedback}**\n\nЧтобы получить следующую задачу, напиши /task"
    else:
        response = f"❌ **{feedback}**\n\nПопробуй решить другую задачу: /task или напиши /help"

    client.send_message(user_id=user_id, text=response)
    return True


def handle_cancel(user_id: str, client, *args, **kwargs) -> None:
    """
    Обработчик отмены текущего действия (/cancel, 'отмена'):
    - Сбрасывает состояние сессии в MAIN_MENU
    - Отправляет подтверждение ученику
    """
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU"}
    client.send_message(
        user_id=user_id,
        text="👌 Действие отменено. Ты вернулся в главное меню.\n"
             "Напиши /task, чтобы получить новую задачу, или /stats для просмотра прогресса."
    )


# Словарь сопоставления команд и обработчиков (Dispatcher Registry)
COMMAND_HANDLERS = {
    "/start": handle_start,
    "/help": handle_help,
    "/stats": handle_stats,
    "📊 моя статистика": handle_stats,
    "/lesson": handle_lesson_plan,
    "📚 план урока": handle_lesson_plan,
    "план урока": handle_lesson_plan,
    "/task": handle_task,
    "🎯 решать задачи": handle_task,
    "решать задачи": handle_task,
    "задача": handle_task,
    "/cancel": handle_cancel,
    "отмена": handle_cancel,
}


def handle_message(user_id: str, text: str, client, db_path: str = DB_NAME) -> None:
    """
    Главный диспетчер текстовых сообщений:
    - Если пользователь в состоянии решения задачи (SOLVING_TASK), передает ввод в handle_answer
    - Иначе маршрутизирует команды /start, /help, /stats, /lesson, /task
    - Отвечает подсказкой на неизвестный текст
    """
    if not text:
        return

    clean_text = text.strip()
    command = clean_text.lower()

    # 1. Проверка системных команд (команды начинающиеся со слеша обрабатываются в первую очередь)
    if command in COMMAND_HANDLERS:
        handler = COMMAND_HANDLERS[command]
        handler(user_id=user_id, client=client, db_path=db_path)
        return

    # 2. Если пользователь в режиме решения задачи — проверяем его математический ответ:
    session = USER_SESSIONS.get(user_id, {})
    if session.get("state") == "SOLVING_TASK":
        handled = handle_answer(user_id=user_id, text=clean_text, client=client, db_path=db_path)
        if handled:
            return

    # 3. Текст не распознан как команда и пользователь не решает задачу:
    fallback_text = (
        "🤖 Я пока понимаю следующие команды:\n"
        "• /task — получить математическую задачу\n"
        "• /stats — твоя статистика успеваемости\n"
        "• /lesson — составить 45-минутный план урока\n"
        "• /help — правила ввода формул и степеней\n"
        "• /start — главное меню\n\n"
        "Напиши /task, чтобы начать решать задачи!"
    )
    client.send_message(user_id=user_id, text=fallback_text)
