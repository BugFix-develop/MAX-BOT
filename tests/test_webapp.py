"""
Unit and integration tests for MAX Mini App (Web App) server and bot menu handlers.
"""

import json
import os
import tempfile
import threading
import urllib.request
import urllib.parse
import pytest

from storage.db import init_db
from webapp_server import create_server
from bot.handlers import handle_app, handle_close, handle_message, handle_start, USER_SESSIONS
from config import WEBAPP_URL


class MockClient:
    def __init__(self):
        self.sent_messages = []
        self.sent_keyboards = []
        self.app_buttons = []

    def send_message(self, user_id=None, chat_id=None, text="", attachments=None, **kwargs):
        self.sent_messages.append({"user_id": user_id, "chat_id": chat_id, "text": text, "attachments": attachments})
        return {"status": "ok"}

    def send_keyboard(self, user_id=None, chat_id=None, text="", buttons=None, **kwargs):
        self.sent_keyboards.append({"user_id": user_id, "chat_id": chat_id, "text": text, "buttons": buttons})
        return {"status": "ok"}

    def send_app_button(self, user_id=None, chat_id=None, text="", webapp_url="", button_text=""):
        self.app_buttons.append({"user_id": user_id, "chat_id": chat_id, "text": text, "url": webapp_url, "btn_text": button_text})
        return {"status": "ok"}


@pytest.fixture(scope="module")
def webapp_test_server():
    """Starts a real ThreadingHTTPServer on an ephemeral port for testing."""
    temp_dir = tempfile.mkdtemp()
    test_db = os.path.join(temp_dir, "test_webapp.db")
    init_db(test_db)

    # Port 0 selects any free port automatically
    server = create_server(host="127.0.0.1", port=0, db_path=test_db)
    assigned_port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{assigned_port}"
    yield {"base_url": base_url, "db_path": test_db}

    server.shutdown()
    server.server_close()


def test_webapp_health(webapp_test_server):
    url = f"{webapp_test_server['base_url']}/health"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data.get("status") == "ok"
        assert data.get("service") == "max-math-webapp"


def test_webapp_static_index(webapp_test_server):
    url = f"{webapp_test_server['base_url']}/"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        content = response.read().decode("utf-8")
        assert "Тренажёр" in content
        assert "max-web-app.js" in content
        assert "closeAppBtn" in content


def test_webapp_api_task(webapp_test_server):
    url = f"{webapp_test_server['base_url']}/api/task?user_id=test_student_1&template_id=1"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert data.get("status") == "ok"
        assert "task_id" in data
        assert "question" in data
        assert "expected_answer" in data
        assert data.get("template_id") == 1


def test_webapp_api_check_and_stats(webapp_test_server):
    base_url = webapp_test_server["base_url"]
    user_id = "test_student_stats_1"

    # 1. Fetch task
    with urllib.request.urlopen(f"{base_url}/api/task?user_id={user_id}&template_id=1") as resp:
        task_data = json.loads(resp.read().decode("utf-8"))

    task_id = task_data["task_id"]
    expected = task_data["expected_answer"]

    # 2. Check correct answer via POST /api/check
    check_payload = json.dumps({
        "user_id": user_id,
        "task_id": task_id,
        "user_answer": expected,
        "expected_answer": expected
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/check",
        data=check_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        check_res = json.loads(resp.read().decode("utf-8"))
        assert check_res.get("is_correct") is True
        assert check_res.get("status") == "ok"

    # 3. Check stats via GET /api/stats
    with urllib.request.urlopen(f"{base_url}/api/stats?user_id={user_id}") as resp:
        assert resp.status == 200
        stats = json.loads(resp.read().decode("utf-8"))
        assert stats.get("status") == "ok"
        assert stats.get("total_solved") >= 1
        assert stats.get("correct_answers") >= 1


def test_webapp_api_lesson_and_variant(webapp_test_server):
    base_url = webapp_test_server["base_url"]

    # POST /api/lesson
    payload = json.dumps({
        "topic": "ФСУ (7 класс)",
        "grade": 7,
        "author_id": "test_teacher"
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/api/lesson",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "ok"
        assert "markdown" in data
        assert "Методический план урока" in data["markdown"]

    # GET /api/lesson?variant=15
    with urllib.request.urlopen(f"{base_url}/api/lesson?variant=15") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "variant_15" in data
        assert "15 задач" in data["variant_15"]


def test_webapp_api_templates(webapp_test_server):
    url = f"{webapp_test_server['base_url']}/api/templates"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        templates = json.loads(response.read().decode("utf-8"))
        assert isinstance(templates, list)
        assert len(templates) >= 10


def test_handle_app_command():
    client = MockClient()
    user_id = "user_app_test"
    handle_app(user_id=user_id, client=client, chat_id=123)

    assert len(client.app_buttons) == 1
    call = client.app_buttons[0]
    assert call["user_id"] == user_id
    assert call["chat_id"] == 123
    assert "Интерактивный «Тренажёр»" in call["text"]
    assert "http" in call["url"]


def test_handle_close_command():
    client = MockClient()
    user_id = "user_close_test"
    USER_SESSIONS[user_id] = {"state": "SOLVING_TASK", "chat_id": 456}

    handle_close(user_id=user_id, client=client, chat_id=456)

    assert USER_SESSIONS[user_id]["state"] == "MAIN_MENU"
    assert len(client.sent_keyboards) == 1
    call = client.sent_keyboards[0]
    assert "Тренажёр закрыт" in call["text"]
    assert any(btn["payload"] == "/app" for row in call["buttons"] for btn in row)


def test_handle_message_app_routing():
    client = MockClient()
    user_id = "user_router_test"

    # Test /app
    handle_message(user_id=user_id, text="/app", client=client, chat_id=789)
    assert len(client.app_buttons) == 1

    # Test /close
    handle_message(user_id=user_id, text="/close", client=client, chat_id=789)
    assert len(client.sent_keyboards) == 1


def test_handle_start_includes_webapp_invitation():
    client = MockClient()
    user_id = "user_start_test"

    handle_start(user_id=user_id, client=client, chat_id=999)
    assert len(client.app_buttons) == 1
    call = client.app_buttons[0]
    assert "Интерактивный тренажёр" in call["text"]
    assert "/app" in call["text"]
    assert "скрепкой" in call["text"]

