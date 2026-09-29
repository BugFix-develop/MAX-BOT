"""
Main entry point for MAX Math Bot.
Supports:
1. MAX Messenger Bot API mode (Long Polling)
2. Interactive Local CLI mode (--cli) for testing logic and dialogs without network.
"""

import sys
import os
import time
import argparse
import logging
import signal

from config import MAX_BOT_TOKEN, MAX_API_BASE_URL, DB_PATH, WEBAPP_PORT, WEBAPP_HOST, WEBAPP_URL
from storage.db import init_db, get_all_active_users
from bot.handlers import handle_message, handle_start
from bot.max_api import MAXClient, MAXApiError
from webapp_server import start_server_in_thread

try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MAXBot")



class ConsoleClient:
    """Simulated client for local terminal interactions."""
    def send_message(self, user_id: str = None, chat_id: str = None, text: str = "", **kwargs):
        print(f"\n💬 [Бот]:\n{text}\n")


def run_cli_mode(db_path: str = DB_PATH):
    """Interactive console session for local testing."""
    print("=" * 60)
    print("🎓 Локальный режим симулятора бота MAX (CLI Mode)")
    print("=" * 60)
    print("Команды: /start, /task, /stats, /lesson, /help, /cancel")
    print("Для выхода введите 'exit' или 'quit'.\n")

    client = ConsoleClient()
    test_user_id = "local_student_1"

    # Start session
    handle_message(user_id=test_user_id, text="/start", client=client, db_path=db_path)

    while True:
        try:
            user_input = input(f"[{test_user_id}] > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Завершение локальной сессии.")
                break
            handle_message(user_id=test_user_id, text=user_input, client=client, db_path=db_path)
        except (KeyboardInterrupt, EOFError):
            print("\nСессия завершена.")
            break


def run_bot_mode(token: str, base_url: str, db_path: str = DB_PATH, webapp_host: str = WEBAPP_HOST, webapp_port: int = WEBAPP_PORT):
    """Live MAX Messenger Bot polling loop + WebApp Server."""
    logger.info("Инициализация клиента MAX Bot API...")
    logger.info("Базовый URL: %s", base_url)

    # 0. Запуск многопоточного сервера мини-приложения в фоне
    server_instance = None
    try:
        server_instance, _ = start_server_in_thread(host=webapp_host, port=webapp_port, db_path=db_path)
    except Exception as server_err:
        logger.warning("Не удалось запустить локальный сервер мини-приложения: %s", server_err)

    client = MAXClient(token=token, base_url=base_url)

    # 1. Проверка подключения и токена
    try:
        me = client.get_me()
        bot_name = me.get("name") or me.get("username") or "MAX Bot"
        logger.info("✅ Успешное подключение к MAX Messenger! Имя бота: %s", bot_name)

        # Регистрация команд в меню мессенджера MAX для кнопки рядом со скрепкой 📎
        bot_commands = [
            {"name": "app", "description": "🚀 Открыть мини-приложение ФСУ"},
            {"name": "close", "description": "❌ Закрыть мини-приложение"},
            {"name": "task", "description": "Решать задачи по ФСУ (7 класс)"},
            {"name": "stats", "description": "Моя статистика успеваемости"},
            {"name": "help", "description": "Правила ввода степеней и формул"},
            {"name": "lesson", "description": "Методический план урока на 45 минут"},
            {"name": "start", "description": "Главное меню тренажёра"},
            {"name": "cancel", "description": "Отменить текущее действие"}
        ]
        client.set_my_commands(bot_commands)

        # Автоматическая отправка /start при старте бота всем известным активным пользователям
        try:
            active_users = get_all_active_users(db_path=db_path)
            logger.info("Найдено %d записей пользователей в базе данных", len(active_users))
            for u in active_users:
                uid = u.get("max_user_id")
                cid = u.get("chat_id")
                # Фильтруем фиктивные локальные тестовые ID без chat_id
                if not cid or not uid or uid.startswith("test_") or uid.startswith("student_test") or uid.startswith("user_") or uid.startswith("local_"):
                    continue
                logger.info("🚀 Отправка приветствия /start пользователю %s (chat_id=%s) при запуске бота...", uid, cid)
                try:
                    handle_start(user_id=uid, client=client, chat_id=cid, db_path=db_path)
                except Exception as notify_err:
                    logger.warning("Не удалось отправить /start пользователю %s: %s", uid, notify_err)
        except Exception as startup_err:
            logger.warning("Ошибка при авторассылке /start активным пользователям: %s", startup_err)

    except MAXApiError as e:
        logger.error("❌ Ошибка авторизации в MAX API: %s", e)
        print("\n" + "!" * 60)
        print("ВНИМАНИЕ: Не удалось подключиться к серверу MAX с текущим токеном.")
        print("Возможные причины:")
        print("1. Токен недействителен или был отозван.")
        print("2. Организаторы хакатона используют другой адрес API (укажите MAX_API_BASE_URL в .env).")
        print("Для локальной проверки работы бота используйте: python3 main.py --cli")
        print("!" * 60 + "\n")
        return
    except Exception as e:
        logger.error("❌ Не удалось соединиться с сервером MAX: %s", e)
        return

    # 2. Флаг остановки при Ctrl+C
    running = True

    def signal_handler(sig, frame):
        nonlocal running
        logger.info("Получен сигнал завершения. Остановка бота...")
        running = False
        if server_instance:
            try:
                server_instance.shutdown()
            except Exception:
                pass

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    marker = None
    logger.info("🚀 Бот запущен в режиме Long Polling. Ожидание сообщений...")

    while running:
        try:
            updates, marker = client.get_updates(marker=marker, timeout=25)
            for update in updates:
                event = client.extract_message_event(update)
                if event:
                    user_id, text, chat_id = event
                    logger.info("📨 Входящее событие от [%s] (chat_id=%s): %s", user_id, chat_id, text)
                    try:
                        handle_message(user_id=user_id, text=text, client=client, chat_id=chat_id, db_path=db_path)
                    except Exception as handler_err:
                        logger.exception("Ошибка при обработке сообщения от [%s]: %s", user_id, handler_err)
        except Exception as poll_err:
            if running:
                logger.error("Ошибка в цикле Long Polling: %s", poll_err)
                time.sleep(2)

    logger.info("Бот корректно остановлен.")


def main():
    parser = argparse.ArgumentParser(description="Запуск бота «Образовательные решения» для MAX")
    parser.add_argument("--cli", action="store_true", help="Запустить в интерактивном локальном режиме консоли")
    parser.add_argument("--url", type=str, default=MAX_API_BASE_URL, help="Переопределить URL API мессенджера MAX")
    parser.add_argument("--token", type=str, default=MAX_BOT_TOKEN, help="Переопределить токен бота")
    parser.add_argument("--webapp-host", type=str, default=WEBAPP_HOST, help="Хост сервера мини-приложения")
    parser.add_argument("--webapp-port", type=int, default=WEBAPP_PORT, help="Порт сервера мини-приложения")
    args = parser.parse_args()

    # Инициализация схемы базы данных
    logger.info("Инициализация базы данных: %s", DB_PATH)
    init_db(DB_PATH)

    if args.cli:
        # В CLI режиме также запускаем фоновый сервер мини-приложения для удобства локального тестирования в браузере
        try:
            start_server_in_thread(host=args.webapp_host, port=args.webapp_port, db_path=DB_PATH)
            print(f"📱 Мини-приложение доступно локально в браузере: http://localhost:{args.webapp_port}/\n")
        except Exception as e:
            logger.warning("Не удалось поднять сервер мини-приложения в CLI режиме: %s", e)
        run_cli_mode(db_path=DB_PATH)
    else:
        token = args.token.strip()
        if not token or token == "your_bot_token_here":
            logger.warning("Токен MAX_BOT_TOKEN не задан в .env!")
            print("Токен не найден. Запуск локального режима симуляции...")
            run_cli_mode(db_path=DB_PATH)
        else:
            run_bot_mode(
                token=token,
                base_url=args.url,
                db_path=DB_PATH,
                webapp_host=args.webapp_host,
                webapp_port=args.webapp_port
            )


if __name__ == "__main__":
    main()

