"""
HTTP Client for MAX Messenger Bot API.
Platform API URL: https://platform-api2.max.ru
Handles long polling, sending messages, keyboards, and event dispatching.
"""

import socket
import logging
import time
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# DNS resolver patch: filter out dead IP 155.212.204.149 that fails SSL handshakes
_orig_getaddrinfo = socket.getaddrinfo


def _patched_getaddrinfo(host, port, *args, **kwargs):
    res = _orig_getaddrinfo(host, port, *args, **kwargs)
    if host == "platform-api2.max.ru":
        filtered = [r for r in res if r[4][0] != "155.212.204.149"]
        if filtered:
            return filtered
    return res


socket.getaddrinfo = _patched_getaddrinfo


class MAXApiError(Exception):
    """Custom exception for MAX API errors."""
    pass


class MAXClient:
    """
    Client for interacting with MAX Messenger Bot API.
    """

    def __init__(self, token: str, base_url: str = "https://platform-api2.max.ru", timeout: int = 30):
        self.token = token.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.user_chats: dict[str, int] = {}

    def _get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": self.token,
            "User-Agent": "MAX-MathBot/1.0"
        }

    def _reset_session(self):
        """Close and recreate session to avoid corrupted SSL connection reuse."""
        try:
            self.session.close()
        except Exception:
            pass
        self.session = requests.Session()

    def get_me(self) -> dict:
        """
        Get bot profile information.
        Endpoint: GET /me
        Header: Authorization: <token>
        """
        url = f"{self.base_url}/me"
        params = {"access_token": self.token}
        for attempt in range(3):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=(5, 10),
                    verify=False
                )
                if response.status_code == 200:
                    return response.json()
                raise MAXApiError(f"HTTP {response.status_code}: {response.text}")
            except requests.exceptions.RequestException as e:
                self._reset_session()
                if attempt == 2:
                    raise MAXApiError(f"Network error in get_me: {e}")
                time.sleep(1)

    def set_my_commands(self, commands: list[dict]) -> bool:
        """
        Register commands menu in MAX Messenger.
        Endpoint: PATCH /me/commands
        Body: {"commands": [{"name": "task", "description": "..."}]}
        """
        url = f"{self.base_url}/me/commands"
        params = {"access_token": self.token}
        payload = {"commands": commands}

        for attempt in range(3):
            try:
                response = self.session.patch(
                    url,
                    params=params,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=(5, 10),
                    verify=False
                )
                if response.status_code == 200:
                    logger.info("✅ Команды бота успешно зарегистрированы в меню MAX (%d шт.)", len(commands))
                    return True
                logger.error("set_my_commands failed (%d): %s", response.status_code, response.text)
                return False
            except requests.exceptions.RequestException as e:
                logger.warning("Сетевая ошибка при регистрации команд (попытка %d/3): %s", attempt + 1, e)
                self._reset_session()
                time.sleep(1)

        return False

    def get_updates(self, marker: int | None = None, limit: int = 50, timeout: int = 25) -> tuple[list[dict], int | None]:
        """
        Long Polling method to fetch incoming events/updates.
        Endpoint: GET /updates
        Header: Authorization: <token>
        Params: marker, limit, timeout
        Returns:
            (updates_list, next_marker)
        """
        url = f"{self.base_url}/updates"
        params = {
            "access_token": self.token,
            "limit": limit,
            "timeout": timeout
        }
        if marker is not None:
            params["marker"] = marker

        for attempt in range(3):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._get_headers(),
                    timeout=(5, timeout + 5),
                    verify=False
                )
                if response.status_code != 200:
                    logger.error("get_updates failed with status %d: %s", response.status_code, response.text)
                    return [], marker
                data = response.json()
                updates = data.get("updates", [])
                next_marker = data.get("marker", marker)
                return updates, next_marker
            except requests.exceptions.Timeout:
                # Long polling timeout without new messages is normal
                return [], marker
            except requests.exceptions.RequestException as e:
                logger.warning("Сетевое предупреждение в get_updates (попытка %d/3): %s", attempt + 1, e)
                self._reset_session()
                time.sleep(1)

        return [], marker

    def send_message(self, user_id: str | int | None = None, chat_id: str | int | None = None, text: str = "", attachments: list | None = None, format: str = "markdown") -> dict | None:
        """
        Send a message to user or chat.
        Endpoint: POST /messages
        Header: Authorization: <token>
        Query: user_id or chat_id
        Body: {"text": "...", "format": "markdown", "attachments": [...]}
        """
        url = f"{self.base_url}/messages"
        params = {"access_token": self.token}

        # Auto-resolve chat_id if user_id is known
        if chat_id is None and user_id is not None and str(user_id) in self.user_chats:
            chat_id = self.user_chats[str(user_id)]

        if chat_id is not None:
            params["chat_id"] = chat_id
        elif user_id is not None:
            try:
                params["user_id"] = int(user_id)
            except (ValueError, TypeError):
                params["user_id"] = user_id
        else:
            raise ValueError("Either user_id or chat_id must be provided.")

        payload = {"text": text}
        if format:
            payload["format"] = format
        if attachments:
            payload["attachments"] = attachments

        for attempt in range(3):
            try:
                response = self.session.post(
                    url,
                    params=params,
                    json=payload,
                    headers=self._get_headers(),
                    timeout=(5, 15),
                    verify=False
                )
                if response.status_code in (200, 201):
                    logger.info("✅ Сообщение успешно отправлено (chat_id=%s, user_id=%s)", chat_id, user_id)
                    return response.json()
                logger.error("send_message failed (%d): %s", response.status_code, response.text)
                return None
            except requests.exceptions.RequestException as e:
                logger.warning("Сетевая ошибка при отправке сообщения (попытка %d/3): %s", attempt + 1, e)
                self._reset_session()
                time.sleep(0.5)

        return None

    def send_keyboard(self, user_id: str | int | None = None, chat_id: str | int | None = None, text: str = "", buttons: list[list[dict]] | None = None) -> dict | None:
        """
        Send an inline keyboard markup.
        Supports button types: 'callback', 'link', 'open_app'.
        """
        attachments = []
        if buttons:
            attachments.append({
                "type": "inline_keyboard",
                "payload": {
                    "buttons": buttons
                }
            })
        return self.send_message(user_id=user_id, chat_id=chat_id, text=text, attachments=attachments)

    def send_app_button(self, user_id: str | int | None = None, chat_id: str | int | None = None, text: str = "", webapp_url: str = "", button_text: str = "🚀 Открыть тренажёр") -> dict | None:
        """
        Send an invitation message with an interactive WebApp launch button and quick controls.
        """
        buttons = [
            [
                {"type": "link", "text": button_text, "url": webapp_url}
            ],
            [
                {"type": "callback", "text": "🎯 Решать в чате", "payload": "/task"},
                {"type": "callback", "text": "📊 Статистика", "payload": "/stats"}
            ],
            [
                {"type": "callback", "text": "❌ Закрыть тренажёр", "payload": "/close"}
            ]
        ]
        return self.send_keyboard(user_id=user_id, chat_id=chat_id, text=text, buttons=buttons)



    def extract_message_event(self, update: dict) -> tuple[str, str, str | int | None] | None:
        """
        Extract (user_id, text, chat_id) from an update dictionary.
        Handles message_created, bot_started, bot_added, user_added, dialog_cleared, and message_callback events.
        """
        update_type = update.get("update_type")
        chat_id = None
        user_id = None
        text = None

        if update_type == "message_created":
            message = update.get("message") or {}
            sender = message.get("sender") or {}
            if sender.get("is_bot"):
                return None
            user_id = str(sender.get("user_id") or "")
            body = message.get("body") or {}
            text = body.get("text", "")
            recipient = message.get("recipient") or {}
            chat_id = recipient.get("chat_id")

        elif update_type in ("bot_started", "bot_added", "user_added", "dialog_cleared", "chat_created"):
            user = update.get("user") or update.get("sender") or {}
            if isinstance(user, dict):
                user_id = str(user.get("user_id") or user.get("id") or "")
            elif isinstance(user, (int, str)):
                user_id = str(user)
            chat_id = update.get("chat_id") or (update.get("recipient") or {}).get("chat_id")
            text = "/start"

        elif update_type == "message_callback":
            callback = update.get("callback") or {}
            user = callback.get("user") or {}
            user_id = str(user.get("user_id") or "")
            text = callback.get("payload", "")
            message = update.get("message") or {}
            recipient = message.get("recipient") or {}
            chat_id = recipient.get("chat_id") or update.get("chat_id")

        if user_id and chat_id:
            self.user_chats[str(user_id)] = chat_id

        if user_id and text is not None:
            return user_id, text, chat_id

        return None
