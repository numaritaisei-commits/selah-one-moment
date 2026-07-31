import json
import http.client
import threading
import unittest
from pathlib import Path

import server


class JsonTests(unittest.TestCase):
    def test_accepts_plain_json(self):
        self.assertEqual(server.strict_json_loads('{"a":1}'), {"a": 1})

    def test_rejects_duplicate_key(self):
        with self.assertRaises(server.SafeError):
            server.strict_json_loads('{"a":1,"a":2}')

    def test_rejects_nan(self):
        with self.assertRaises(server.SafeError):
            server.strict_json_loads('{"a":NaN}')

    def test_rejects_trailing_text(self):
        with self.assertRaises(server.SafeError):
            server.strict_json_loads('{"a":1} extra')


class RequestTests(unittest.TestCase):
    def test_valid_request(self):
        self.assertEqual(
            server.validate_request({"draft": "That feels unfair.", "intent": "be_accurate"}),
            ("That feels unfair.", "be_accurate"),
        )

    def test_rejects_unknown_key(self):
        with self.assertRaises(server.SafeError):
            server.validate_request({"draft": "x", "intent": "be_accurate", "url": "x"})

    def test_rejects_unknown_intent(self):
        with self.assertRaises(server.SafeError):
            server.validate_request({"draft": "x", "intent": "win"})

    def test_rejects_email(self):
        with self.assertRaises(server.SafeError):
            server.validate_request({"draft": "mail me at a@example.com", "intent": "be_accurate"})

    def test_rejects_phone(self):
        with self.assertRaises(server.SafeError):
            server.validate_request({"draft": "call 123-456-7890", "intent": "be_accurate"})

    def test_rejects_url(self):
        with self.assertRaises(server.SafeError):
            server.validate_request({"draft": "see https://example.com", "intent": "be_accurate"})

    def test_rejects_oversize_draft(self):
        with self.assertRaises(server.SafeError):
            server.validate_request({"draft": "x" * 2001, "intent": "be_accurate"})


class ModelOutputTests(unittest.TestCase):
    def test_valid_choice(self):
        self.assertEqual(
            server.validate_model_choice(
                {"passage_key": "listen_first", "question_key": "hear_meaning"}
            ),
            ("listen_first", "What would make your meaning easier to hear?"),
        )

    def test_rejects_unknown_passage(self):
        with self.assertRaises(server.SafeError):
            server.validate_model_choice(
                {"passage_key": "invented", "question_key": "hear_meaning"}
            )

    def test_rejects_extra_key(self):
        with self.assertRaises(server.SafeError):
            server.validate_model_choice(
                {"passage_key": "listen_first", "question_key": "hear_meaning", "verse": "fake"}
            )

    def test_rejects_unknown_question(self):
        with self.assertRaises(server.SafeError):
            server.validate_model_choice(
                {"passage_key": "listen_first", "question_key": "invented"}
            )


class OfflineTests(unittest.TestCase):
    def test_offline_never_returns_verse(self):
        result = server.offline_reflection("synthetic", "protect_relationship")
        self.assertEqual(result["mode"], "offline-preview")
        self.assertIsNone(result["passage"])
        self.assertIn("does not display or invent", result["notice"])

    def test_all_intents_have_questions(self):
        for intent in server.INTENTS:
            with self.subTest(intent=intent):
                result = server.offline_reflection("synthetic", intent)
                self.assertTrue(result["reflection_question"].endswith("?"))


class FakeTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        path = kwargs["path"]
        if path == server.GLOO_TOKEN_PATH:
            body = {"access_token": "token-value", "token_type": "Bearer", "expires_in": 600, "scope": "api/access"}
        elif path == server.GLOO_COMPLETIONS_PATH:
            content = json.dumps(
                {"passage_key": "gentle_answer", "question_key": "lower_heat"}
            )
            body = {
                "model": "fixture-model",
                "auto_routing": False,
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": content},
                    }
                ],
            }
        elif path == "/v1/bibles/3034":
            body = {
                "id": 3034,
                "abbreviation": "BSB",
                "localized_title": "Berean Standard Bible",
                "copyright": "Public-domain test attribution",
                "youversion_deep_link": "https://www.bible.com/versions/3034",
            }
        elif path.startswith("/v1/bibles/3034/passages/PRO.15.1"):
            body = {"id": "PRO.15.1", "content": "Provider-returned test text", "reference": "Proverbs 15:1"}
        else:
            raise AssertionError(f"unexpected path: {path}")
        return server.HttpResult(200, {}, json.dumps(body).encode())


class LiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.providers = server.LiveProviders(
            gloo_client_id="client-id",
            gloo_client_secret="client-secret",
            yv_app_key="yv-key",
            bible_id=3034,
            transport=self.transport,
        )

    def test_full_adapter_path(self):
        result = self.providers.reflect(next(iter(server.LIVE_SYNTHETIC_DRAFTS)), "be_accurate")
        self.assertEqual(result["mode"], "live")
        self.assertEqual(result["passage"]["reference"], "Proverbs 15:1")
        self.assertEqual(result["passage"]["version_title"], "Berean Standard Bible")
        self.assertEqual(result["passage"]["version"], "BSB")
        self.assertEqual(result["passage"]["copyright"], "Public-domain test attribution")
        self.assertEqual(len(self.transport.calls), 4)

    def test_rejects_completion_from_different_model(self):
        original = self.transport

        def mismatched_model_transport(**kwargs):
            result = original(**kwargs)
            if kwargs["path"] == server.GLOO_COMPLETIONS_PATH:
                body = json.loads(result.body)
                body["model"] = "unexpected-model"
                return server.HttpResult(200, {}, json.dumps(body).encode())
            return result

        self.providers._transport = mismatched_model_transport
        with self.assertRaises(server.SafeError):
            self.providers.choose_passage("synthetic", "be_accurate")

    def test_rejects_automatic_model_routing(self):
        original = self.transport

        def auto_routed_transport(**kwargs):
            result = original(**kwargs)
            if kwargs["path"] == server.GLOO_COMPLETIONS_PATH:
                body = json.loads(result.body)
                body["auto_routing"] = True
                return server.HttpResult(200, {}, json.dumps(body).encode())
            return result

        self.providers._transport = auto_routed_transport
        with self.assertRaises(server.SafeError):
            self.providers.choose_passage("synthetic", "be_accurate")

    def test_token_is_reused_in_memory(self):
        self.providers.choose_passage("first", "be_accurate")
        self.providers.choose_passage("second", "be_accurate")
        token_calls = [c for c in self.transport.calls if c["path"] == server.GLOO_TOKEN_PATH]
        self.assertEqual(len(token_calls), 1)

    def test_gloo_never_receives_verse_text(self):
        self.providers.reflect(next(iter(server.LIVE_SYNTHETIC_DRAFTS)), "be_accurate")
        completion_call = next(c for c in self.transport.calls if c["path"] == server.GLOO_COMPLETIONS_PATH)
        body = completion_call["body"].decode()
        self.assertNotIn("Provider-returned test text", body)

    def test_youversion_key_is_header_only(self):
        self.providers.fetch_passage("gentle_answer")
        for call in self.transport.calls:
            if call["host"] == server.YV_HOST:
                self.assertNotIn("yv-key", call["path"])
                self.assertEqual(call["headers"]["X-YVP-App-Key"], "yv-key")

    def test_rejects_lookalike_bible_host(self):
        original = self.transport

        def bad_link_transport(**kwargs):
            result = original(**kwargs)
            if kwargs["path"] == "/v1/bibles/3034":
                body = json.loads(result.body)
                body["youversion_deep_link"] = "https://www.bible.com.evil.invalid/versions/3034"
                return server.HttpResult(200, {}, json.dumps(body).encode())
            return result

        self.providers._transport = bad_link_transport
        with self.assertRaises(server.SafeError):
            self.providers.fetch_passage("gentle_answer")

    def test_live_request_budget_is_atomic(self):
        synthetic = next(iter(server.LIVE_SYNTHETIC_DRAFTS))
        self.providers.reflect(synthetic, "be_accurate")
        with self.assertRaises(server.SafeError):
            self.providers.reflect(synthetic, "be_accurate")

    def test_live_rejects_unfixed_draft(self):
        with self.assertRaises(server.SafeError):
            self.providers.reflect("A different draft", "be_accurate")


class StaticSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (Path(server.STATIC) / "app.js").read_text(encoding="utf-8")
        cls.html = (Path(server.STATIC) / "index.html").read_text(encoding="utf-8")

    def test_no_local_storage(self):
        self.assertNotIn("localStorage", self.js)
        self.assertNotIn("sessionStorage", self.js)

    def test_no_inner_html(self):
        self.assertNotIn("innerHTML", self.js)

    def test_no_inline_script(self):
        self.assertNotIn("<script>", self.html)

    def test_no_external_resource(self):
        self.assertNotIn("https://", self.html)

    def test_live_request_timeout_allows_provider_budget(self):
        self.assertIn("controller.abort(), 65000", self.js)
        self.assertNotIn("controller.abort(), 35000", self.js)

    def test_live_version_display_includes_title_and_abbreviation(self):
        self.assertIn("result.passage.version_title", self.js)
        self.assertIn("(${result.passage.version})", self.js)
        self.assertIn("result.passage.copyright", self.js)


class ServerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.httpd = server.SelahServer(
            ("127.0.0.1", 0), server.Handler, server.offline_reflection, "offline-preview"
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_status_and_security_headers(self):
        status, headers, body = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["mode"], "offline-preview")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])

    def test_offline_http_flow_never_returns_verse(self):
        raw = json.dumps(
            {"draft": "That conclusion feels unfair.", "intent": "be_accurate"}
        ).encode()
        status, _, body = self.request(
            "POST",
            "/api/reflect",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(raw)),
                "Origin": f"http://127.0.0.1:{self.port}",
                "X-Selah-Session": self.httpd.session_token,
            },
        )
        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["mode"], "offline-preview")
        self.assertIsNone(payload["passage"])

    def test_invalid_http_input_fails_open(self):
        raw = json.dumps({"draft": "call 123-456-7890", "intent": "be_accurate"}).encode()
        status, _, body = self.request(
            "POST",
            "/api/reflect",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(raw)),
                "Origin": f"http://127.0.0.1:{self.port}",
                "X-Selah-Session": self.httpd.session_token,
            },
        )
        payload = json.loads(body)
        self.assertEqual(status, 502)
        self.assertTrue(payload["fail_open"])
        self.assertEqual(
            payload["error"],
            "Selah could not complete the pause. Your draft is unchanged; "
            "keep editing or continue without Selah.",
        )

    def test_cross_origin_post_is_refused(self):
        raw = json.dumps({"draft": "synthetic", "intent": "be_accurate"}).encode()
        status, _, _ = self.request(
            "POST",
            "/api/reflect",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(raw)),
                "Origin": "https://attacker.invalid",
                "X-Selah-Session": self.httpd.session_token,
            },
        )
        self.assertEqual(status, 403)

    def test_missing_session_token_is_refused(self):
        raw = json.dumps({"draft": "synthetic", "intent": "be_accurate"}).encode()
        status, _, _ = self.request(
            "POST",
            "/api/reflect",
            body=raw,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(raw)),
                "Origin": f"http://127.0.0.1:{self.port}",
            },
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
