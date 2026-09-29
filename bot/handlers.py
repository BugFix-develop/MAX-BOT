
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
from config import WEBAPP_URL, BOT_USERNAME

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


def handle_start(user_id: str, client, chat_id: str | int | None = None, db_path: str = DB_NAME, **kwargs) -> None:
    """
    Обработчик команды /start:
    - Регистрирует ученика в базе данных (если новый) с сохранением chat_id
    - Сбрасывает текущее состояние в главное меню
    - Отправляет приветствие и знакомит с возможностями бота и интерактивного мини-приложения
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU", "chat_id": cid}
    get_or_create_user(max_user_id=user_id, role="student", chat_id=cid, db_path=db_path)

    import config
    app_url = getattr(config, "WEBAPP_URL", f"http://{config.LOCAL_IP}:{config.WEBAPP_PORT}")

    welcome_text = (
        "**Добро пожаловать в Тренажёр по алгебре (7 класс)!**\n"
        "────────────────────────\n"
        "Интерактивный тренажёр поможет вам отрабатывать формулы сокращённого умножения, проверять свои решения и следить за личным прогрессом.\n\n"
        "**Интерактивное приложение:**\n"
        "Откройте визуальный тренажёр с удобной математической клавиатурой, карточками заданий и полным справочником формул.\n\n"
        "**Быстрое меню:**\n"
        "Используйте кнопку `[ / ]` в строке ввода (рядом со скрепкой вложений), чтобы открывать нужные разделы в один клик:\n\n"
        "• `/app` — Открыть тренажёр\n"
        "• `/task` — Решать задачи прямо в чате\n"
        "• `/stats` — Моя статистика и точность\n"
        "• `/help` — Правила записи степеней и ответов\n"
        "• `/lesson` — Методический план урока (для учителей)\n"
        "• `/close` — Завершить сеанс тренажёра\n\n"
        "Нажмите кнопку ниже или отправьте команду **/app**."
    )

    sep = "&" if "?" in app_url else "?"
    user_app_url = f"{app_url}{sep}user_id={user_id}"

    if hasattr(client, "send_app_button"):
        client.send_app_button(user_id=user_id, chat_id=cid, text=welcome_text, webapp_url=user_app_url, button_text="Открыть тренажёр")
    else:
        client.send_message(user_id=user_id, chat_id=cid, text=welcome_text)


def handle_app(user_id: str, client, chat_id: str | int | None = None, *args, **kwargs) -> None:
    """
    Обработчик команды /app (кнопка меню «Открыть тренажёр»):
    - Отправляет карточку с описанием возможностей тренажёра
    - Прикрепляет кнопку прямого открытия приложения (link)
    - Поясняет, как использовать меню команд рядом с ячейкой прикрепления файлов 📎
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU", "chat_id": cid}

    import config
    app_url = getattr(config, "WEBAPP_URL", f"http://{config.LOCAL_IP}:{config.WEBAPP_PORT}")

    app_text = (
        "**Интерактивный «Тренажёр»**\n"
        "────────────────────────\n"
        "Визуальное мини-приложение для тренировки 30 формул сокращённого умножения:\n\n"
        "• Карточки с автоматической проверкой ответов\n"
        "• Экранная клавиатура степеней и переменных (x², x³, +, −)\n"
        "• Аналитика успеваемости и уровни мастерства\n"
        "• Конструктор конспектов уроков на 45 минут для учителей\n"
        "• Полный справочник всех 30 формул курса 7 класса\n\n"
        f"Прямая ссылка для браузера: {app_url}\n\n"
        "Нажмите кнопку ниже, чтобы запустить приложение, или начните решать прямо в диалоге."
    )

    # Передаем user_id в URL веб-приложения для синхронизации единой статистики с ботом (/stats)
    sep = "&" if "?" in app_url else "?"
    user_app_url = f"{app_url}{sep}user_id={user_id}"

    if hasattr(client, "send_app_button"):
        client.send_app_button(user_id=user_id, chat_id=cid, text=app_text, webapp_url=user_app_url, button_text="Открыть тренажёр")
    else:
        buttons = [
            [{"type": "link", "text": "Открыть тренажёр", "url": app_url}],
            [{"type": "callback", "text": "Решать в чате", "payload": "/task"}, {"type": "callback", "text": "Моя статистика", "payload": "/stats"}],
            [{"type": "callback", "text": "Закрыть тренажёр", "payload": "/close"}]
        ]
        if hasattr(client, "send_keyboard"):
            client.send_keyboard(user_id=user_id, chat_id=cid, text=app_text, buttons=buttons)
        else:
            client.send_message(user_id=user_id, chat_id=cid, text=f"{app_text}\n\nСсылка: {app_url}")


def handle_close(user_id: str, client, chat_id: str | int | None = None, *args, **kwargs) -> None:
    """
    Обработчик команды /close (кнопка меню «Закрыть тренажёр»):
    - Сбрасывает активную сессию тренажёра
    - Подтверждает закрытие приложения и предлагает продолжить работу в чате
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU", "chat_id": cid}

    close_text = (
        "**Тренажёр закрыт**\n"
        "────────────────────────\n"
        "Вы вернулись в стандартный режим диалога.\n"
        "Вы можете продолжать обучение в чате:\n\n"
        "• Напишите **/task** для получения задачи\n"
        "• Напишите **/app** для повторного запуска приложения\n"
        "• Или выберите действие в меню рядом со скрепкой 📎"
    )

    buttons = [
        [{"type": "callback", "text": "Открыть тренажёр", "payload": "/app"}],
        [{"type": "callback", "text": "Решать в чате", "payload": "/task"}]
    ]
    if hasattr(client, "send_keyboard"):
        client.send_keyboard(user_id=user_id, chat_id=cid, text=close_text, buttons=buttons)
    else:
        client.send_message(user_id=user_id, chat_id=cid, text=close_text)



def handle_help(user_id: str, client, chat_id: str | int | None = None, *args, **kwargs) -> None:
    """
    Обработчик команды /help:
    - Отправляет ученику памятку по правилам ввода математических ответов
    - Объясняет, как писать степени, знаки умножения и переменные
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
    help_text = (
        "📖 **Памятка: Как вводить ответы**\n"
        "────────────────────────\n"
        "Бот автоматически поймёт твой ввод в любом удобном виде:\n\n"
        "1️⃣ **Степени (квадраты и кубы):**\n"
        "• Через символ `^`: `x^2`, `y^3`, `a^2`\n"
        "• В стиле Python: `x**2`, `x**3`\n"
        "• Словами: `x во 2`, `x в квадрате`, `x в кубе`\n\n"
        "2️⃣ **Коэффициенты и умножение:**\n"
        "• Слитно: `4x`, `12xy`, `9a^2`\n"
        "• Со знаком `*`: `4*x`, `12*x*y`\n\n"
        "3️⃣ **Раскладка клавиатуры:**\n"
        "• Случайно напечатал русскую «х» вместо английской `x`? Бот поймёт оба варианта!\n\n"
        "💡 **Пример решения:**\n"
        "Задача: `(x + 2)^2`\n"
        "Твой ответ: `x^2 + 4x + 4`\n"
        "────────────────────────\n"
        "Напиши **/task**, чтобы проверить свои силы!"
    )

    client.send_message(user_id=user_id, chat_id=cid, text=help_text)


def handle_stats(user_id: str, client, chat_id: str | int | None = None, db_path: str = DB_NAME, **kwargs) -> None:
    """
    Обработчик команды /stats (кнопка «Моя статистика»):
    - Получает из БД статистику ученика (всего решено, верных, % точности)
    - Отправляет наглядный отчет с результатами
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
    stats = get_user_statistics(user_id=user_id, db_path=db_path)

    total = stats.get("total_solved", 0)
    correct = stats.get("correct_answers", 0)
    accuracy = stats.get("accuracy_percent", 0.0)

    if total == 0:
        stats_text = (
            "📊 **Твоя статистика успеваемости**\n"
            "────────────────────────\n"
            "Ты пока не решил ни одной задачи.\n\n"
            "Самое время начать! Напиши **/task**, чтобы сделать первый шаг! 🚀"
        )
    else:
        # Прогресс-бар из 10 делений
        filled = max(0, min(10, int(round(accuracy / 10))))
        bar = "🟩" * filled + "⬜" * (10 - filled)

        if accuracy >= 80.0:
            badge = "🏆 **Уровень:** Эксперт ФСУ\nОтличный результат, формулы отскакивают от зубов!"
        elif accuracy >= 50.0:
            badge = "🥈 **Уровень:** Практик\nХороший темп! Ещё немного практики, и будет 100%!"
        else:
            badge = "🌱 **Уровень:** Ученик\nНужно немного повторить теорию. Напиши `/help` за подсказкой!"

        stats_text = (
            "📊 **Твоя статистика успеваемости**\n"
            "────────────────────────\n"
            f"🎯 Решено задач: `{total}`\n"
            f"✅ Верных ответов: `{correct}`\n"
            f"📈 Успешность: `{accuracy:.1f}%`\n"
            f"Прогресс: {bar}\n"
            "────────────────────────\n"
            f"{badge}\n\n"
            "👉 Напиши **/task**, чтобы продолжить тренировку"
        )

    client.send_message(user_id=user_id, chat_id=cid, text=stats_text)


def handle_lesson_plan(user_id: str, client, topic: str = "ФСУ (7 класс)", chat_id: str | int | None = None, db_path: str = DB_NAME, **kwargs) -> None:
    """
    Обработчик команды /lesson (кнопка «План урока»):
    - Генерирует 45-минутный конспект урока через core.lesson_builder
    - Сохраняет план в базу данных
    - Отправляет конспект в формате Markdown учителю
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
    client.send_message(user_id=user_id, chat_id=cid, text="⏳ **Формирую методический план урока на 45 минут...**")
    plan_markdown = build_lesson_plan(
        topic=topic,
        grade=7,
        author_id=user_id,
        save_to_db=True,
        db_path=db_path
    )
    client.send_message(user_id=user_id, chat_id=cid, text=plan_markdown)


def handle_task(user_id: str, client, template_id: int = None, chat_id: str | int | None = None, db_path: str = DB_NAME, **kwargs) -> None:
    """
    Обработчик команды /task (кнопка «🎯 Решать задачи»):
    - Генерирует уникальную задачу (проверяет отсутствие повторов через is_task_already_solved)
    - Фиксирует выдачу в БД через save_task_issue
    - Переводит пользователя в состояние FSM: SOLVING_TASK
    - Отправляет условие задачи ученику
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
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
        "question": question,
        "chat_id": cid
    }

    # 3. Отправка задания ученику:
    task_message = (
        f"🎯 **Задание #{t_id}**\n"
        f"────────────────────────\n"
        f"📝 **{question}**\n"
        f"────────────────────────\n"
        f"✍️ Напиши свой ответ сообщением в чат.\n\n"
        f"💡 *Справка по вводу:* `/help`  |  ❌ *Отмена:* `/cancel`"
    )
    client.send_message(user_id=user_id, chat_id=cid, text=task_message)


def handle_answer(user_id: str, text: str, client, chat_id: str | int | None = None, db_path: str = DB_NAME, **kwargs) -> bool:
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
    cid = chat_id or session.get("chat_id")

    # 1. Валидация ответа ученика:
    is_correct, feedback = check_answer(user_input=text, expected_answer=expected_answer)

    # 2. Фиксация результата в базе данных:
    save_task_result(task_id=task_id, user_answer=text, is_correct=is_correct, db_path=db_path)

    # 3. Сброс состояния:
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU", "chat_id": cid}

    # 4. Формирование ответа:
    if is_correct:
        response = (
            "🎉 **Отлично! Ответ верный!**\n"
            "────────────────────────\n"
            f"✅ Твой ответ: `{text.strip()}`\n\n"
            "👉 Напиши **/task**, чтобы решить следующее задание\n"
            "👉 Напиши **/stats**, чтобы посмотреть свой прогресс"
        )
    else:
        response = (
            "❌ **Увы, ответ не совпал.**\n"
            "────────────────────────\n"
            f"Твой ответ: `{text.strip()}`\n"
            f"Правильный ответ: `{expected_answer}`\n\n"
            "Не расстраивайся, математика любит упорство! 💪\n\n"
            "👉 Напиши **/task**, чтобы попробовать снова\n"
            "👉 Напиши **/help**, чтобы посмотреть правила записи"
        )

    client.send_message(user_id=user_id, chat_id=cid, text=response)
    return True


def handle_cancel(user_id: str, client, chat_id: str | int | None = None, *args, **kwargs) -> None:
    """
    Обработчик отмены текущего действия (/cancel, 'отмена'):
    - Сбрасывает состояние сессии в MAIN_MENU
    - Отправляет подтверждение ученику
    """
    cid = chat_id or USER_SESSIONS.get(user_id, {}).get("chat_id")
    USER_SESSIONS[user_id] = {"state": "MAIN_MENU", "chat_id": cid}
    cancel_text = (
        "👌 **Действие отменено**\n"
        "────────────────────────\n"
        "Ты вернулся в главное меню.\n\n"
        "👉 `/task` — получить новую задачу\n"
        "👉 `/stats` — посмотреть свой прогресс"
    )
    client.send_message(user_id=user_id, chat_id=cid, text=cancel_text)


# Словарь сопоставления команд и обработчиков (Dispatcher Registry)
COMMAND_HANDLERS = {
    "/start": handle_start,
    "start": handle_start,
    "старт": handle_start,
    "/старт": handle_start,
    "начать": handle_start,
    "/начать": handle_start,
    "запуск": handle_start,
    "/запуск": handle_start,
    "запустить": handle_start,
    "/запустить": handle_start,
    "начало": handle_start,
    "/начало": handle_start,
    "привет": handle_start,
    "здравствуйте": handle_start,
    "хай": handle_start,
    "меню": handle_start,
    "/меню": handle_start,
    "/help": handle_help,
    "help": handle_help,
    "помощь": handle_help,
    "/помощь": handle_help,
    "справка": handle_help,
    "/справка": handle_help,
    "/stats": handle_stats,
    "stats": handle_stats,
    "статистика": handle_stats,
    "/статистика": handle_stats,
    "📊 моя статистика": handle_stats,
    "/lesson": handle_lesson_plan,
    "lesson": handle_lesson_plan,
    "📚 план урока": handle_lesson_plan,
    "план урока": handle_lesson_plan,
    "/урок": handle_lesson_plan,
    "урок": handle_lesson_plan,
    "/task": handle_task,
    "task": handle_task,
    "🎯 решать задачи": handle_task,
    "решать задачи": handle_task,
    "задача": handle_task,
    "/задача": handle_task,
    "/app": handle_app,
    "app": handle_app,
    "/мини": handle_app,
    "мини": handle_app,
    "/мини-приложение": handle_app,
    "мини-приложение": handle_app,
    "/приложение": handle_app,
    "приложение": handle_app,
    "🚀 открыть мини-приложение": handle_app,
    "открыть мини-приложение": handle_app,
    "🚀 открыть тренажёр": handle_app,
    "открыть тренажёр": handle_app,
    "🚀 открыть тренажер": handle_app,
    "открыть тренажер": handle_app,
    "тренажёр": handle_app,
    "тренажер": handle_app,
    "/тренажёр": handle_app,
    "/тренажер": handle_app,
    "открыть": handle_app,
    "/открыть": handle_app,
    "🚀 открыть": handle_app,
    "🚀 открыть тренажёр фсу": handle_app,
    "открыть тренажёр фсу": handle_app,
    "открыть тренажер фсу": handle_app,
    "/close": handle_close,
    "close": handle_close,
    "/закрыть": handle_close,
    "закрыть": handle_close,
    "закрыть приложение": handle_close,
    "/закрыть_приложение": handle_close,
    "❌ закрыть приложение": handle_close,
    "закрыть тренажер": handle_close,
    "закрыть тренажёр": handle_close,
    "❌ закрыть тренажёр": handle_close,
    "❌ закрыть тренажер": handle_close,
    "❌ закрыть": handle_close,
    "/cancel": handle_cancel,
    "cancel": handle_cancel,
    "отмена": handle_cancel,
    "/отмена": handle_cancel,
}


def handle_message(user_id: str, text: str, client, chat_id: str | int | None = None, db_path: str = DB_NAME) -> None:
    """
    Главный диспетчер текстовых сообщений:
    - Сохраняет chat_id пользователя в БД и FSM
    - Если сообщение пустое или событие старта без текста -> автоматически запускает /start
    - Если пользователь в состоянии решения задачи (SOLVING_TASK), передает ввод в handle_answer
    - Иначе маршрутизирует команды /app, /close, /start, /help, /stats, /lesson, /task
    - Отвечает подсказкой на неизвестный текст
    """
    if chat_id:
        if user_id in USER_SESSIONS:
            USER_SESSIONS[user_id]["chat_id"] = chat_id
        get_or_create_user(max_user_id=user_id, chat_id=chat_id, db_path=db_path)

    if not text:
        handle_start(user_id=user_id, client=client, chat_id=chat_id, db_path=db_path)
        return

    clean_text = text.strip()
    command = clean_text.lower()

    # 1. Проверка системных команд (команды начинающиеся со слеша обрабатываются в первую очередь)
    if command in COMMAND_HANDLERS:
        handler = COMMAND_HANDLERS[command]
        handler(user_id=user_id, client=client, chat_id=chat_id, db_path=db_path)
        return

    # 2. Если пользователь в режиме решения задачи — проверяем его математический ответ:
    session = USER_SESSIONS.get(user_id, {})
    if session.get("state") == "SOLVING_TASK":
        handled = handle_answer(user_id=user_id, text=clean_text, client=client, chat_id=chat_id, db_path=db_path)
        if handled:
            return

    # 3. Текст не распознан как команда и пользователь не решает задачу:
    cid = chat_id or session.get("chat_id")
    fallback_text = (
        "🤖 **Команда не распознана**\n"
        "────────────────────────\n"
        "Я чат-бот тренажёра по математике (7 класс).\n\n"
        "⚡ **Доступные команды (меню рядом со скрепкой 📎):**\n"
        "• `/app` — 🚀 открыть тренажёр\n"
        "• `/close` — ❌ закрыть тренажёр\n"
        "• `/task` — получить математическую задачу в чате\n"
        "• `/stats` — твоя статистика успеваемости\n"
        "• `/help` — правила ввода формул и степеней\n"
        "• `/lesson` — составить 45-минутный план урока\n"
        "• `/start` — главное меню и перезапуск\n\n"
        "Напиши **/app**, чтобы открыть тренажёр, или **/task**, чтобы решать в чате! 🎯"
    )
    client.send_message(user_id=user_id, chat_id=cid, text=fallback_text)


