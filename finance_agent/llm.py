from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, purpose: str) -> str: ...


class ReplayClient:
    def __init__(self, path: Path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.entries = payload["interactions"]
        self.position = 0

    def complete(self, prompt: str, purpose: str) -> str:
        if self.position >= len(self.entries):
            raise RuntimeError("recording exhausted")
        entry = self.entries[self.position]
        self.position += 1
        if entry["purpose"] != purpose:
            raise RuntimeError(f"replay mismatch: expected {entry['purpose']!r}, got {purpose!r}")
        return entry["response"]


class OllamaClient:
    def __init__(self, model: str, url: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    def complete(self, prompt: str, purpose: str) -> str:
        body = json.dumps(
            {"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0}}
        ).encode()
        request = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read())["response"]
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc


class RecordingClient:
    def __init__(self, inner: LLMClient, path: Path, provider: str, model: str):
        self.inner = inner
        self.path = path
        self.payload = {"provider": provider, "model": model, "interactions": []}

    def complete(self, prompt: str, purpose: str) -> str:
        response = self.inner.complete(prompt, purpose)
        self.payload["interactions"].append(
            {"purpose": purpose, "prompt": prompt, "response": response}
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.payload, indent=2) + "\n", encoding="utf-8")
        return response
