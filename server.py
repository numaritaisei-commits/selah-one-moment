#!/usr/bin/env python3
"""Selah: a dependency-free, local-first competition demo.

Offline mode never calls a provider and never invents Bible text. Live mode is
explicit, binds only to loopback, prompts for credentials without echoing them,
and keeps those credentials in process memory only.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import http.client
import json
import re
import secrets
import ssl
import threading
import time
import urllib.parse
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MAX_DRAFT_CHARS = 2_000
MAX_REQUEST_BYTES = 16 * 1024

GLOO_HOST = "platform.ai.gloo.com"
GLOO_TOKEN_PATH = "/oauth2/token"
GLOO_COMPLETIONS_PATH = "/ai/v2/chat/completions"
YV_HOST = "api.youversion.com"

PASSAGES = {
    "listen_first": "JAS.1.19",
    "gentle_answer": "PRO.15.1",
    "build_up": "EPH.4.29",
    "make_peace": "ROM.12.18",
    "peacemaker": "MAT.5.9",
    "careful_words": "PRO.12.18",
    "few_words": "PRO.17.27",
    "honor_others": "PHP.2.3",
    "do_not_repay": "1PE.3.9",
    "gracious_words": "COL.4.6",
    "guard_my_words": "PSA.141.3",
    "bear_and_forgive": "COL.3.13",
}

# Live competition recordings use only fixed, visibly fictional text. This avoids
# treating regex-based PII detection as a complete privacy control.
LIVE_SYNTHETIC_DRAFTS = {
    "That's a ridiculous take. You clearly didn't read anything we shared.",
}

# Populate only after the official competition account shows a specific model or
# route is covered at zero cost with no payment method. An empty tuple intentionally
# keeps live mode unavailable until that evidence exists.
APPROVED_ZERO_COST_GLOO_MODELS: tuple[str, ...] = ()

INTENTS = {"be_understood", "protect_relationship", "be_accurate"}
QUESTIONS = {
    "hear_meaning": "What would make your meaning easier to hear?",
    "protect_bond": "What could protect the relationship without hiding your concern?",
    "separate_fact": "Which part can you state as a fact rather than an assumption?",
    "lower_heat": "Which words carry more heat than meaning?",
    "invite_dialogue": "What question could leave room for a real answer?",
    "own_part": "What part of this moment is yours to take responsibility for?",
}
SENSITIVE_PATTERNS = (
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(r"https?://|www\.", re.IGNORECASE),
    re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){9,}(?!\d)"),
)


class SafeError(Exception):
    """An intentionally non-sensitive error suitable for a local response."""


def strict_json_loads(raw: bytes | str) -> Any:
    """Parse JSON while rejecting duplicate keys and non-finite numbers."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise SafeError("duplicate JSON key")
            out[key] = value
        return out

    def constant(_: str) -> Any:
        raise SafeError("non-finite JSON number")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise SafeError("invalid JSON") from exc


def has_sensitive_pattern(text: str) -> bool:
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def validate_request(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict) or set(payload) != {"draft", "intent"}:
        raise SafeError("request must contain only draft and intent")
    draft = payload["draft"]
    intent = payload["intent"]
    if not isinstance(draft, str) or not 1 <= len(draft) <= MAX_DRAFT_CHARS:
        raise SafeError("draft length is invalid")
    if not isinstance(intent, str) or intent not in INTENTS:
        raise SafeError("intent is invalid")
    if any(ord(char) < 32 and char not in "\n\t" for char in draft):
        raise SafeError("draft contains control characters")
    if has_sensitive_pattern(draft):
        raise SafeError("use synthetic text without contact details or URLs")
    return draft, intent


def validate_model_choice(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict) or set(payload) != {
        "passage_key",
        "question_key",
    }:
        raise SafeError("model output schema mismatch")
    key = payload["passage_key"]
    question_key = payload["question_key"]
    if not isinstance(key, str) or key not in PASSAGES:
        raise SafeError("model selected a passage outside the allowlist")
    if not isinstance(question_key, str) or question_key not in QUESTIONS:
        raise SafeError("model selected a question outside the allowlist")
    return key, QUESTIONS[question_key]


@dataclass(frozen=True)
class HttpResult:
    status: int
    headers: dict[str, str]
    body: bytes


def bounded_https_request(
    *,
    host: str,
    path: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
    max_bytes: int,
) -> HttpResult:
    """Perform one HTTPS request to a fixed host/path without redirects."""
    if host not in {GLOO_HOST, YV_HOST}:
        raise SafeError("provider host is not allowlisted")
    if not path.startswith("/") or ".." in path or "#" in path:
        raise SafeError("provider path is invalid")
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(host, 443, timeout=timeout, context=context)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise SafeError("provider redirect refused")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise SafeError("provider response exceeded limit")
        return HttpResult(
            status=response.status,
            headers={key.lower(): value for key, value in response.getheaders()},
            body=data,
        )
    except (OSError, http.client.HTTPException) as exc:
        raise SafeError("provider connection failed") from exc
    finally:
        connection.close()


class LiveProviders:
    def __init__(
        self,
        *,
        gloo_client_id: str,
        gloo_client_secret: str,
        yv_app_key: str,
        bible_id: int,
        gloo_model: str = "fixture-model",
        max_live_requests: int = 1,
        transport: Callable[..., HttpResult] = bounded_https_request,
    ) -> None:
        self._gloo_client_id = gloo_client_id
        self._gloo_client_secret = gloo_client_secret
        self._yv_app_key = yv_app_key
        self._bible_id = bible_id
        self._gloo_model = gloo_model
        self._transport = transport
        self._token = ""
        self._token_expiry = 0.0
        self._token_lock = threading.Lock()
        self._reflect_lock = threading.BoundedSemaphore(1)
        self._recent_requests: list[float] = []
        self._rate_lock = threading.Lock()
        self._remaining_requests = max_live_requests

    def _check_rate(self) -> None:
        now = time.monotonic()
        with self._rate_lock:
            self._recent_requests = [stamp for stamp in self._recent_requests if now - stamp < 60]
            if self._remaining_requests <= 0:
                raise SafeError("live-mode process request budget exhausted")
            if len(self._recent_requests) >= 5:
                raise SafeError("local live-mode rate limit reached")
            self._recent_requests.append(now)
            self._remaining_requests -= 1

    def _access_token(self) -> str:
        with self._token_lock:
            if self._token and time.monotonic() < self._token_expiry:
                return self._token
            credentials = f"{self._gloo_client_id}:{self._gloo_client_secret}".encode()
            auth = base64.b64encode(credentials).decode("ascii")
            body = urllib.parse.urlencode(
                {"grant_type": "client_credentials", "scope": "api/access"}
            ).encode("ascii")
            result = self._transport(
                host=GLOO_HOST,
                path=GLOO_TOKEN_PATH,
                method="POST",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json",
                },
                body=body,
                timeout=8.0,
                max_bytes=64 * 1024,
            )
            if result.status != HTTPStatus.OK:
                raise SafeError("Gloo authentication failed")
            payload = strict_json_loads(result.body)
            if not isinstance(payload, dict):
                raise SafeError("Gloo authentication response is invalid")
            token = payload.get("access_token")
            token_type = payload.get("token_type")
            expires_in = payload.get("expires_in")
            scope = payload.get("scope")
            if (
                not isinstance(token, str)
                or not 1 <= len(token.encode()) <= 8192
                or any(ord(c) < 33 for c in token)
            ):
                raise SafeError("Gloo token is invalid")
            if not isinstance(token_type, str) or token_type.lower() != "bearer":
                raise SafeError("Gloo token type is invalid")
            if not isinstance(expires_in, int) or isinstance(expires_in, bool) or expires_in <= 0:
                raise SafeError("Gloo token lifetime is invalid")
            if scope is not None and scope != "api/access":
                raise SafeError("Gloo token scope is invalid")
            ttl = min(max(expires_in - 60, 0), 3600)
            self._token = token
            self._token_expiry = time.monotonic() + ttl
            return token

    def choose_passage(self, draft: str, intent: str) -> tuple[str, str]:
        allowed = ", ".join(sorted(PASSAGES))
        system = (
            "You support an optional pause before a social post. Select exactly one "
            "opaque passage key and one opaque question key from the supplied allowlists. "
            "Do not quote or paraphrase scripture. Do not rewrite the draft. Return only "
            "a JSON object with exactly passage_key and question_key. "
            f"Allowed passage keys: {allowed}. Allowed question keys: {', '.join(sorted(QUESTIONS))}."
        )
        user = json.dumps({"draft": draft, "intent": intent}, ensure_ascii=False)
        request_payload = {
            "model": self._gloo_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 160,
            "tool_choice": "none",
        }
        body = json.dumps(request_payload, separators=(",", ":")).encode()
        if len(body) > 64 * 1024:
            raise SafeError("Gloo request exceeded limit")
        result = self._transport(
            host=GLOO_HOST,
            path=GLOO_COMPLETIONS_PATH,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=body,
            timeout=30.0,
            max_bytes=1024 * 1024,
        )
        if result.status != HTTPStatus.OK:
            raise SafeError("Gloo completion failed")
        envelope = strict_json_loads(result.body)
        if not isinstance(envelope, dict):
            raise SafeError("Gloo completion response is invalid")
        if envelope.get("model") != self._gloo_model:
            raise SafeError("Gloo completion model did not match the requested model")
        if envelope.get("auto_routing") is True:
            raise SafeError("Gloo automatic routing was refused")
        choices = envelope.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise SafeError("Gloo completion choices are invalid")
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
            raise SafeError("Gloo completion did not finish safely")
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise SafeError("Gloo completion message is invalid")
        if message.get("tool_calls"):
            raise SafeError("Gloo tool call refused")
        content = message.get("content")
        if not isinstance(content, str) or len(content) > 4096:
            raise SafeError("Gloo completion content is invalid")
        return validate_model_choice(strict_json_loads(content))

    def fetch_passage(self, passage_key: str) -> dict[str, str]:
        passage_id = PASSAGES[passage_key]
        if not re.fullmatch(r"[1-3]?[A-Z]{3}\.\d{1,3}\.\d{1,3}", passage_id):
            raise SafeError("passage mapping is invalid")
        base_path = f"/v1/bibles/{self._bible_id}"
        headers = {"X-YVP-App-Key": self._yv_app_key, "Accept": "application/json"}
        metadata_result = self._transport(
            host=YV_HOST,
            path=base_path,
            method="GET",
            headers=headers,
            body=None,
            timeout=8.0,
            max_bytes=512 * 1024,
        )
        if metadata_result.status != HTTPStatus.OK:
            raise SafeError("YouVersion Bible metadata request failed")
        metadata = strict_json_loads(metadata_result.body)
        if not isinstance(metadata, dict) or metadata.get("id") != self._bible_id:
            raise SafeError("YouVersion Bible metadata is invalid")
        title = metadata.get("localized_title") or metadata.get("title")
        abbreviation = metadata.get("localized_abbreviation") or metadata.get("abbreviation")
        copyright_text = metadata.get("copyright")
        deep_link = metadata.get("youversion_deep_link")
        if not all(isinstance(v, str) and v for v in (title, abbreviation, copyright_text)):
            raise SafeError("YouVersion attribution is incomplete")
        try:
            parsed_link = urllib.parse.urlsplit(deep_link) if isinstance(deep_link, str) else None
            parsed_port = parsed_link.port if parsed_link is not None else None
        except ValueError as exc:
            raise SafeError("YouVersion link is invalid") from exc
        if (
            parsed_link is None
            or parsed_link.scheme != "https"
            or parsed_link.hostname != "www.bible.com"
            or parsed_link.username is not None
            or parsed_link.password is not None
            or parsed_port not in {None, 443}
        ):
            raise SafeError("YouVersion link is invalid")
        passage_result = self._transport(
            host=YV_HOST,
            path=f"{base_path}/passages/{passage_id}?format=text&include_headings=false&include_notes=false",
            method="GET",
            headers=headers,
            body=None,
            timeout=8.0,
            max_bytes=512 * 1024,
        )
        if passage_result.status != HTTPStatus.OK:
            raise SafeError("YouVersion passage request failed")
        passage = strict_json_loads(passage_result.body)
        if not isinstance(passage, dict) or passage.get("id") != passage_id:
            raise SafeError("YouVersion passage is invalid")
        content = passage.get("content")
        reference = passage.get("reference")
        if not isinstance(content, str) or not 1 <= len(content) <= 20_000:
            raise SafeError("YouVersion passage content is invalid")
        if not isinstance(reference, str) or not 1 <= len(reference) <= 200:
            raise SafeError("YouVersion passage reference is invalid")
        return {
            "content": content,
            "reference": reference,
            "version": str(abbreviation),
            "version_title": str(title),
            "copyright": str(copyright_text),
            "youversion_url": deep_link,
        }

    def reflect(self, draft: str, intent: str) -> dict[str, Any]:
        if draft not in LIVE_SYNTHETIC_DRAFTS:
            raise SafeError("live mode accepts only a fixed synthetic scenario")
        if not self._reflect_lock.acquire(blocking=False):
            raise SafeError("a live reflection is already in progress")
        try:
            self._check_rate()
            passage_key, question = self.choose_passage(draft, intent)
            passage = self.fetch_passage(passage_key)
            return {
                "mode": "live",
                "reflection_question": question,
                "passage": passage,
                "notice": "Verse text, version, and attribution were returned by YouVersion.",
            }
        finally:
            self._reflect_lock.release()


def offline_reflection(_: str, intent: str) -> dict[str, Any]:
    questions = {
        "be_understood": "What would make your meaning easier to hear?",
        "protect_relationship": "What could protect the relationship without hiding your concern?",
        "be_accurate": "Which part can you state as a fact rather than an assumption?",
    }
    return {
        "mode": "offline-preview",
        "reflection_question": questions[intent],
        "passage": None,
        "notice": (
            "Offline preview: no provider was called, so Selah does not display or invent verse text."
        ),
    }


class SelahServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], handler: type[BaseHTTPRequestHandler], reflector: Callable[[str, str], dict[str, Any]], mode: str) -> None:
        super().__init__(address, handler)
        self.reflector = reflector
        self.mode = mode
        self.session_token = secrets.token_urlsafe(24)


class Handler(BaseHTTPRequestHandler):
    server: SelahServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # Do not log paths, payloads, headers, or provider bodies.
        return

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )

    def _valid_host(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host", "") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _valid_origin(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Origin", "") in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }

    def _valid_session(self) -> bool:
        supplied = self.headers.get("X-Selah-Session", "")
        return bool(supplied) and secrets.compare_digest(supplied, self.server.session_token)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_static(self, file_name: str, content_type: str) -> None:
        path = STATIC / file_name
        try:
            raw = path.read_bytes()
        except OSError:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        self.send_response(HTTPStatus.OK)
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if not self._valid_host():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "host refused"})
            return
        routes = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/selah-cover.png": ("selah-cover.png", "image/png"),
        }
        if self.path == "/api/status":
            self._send_json(
                HTTPStatus.OK,
                {"mode": self.server.mode, "session_token": self.server.session_token},
            )
            return
        route = routes.get(self.path)
        if route is None:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        self._send_static(*route)

    def do_POST(self) -> None:  # noqa: N802
        if not self._valid_host() or not self._valid_origin() or not self._valid_session():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "origin refused"})
            return
        if self.path != "/api/reflect":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "JSON required"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 1 <= length <= MAX_REQUEST_BYTES:
            self._send_json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "request too large"})
            return
        raw = self.rfile.read(length)
        request_id = secrets.token_hex(4)
        started = time.monotonic()
        try:
            draft, intent = validate_request(strict_json_loads(raw))
            response = self.server.reflector(draft, intent)
            self._send_json(HTTPStatus.OK, {"request_id": request_id, **response})
        except SafeError:
            self._send_json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "request_id": request_id,
                    "error": (
                        "Selah could not complete the pause. Your draft is unchanged; "
                        "keep editing or continue without Selah."
                    ),
                    "fail_open": True,
                },
            )
        finally:
            _ = round((time.monotonic() - started) * 1000)


def nonempty_secret(prompt: str) -> str:
    value = getpass.getpass(prompt)
    if not value or len(value) > 8192 or any(ord(c) < 33 for c in value):
        raise SystemExit("Credential input was empty or invalid; nothing was sent.")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local Selah demo")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--live", action="store_true", help="enable official provider calls")
    parser.add_argument("--bible-id", type=int, help="licensed YouVersion Bible ID")
    parser.add_argument("--gloo-model", help="officially verified zero-cost Gloo model ID")
    parser.add_argument(
        "--confirm-zero-cost",
        action="store_true",
        help="confirm competition entitlement is active and no card/payment is required",
    )
    parser.add_argument(
        "--max-live-requests",
        type=int,
        default=1,
        choices=[1, 2, 3],
        help="hard per-process provider-call budget (default: 1)",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65535:
        raise SystemExit("Port must be between 1 and 65535.")
    if args.live:
        if not args.confirm_zero_cost:
            raise SystemExit("Live mode requires --confirm-zero-cost.")
        if args.bible_id is None or args.bible_id <= 0:
            raise SystemExit("Live mode requires a licensed positive --bible-id.")
        if args.gloo_model not in APPROVED_ZERO_COST_GLOO_MODELS:
            raise SystemExit(
                "Live mode is locked until a specific zero-cost Gloo model is verified in the official participant account."
            )
        client_id = nonempty_secret("Gloo client ID (hidden): ")
        client_secret = nonempty_secret("Gloo client secret (hidden): ")
        yv_key = nonempty_secret("YouVersion App Key (hidden): ")
        providers = LiveProviders(
            gloo_client_id=client_id,
            gloo_client_secret=client_secret,
            yv_app_key=yv_key,
            bible_id=args.bible_id,
            gloo_model=args.gloo_model,
            max_live_requests=args.max_live_requests,
        )
        reflector = providers.reflect
        mode = "live"
    else:
        reflector = offline_reflection
        mode = "offline-preview"
    server = SelahServer((args.host, args.port), Handler, reflector, mode)
    print(f"Selah {mode} is available at http://{args.host}:{args.port}")
    print("Press Ctrl-C to stop. Drafts and credentials are not written by this app.")
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
