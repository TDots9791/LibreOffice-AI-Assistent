#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for provider adapters, config and prompt building (host Python)."""

import os
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)                                    # mock_server
sys.path.insert(0, os.path.join(ROOT, "src", "extension", "Scripts", "python", "pythonpath"))

import mock_server                                          # noqa: E402
from lo_ai import http_client                               # noqa: E402
from lo_ai import assistant as _assistant                   # noqa: E402
from lo_ai.config import Config                             # noqa: E402
from lo_ai.http_client import Cancelled, HttpError          # noqa: E402
from lo_ai.providers import create_provider                 # noqa: E402
from lo_ai.providers.base import ProviderError              # noqa: E402
from lo_ai.providers.openai_compat import build_payload     # noqa: E402

SERVER = None
BASE = ""


def setUpModule():
    global SERVER, BASE
    SERVER, BASE = mock_server.start_server()


def tearDownModule():
    if SERVER:
        SERVER.shutdown()


def settings(style, model="test-model", key="good-key", **kw):
    s = {
        "api_style": style,
        "base_url": BASE + "/v1",
        "model": model,
        "api_key": key,
        "temperature": 0.7,
        "max_tokens": 0,
        "timeout": 30,
        "streaming": True,
        "system_prompt": "be brief",
    }
    s.update(kw)
    return s


MESSAGES = [
    {"role": "system", "content": "be brief"},
    {"role": "user", "content": "say hi"},
]


class TestOpenAICompat(unittest.TestCase):
    def test_streaming(self):
        p = create_provider(settings("openai"))
        seen = []
        answer = p.stream_chat(MESSAGES, seen.append)
        self.assertEqual(answer, "Hello from chat")
        self.assertEqual("".join(seen), "Hello from chat")

    def test_non_streaming(self):
        p = create_provider(settings("openai", streaming=False))
        answer = p.stream_chat(MESSAGES, lambda s: None)
        self.assertEqual(answer, "Hello from chat")

    def test_bad_key(self):
        p = create_provider(settings("openai", key="badkey"))
        with self.assertRaises(ProviderError) as ctx:
            p.stream_chat(MESSAGES, lambda s: None)
        self.assertIn("invalid api key", str(ctx.exception))

    def test_reasoning_payload(self):
        s = settings("openai", model="gpt-5.1", max_tokens=100, temperature=0.5)
        payload = build_payload(create_provider(s), MESSAGES, stream=False)
        self.assertNotIn("temperature", payload)
        self.assertIn("max_completion_tokens", payload)
        self.assertNotIn("max_tokens", payload)

    def test_plain_payload(self):
        s = settings("openai", model="glm-4.7", max_tokens=100, temperature=0.5)
        payload = build_payload(create_provider(s), MESSAGES, stream=False)
        self.assertEqual(payload["temperature"], 0.5)
        self.assertEqual(payload["max_tokens"], 100)
        self.assertNotIn("max_completion_tokens", payload)


class TestAnthropic(unittest.TestCase):
    def test_streaming(self):
        p = create_provider(settings("anthropic"))
        seen = []
        answer = p.stream_chat(MESSAGES, seen.append)
        self.assertEqual(answer, "Hi from claude")

    def test_payload_shape(self):
        p = create_provider(settings("anthropic", max_tokens=0))
        payload = p.build_payload(MESSAGES, stream=False)
        self.assertEqual(payload["max_tokens"], 4096)
        self.assertEqual(payload["system"], "be brief")
        self.assertNotIn("system", payload["messages"][0])
        self.assertEqual(payload["messages"][0]["role"], "user")


class TestResponses(unittest.TestCase):
    def test_streaming(self):
        p = create_provider(settings("responses", model="gpt-5-codex"))
        seen = []
        answer = p.stream_chat(MESSAGES, seen.append)
        self.assertEqual(answer, "Codex!")
        self.assertEqual("".join(seen), "Codex!")

    def test_input_mapping(self):
        p = create_provider(settings("responses", model="codex-mini-latest"))
        payload = p.build_payload(MESSAGES, stream=False)
        self.assertEqual(payload["instructions"], "be brief")
        self.assertEqual(payload["input"][0]["role"], "user")
        self.assertEqual(payload["input"][0]["content"][0]["type"], "input_text")


class TestCancellation(unittest.TestCase):
    def test_cancel_mid_stream(self):
        p = create_provider(settings("openai"))
        cancel = threading.Event()
        count = [0]

        def on_delta(chunk):
            count[0] += 1
            cancel.set()

        with self.assertRaises(Cancelled):
            p.stream_chat(MESSAGES, on_delta, cancel=cancel)
        self.assertGreaterEqual(count[0], 1)


class TestHttpErrors(unittest.TestCase):
    def test_error_extraction(self):
        self.assertEqual(http_client._extract_error_message(
            '{"error": {"message": "quota"}}'), "quota")
        self.assertIsNone(http_client._extract_error_message("not json"))


class TestConfig(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Config(tmp)
            cfg.active_provider = "anthropic"
            cfg.set_provider_settings("anthropic", {
                "api_key": "sk-test", "model": "claude-sonnet-4-5"})
            cfg.save()
            again = Config(tmp)
            self.assertEqual(again.active_provider, "anthropic")
            s = again.provider_settings("anthropic")
            self.assertEqual(s["api_key"], "sk-test")
            self.assertEqual(s["temperature"], 0.7)  # default preserved
            mode = os.stat(again.path).st_mode & 0o777
            self.assertEqual(mode, 0o600)

    def test_coercion(self):
        self.assertEqual(Config.coerce_int("42", 0), 42)
        self.assertEqual(Config.coerce_int("abc", 7), 7)
        self.assertIsNone(Config.coerce_float_none(""))
        self.assertEqual(Config.coerce_float_none("0,5"), 0.5)


class TestAssistant(unittest.TestCase):
    def test_build_user_message_translate(self):
        msg = _assistant.build_user_message(
            "translate", "привет", "", "English")
        self.assertIn("English", msg)
        self.assertIn("привет", msg)

    def test_context_appended(self):
        msg = _assistant.build_user_message("chat", "what is this?", "\n---\nCTX\n---\n")
        self.assertIn("CTX", msg)

    def test_history_trimming(self):
        messages = _assistant.build_messages(
            "sys", [{"role": "user", "content": str(i)} for i in range(20)], "new")
        self.assertEqual(messages[-1]["content"], "new")
        self.assertLessEqual(len(messages), 22)


if __name__ == "__main__":
    unittest.main(verbosity=2)
