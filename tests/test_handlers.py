"""
Unit tests for bot/handlers.py
"""

import os
import tempfile
import pytest

from bot.handlers import (
    handle_start,
    handle_help,
    handle_stats,
    handle_task,
    handle_answer,
    handle_cancel,
    handle_message,
    USER_SESSIONS,
)
from storage.db import init_db


class DummyClient:
    def __init__(self):
        self.sent_messages = []

    def send_message(self, user_id=None, chat_id=None, text="", attachments=None, format="markdown"):
        self.sent_messages.append({
            "user_id": user_id,
            "chat_id": chat_id,
            "text": text,
            "format": format,
            "attachments": attachments,
        })
        return {"success": True}


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    if os.path.exists(path):
        os.remove(path)


def test_handle_start(temp_db):
    client = DummyClient()
    user_id = "test_user_start"
    handle_start(user_id=user_id, client=client, db_path=temp_db)

    assert len(client.sent_messages) == 1
    msg = client.sent_messages[0]["text"]
    assert "Добро пожаловать в Тренажёр" in msg
    assert "/task" in msg
    assert USER_SESSIONS[user_id]["state"] == "MAIN_MENU"


def test_handle_help():
    client = DummyClient()
    handle_help(user_id="test_user_help", client=client)

    assert len(client.sent_messages) == 1
    msg = client.sent_messages[0]["text"]
    assert "Памятка: Как вводить ответы" in msg
    assert "x^2" in msg


def test_handle_stats_empty(temp_db):
    client = DummyClient()
    handle_stats(user_id="test_user_stats", client=client, db_path=temp_db)

    assert len(client.sent_messages) == 1
    msg = client.sent_messages[0]["text"]
    assert "Твоя статистика успеваемости" in msg
    assert "Ты пока не решил ни одной задачи" in msg


def test_task_flow(temp_db):
    client = DummyClient()
    user_id = "test_user_task"

    # 1. Request task
    handle_task(user_id=user_id, client=client, db_path=temp_db)
    assert len(client.sent_messages) == 1
    task_msg = client.sent_messages[0]["text"]
    assert "Задание #" in task_msg
    assert USER_SESSIONS[user_id]["state"] == "SOLVING_TASK"

    expected = USER_SESSIONS[user_id]["expected_answer"]

    # 2. Answer correctly
    handle_message(user_id=user_id, text=expected, client=client, db_path=temp_db)
    assert len(client.sent_messages) == 2
    ans_msg = client.sent_messages[1]["text"]
    assert "Отлично! Ответ верный!" in ans_msg
    assert USER_SESSIONS[user_id]["state"] == "MAIN_MENU"

    # 3. Check stats after 1 solved
    handle_stats(user_id=user_id, client=client, db_path=temp_db)
    assert len(client.sent_messages) == 3
    stats_msg = client.sent_messages[2]["text"]
    assert "Решено задач: `1`" in stats_msg
    assert "Верных ответов: `1`" in stats_msg


def test_cancel_flow(temp_db):
    client = DummyClient()
    user_id = "test_user_cancel"

    handle_task(user_id=user_id, client=client, db_path=temp_db)
    assert USER_SESSIONS[user_id]["state"] == "SOLVING_TASK"

    handle_cancel(user_id=user_id, client=client, db_path=temp_db)
    assert USER_SESSIONS[user_id]["state"] == "MAIN_MENU"
    assert "Действие отменено" in client.sent_messages[-1]["text"]


def test_task_hint_flow(temp_db):
    client = DummyClient()
    user_id = "test_user_hint"

    # 1. Request task
    handle_task(user_id=user_id, client=client, db_path=temp_db)
    assert USER_SESSIONS[user_id]["state"] == "SOLVING_TASK"
    hint_formula = USER_SESSIONS[user_id]["hint"]
    assert "=" in hint_formula

    # 2. Ask for hint via /hint
    handle_message(user_id=user_id, text="/hint", client=client, db_path=temp_db)
    assert len(client.sent_messages) == 2
    hint_msg = client.sent_messages[1]["text"]
    assert "Формула для решения:" in hint_msg
    assert hint_formula in hint_msg
    assert USER_SESSIONS[user_id]["state"] == "SOLVING_TASK"

    # 3. Answering incorrectly shows formula as well
    handle_message(user_id=user_id, text="неверный_ответ", client=client, db_path=temp_db)
    assert len(client.sent_messages) == 3
    wrong_msg = client.sent_messages[2]["text"]
    assert "Формула решения:" in wrong_msg
    assert hint_formula in wrong_msg



def test_fallback(temp_db):
    client = DummyClient()
    user_id = "test_user_fallback"
    handle_message(user_id=user_id, text="непонятное сообщение", client=client, db_path=temp_db)

    assert len(client.sent_messages) == 1
    assert "Команда не распознана" in client.sent_messages[0]["text"]


def test_lesson_plan_format(temp_db):
    from bot.handlers import handle_lesson_plan
    client = DummyClient()
    user_id = "test_user_teacher"
    handle_lesson_plan(user_id=user_id, client=client, db_path=temp_db)

    assert len(client.sent_messages) == 2
    plan_text = client.sent_messages[1]["text"]
    assert "Методический план урока" in plan_text
    assert "Шпаргалка с ответами (для учителя)" in plan_text
    assert "| Этап |" not in plan_text  # Check that ugly markdown table is removed!
    assert "⚡ **Разминка:**" in plan_text
    assert "🏠 **Домашнее задание:**" in plan_text


def test_chat_id_routing_and_db(temp_db):
    from storage.db import get_or_create_user
    client = DummyClient()
    user_id = "test_user_cid_1"
    chat_id = "chat_998877"

    # 1. Start with chat_id
    handle_message(user_id=user_id, text="/start", client=client, chat_id=chat_id, db_path=temp_db)
    assert len(client.sent_messages) == 1
    assert client.sent_messages[0]["chat_id"] == chat_id
    assert USER_SESSIONS[user_id]["chat_id"] == chat_id

    # 2. Database check
    user_row = get_or_create_user(max_user_id=user_id, db_path=temp_db)
    assert user_row["chat_id"] == chat_id

    # 3. Subsequent command without passing chat_id explicitly should use session chat_id
    handle_message(user_id=user_id, text="/help", client=client, db_path=temp_db)
    assert len(client.sent_messages) == 2
    assert client.sent_messages[1]["chat_id"] == chat_id


def test_auto_start_on_empty_text(temp_db):
    client = DummyClient()
    user_id = "test_user_empty"
    chat_id = "chat_12345"

    handle_message(user_id=user_id, text="", client=client, chat_id=chat_id, db_path=temp_db)
    assert len(client.sent_messages) == 1
    assert "Добро пожаловать в Тренажёр" in client.sent_messages[0]["text"]
    assert client.sent_messages[0]["chat_id"] == chat_id


def test_start_command_aliases(temp_db):
    client = DummyClient()
    aliases = ["старт", "start", "/старт", "начать", "/начать", "запустить", "запуск", "меню", "привет"]
    for idx, cmd in enumerate(aliases):
        uid = f"user_alias_{idx}"
        handle_message(user_id=uid, text=cmd, client=client, db_path=temp_db)
        assert "Добро пожаловать в Тренажёр" in client.sent_messages[-1]["text"]



def test_trainer_command_aliases(temp_db):
    client = DummyClient()
    trainer_aliases = [
        "/app", "app", "тренажер", "тренажёр", "/тренажер", "/тренажёр",
        "открыть тренажер", "открыть тренажёр", "🚀 открыть тренажёр", "🚀 открыть тренажер"
    ]
    for idx, cmd in enumerate(trainer_aliases):
        uid = f"user_trainer_{idx}"
        handle_message(user_id=uid, text=cmd, client=client, db_path=temp_db)
        assert len(client.sent_messages) == idx + 1
        msg = client.sent_messages[-1]["text"]
        assert "Интерактивный «Тренажёр»" in msg


def test_max_bot_started_event():
    from bot.max_api import MAXClient
    client = MAXClient(token="dummy")

    update = {
        "update_type": "bot_started",
        "chat_id": 555666777,
        "user": {
            "user_id": 123456,
            "name": "Test User"
        }
    }

    event = client.extract_message_event(update)
    assert event is not None
    user_id, text, chat_id = event
    assert user_id == "123456"
    assert text == "/start"
    assert chat_id == 555666777

