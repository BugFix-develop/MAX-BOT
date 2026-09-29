"""
Lightweight Multithreaded HTTP Server for MAX Math Mini App.
Serves:
1. Static SPA files from `webapp/` (index.html, assets, styles)
2. REST API for task generation, answer checking, statistics, lesson plans, and formula templates.
Zero external framework dependencies (uses standard library http.server and socketserver).
"""

import os
import json
import logging
import random
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from config import DB_PATH, BASE_DIR, TEMPLATES_PATH
from core.validator import check_answer
from core.lesson_builder import build_lesson_plan, build_teacher_variant
from storage.db import (
    save_task_issue,
    save_task_result,
    get_user_statistics,
    is_task_already_solved,
)

try:
    from engine.generator import TaskGenerator
    generator_instance = TaskGenerator()
except (ImportError, Exception):
    generator_instance = None

logger = logging.getLogger("WebAppServer")

WEBAPP_DIR = BASE_DIR / "webapp"

FALLBACK_TASKS = [
    (1, "Раскройте скобки: (x - 3)(x + 3)", "x^2-9", "Разность квадратов", "(a - b)(a + b) = a² - b²"),
    (2, "Раскройте скобки: (5 - x)(5 + x)", "25-x^2", "Разность квадратов", "(a - b)(a + b) = a² - b²"),
    (3, "Раскройте скобки: (2x - 4)(2x + 4)", "4x^2-16", "Разность квадратов", "(kx - a)(kx + a) = k²x² - a²"),
    (8, "Раскройте скобки: (x + 4)^2", "x^2+8x+16", "Квадрат суммы", "(a + b)² = a² + 2ab + b²"),
    (10, "Раскройте скобки: (2x + 3)^2", "4x^2+12x+9", "Квадрат суммы", "(kx + a)² = k²x² + 2kax + a²"),
    (14, "Раскройте скобки: (x - 5)^2", "x^2-10x+25", "Квадрат разности", "(a - b)² = a² - 2ab + b²"),
    (16, "Раскройте скобки: (2x - 3y)^2", "4x^2-12xy+9y^2", "Квадрат разности", "(kx - my)² = k²x² - 2kmxy + m²y²"),
    (20, "Раскройте скобки: (-x - 4)^2", "x^2+8x+16", "Квадрат суммы", "(-a - b)² = (a + b)²"),
    (21, "Раскройте скобки: (x + 2)^3", "x^3+6x^2+12x+8", "Куб суммы", "(a + b)³ = a³ + 3a²b + 3ab² + b³"),
    (25, "Умножьте: (x - 3)(x^2 + 3x + 9)", "x^3-27", "Разность кубов", "(a - b)(a² + ab + b²) = a³ - b³"),
]


class MiniAppRequestHandler(SimpleHTTPRequestHandler):
    """
    HTTP Request Handler serving both static WebApp files and JSON REST API.
    """

    def __init__(self, *args, db_path: str = DB_PATH, **kwargs):
        self.db_path = db_path
        super().__init__(*args, directory=str(WEBAPP_DIR), **kwargs)

    def _set_cors_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self):
        """Pre-flight CORS support."""
        self._set_cors_headers(204)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. API: Health Check
        if path == "/health":
            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "service": "max-math-webapp"}).encode("utf-8"))
            return

        # 2. API: Get Task (/api/task)
        if path == "/api/task":
            user_id = query.get("user_id", ["webapp_guest"])[0]
            tid_param = query.get("template_id", [None])[0]
            template_id = int(tid_param) if tid_param and tid_param.isdigit() else None

            t_id, question, answer, category, hint = None, None, None, "ФСУ (7 класс)", ""

            if generator_instance is not None:
                try:
                    checker = lambda uid, qtext: is_task_already_solved(uid, qtext, db_path=self.db_path)
                    task_obj = generator_instance.get_unique_task(user_id=user_id, template_id=template_id, checker=checker)
                    t_id = task_obj.template_id
                    question = task_obj.question_text
                    answer = task_obj.reference_answer
                    hint = getattr(task_obj, "hint", "")
                except Exception as e:
                    logger.warning("Ошибка генератора в webapp_server: %s", e)

            if question is None:
                chosen = random.choice(FALLBACK_TASKS)
                t_id, question, answer, category, hint = chosen[0], chosen[1], chosen[2], chosen[3], chosen[4]

            task_db_id = save_task_issue(
                user_id=user_id,
                template_id=t_id,
                task_text=question,
                expected_answer=answer,
                db_path=self.db_path
            )

            # Determine category label
            if t_id <= 7:
                category = "Разность квадратов"
            elif t_id <= 20:
                category = "Квадрат суммы / разности"
            else:
                category = "Кубы формул"

            res = {
                "status": "ok",
                "task_id": task_db_id,
                "template_id": t_id,
                "question": question,
                "expected_answer": answer,
                "category": category,
                "hint": hint or "Используйте формулу сокращенного умножения"
            }
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return

        # 3. API: Get User Statistics (/api/stats)
        if path == "/api/stats":
            user_id = query.get("user_id", ["webapp_guest"])[0]
            stats = get_user_statistics(user_id=user_id, db_path=self.db_path)
            stats["status"] = "ok"
            stats["user_id"] = user_id
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode("utf-8"))
            return

        # 4. API: Get 30 Formula Templates (/api/templates)
        if path == "/api/templates":
            templates_data = []
            if TEMPLATES_PATH.exists():
                try:
                    with open(TEMPLATES_PATH, encoding="utf-8") as f:
                        templates_data = json.load(f)
                except Exception:
                    pass

            if not templates_data:
                # Built-in minimal template list
                templates_data = [
                    {"id": tid, "name": f"Шаблон #{tid}", "formula": formula, "group": grp}
                    for tid, _, formula, grp, _ in FALLBACK_TASKS
                ]

            self._set_cors_headers(200)
            self.wfile.write(json.dumps(templates_data, ensure_ascii=False).encode("utf-8"))
            return

        # 5. API: Teacher Variant via GET (/api/lesson?variant=15)
        if path == "/api/lesson" and query.get("variant"):
            var_count = int(query.get("variant", [15])[0])
            doc = build_teacher_variant(grade=7, count=var_count)
            self._set_cors_headers(200)
            self.wfile.write(json.dumps({"status": "ok", "variant_15": doc}, ensure_ascii=False).encode("utf-8"))
            return

        # 6. Static files (index.html, etc.)
        if path in ("", "/"):
            self.path = "/index.html"

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            data = json.loads(body)
        except Exception as e:
            self._set_cors_headers(400)
            self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {e}"}).encode("utf-8"))
            return

        # 1. API: Check Answer (/api/check)
        if path == "/api/check":
            user_id = str(data.get("user_id", "webapp_guest"))
            task_id = int(data.get("task_id", 0))
            user_answer = str(data.get("user_answer", ""))
            expected_answer = str(data.get("expected_answer", ""))

            is_correct, feedback = check_answer(user_input=user_answer, expected_answer=expected_answer)

            if task_id > 0:
                save_task_result(task_id=task_id, user_answer=user_answer, is_correct=is_correct, db_path=self.db_path)

            stats = get_user_statistics(user_id=user_id, db_path=self.db_path)

            res = {
                "status": "ok",
                "is_correct": is_correct,
                "expected_answer": expected_answer,
                "feedback": feedback,
                "stats": stats
            }
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return

        # 2. API: Generate Lesson Plan (/api/lesson)
        if path == "/api/lesson":
            topic = str(data.get("topic", "ФСУ (7 класс)"))
            grade = int(data.get("grade", 7))
            author_id = str(data.get("author_id", "teacher_webapp"))

            plan_markdown = build_lesson_plan(
                topic=topic,
                grade=grade,
                author_id=author_id,
                save_to_db=True,
                db_path=self.db_path
            )
            variant_15 = build_teacher_variant(grade=grade, count=15)

            res = {
                "status": "ok",
                "topic": topic,
                "markdown": plan_markdown,
                "variant_15": variant_15
            }
            self._set_cors_headers(200)
            self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            return

        self._set_cors_headers(404)
        self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))


def create_server(host: str = "0.0.0.0", port: int = 8080, db_path: str = DB_PATH) -> ThreadingHTTPServer:
    """Create a configured ThreadingHTTPServer instance."""
    def handler_factory(*args, **kwargs):
        return MiniAppRequestHandler(*args, db_path=db_path, **kwargs)

    server = ThreadingHTTPServer((host, port), handler_factory)
    return server


_tunnel_proc = None


def start_tunnel_in_background(port: int = 8080) -> None:
    """
    Spawns a background thread that establishes an HTTPS tunnel via pinggy (over SSH port 443).
    Once connected, updates config.WEBAPP_URL with the public HTTPS URL so that MAX Messenger
    clients on any device can open the WebApp directly without 'такого нет' errors.
    """
    import subprocess
    import re
    import time
    import config

    global _tunnel_proc

    def _tunnel_worker():
        global _tunnel_proc
        hosts = ["free.pinggy.io", "qr@a.pinggy.io"]
        host_idx = 0
        while True:
            target_host = hosts[host_idx % len(hosts)]
            host_idx += 1
            cmd = [
                "ssh", "-p", "443",
                "-o", "StrictHostKeyChecking=no",
                "-o", "ServerAliveInterval=30",
                f"-R0:localhost:{port}",
                target_host
            ]
            try:
                logger.info("⏳ Запуск публичного HTTPS туннеля для тренажёра (%s)...", target_host)
                _tunnel_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                start_t = time.time()
                url_found = False
                collected_output = []
                while time.time() - start_t < 20 and _tunnel_proc.poll() is None:
                    line = _tunnel_proc.stdout.readline()
                    if not line:
                        break
                    collected_output.append(line.strip())
                    m = re.search(r"https://[a-zA-Z0-9\.\-]+(?:\.free\.pinggy\.net|\.run\.pinggy\-free\.link)", line)
                    if m:
                        public_url = m.group(0)
                        config.WEBAPP_URL = public_url
                        logger.info("🌐 Публичный HTTPS URL тренажёра успешно активирован: %s", public_url)
                        url_found = True
                        break

                if not url_found:
                    logger.warning("Не удалось автоматически получить HTTPS URL туннеля, используется: %s (вывод: %s)", config.WEBAPP_URL, " | ".join(collected_output))

                # Keep reading output so buffer doesn't fill up
                for _ in _tunnel_proc.stdout:
                    pass

                _tunnel_proc.wait()
            except Exception as e:
                logger.warning("Ошибка в фоновом туннеле: %s", e)

            # Reconnection backoff
            time.sleep(25)

    thread = threading.Thread(target=_tunnel_worker, daemon=True, name="PinggyTunnelThread")
    thread.start()


def start_server_in_thread(host: str = "0.0.0.0", port: int = 8080, db_path: str = DB_PATH) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """
    Starts the WebApp server in a background daemon thread.
    Also starts the public HTTPS tunnel if enabled in config.
    Returns (server_instance, thread).
    """
    server = create_server(host=host, port=port, db_path=db_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="WebAppServerThread")
    thread.start()
    logger.info("🌐 Веб-сервер тренажёра успешно запущен на http://%s:%d", host, port)

    import config
    if getattr(config, "ENABLE_TUNNEL", True) and "?startapp" not in os.getenv("WEBAPP_URL", ""):
        # If user explicitly provided a custom public URL in .env, don't override it with pinggy
        if not os.getenv("WEBAPP_URL"):
            start_tunnel_in_background(port=port)

    return server, thread



def run_standalone(host: str = "0.0.0.0", port: int = 8080, db_path: str = DB_PATH):
    """Run server synchronously in foreground."""
    server = create_server(host=host, port=port, db_path=db_path)
    print(f"🚀 Веб-сервер мини-приложения запущен: http://{host}:{port}")
    print("Нажмите Ctrl+C для остановки.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановка веб-сервера...")
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Запуск веб-сервера мини-приложения МАХ")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Хост для привязки")
    parser.add_argument("--port", type=int, default=8080, help="Порт веб-сервера")
    parser.add_argument("--db", type=str, default=DB_PATH, help="Путь к SQLite БД")
    args = parser.parse_args()

    run_standalone(host=args.host, port=args.port, db_path=args.db)
