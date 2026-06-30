#!/usr/bin/env python3
"""
Programmatic client for the Seattle Regulatory RAG API (PolicyBridge).

It clears both access gates for you:
  1. Team key  -> sent as the  X-Access-Key  header on every request
  2. User JWT  -> obtained from /api/auth/login (or /api/auth/register), then
                  sent as  Authorization: Bearer <token>

The /api/chat endpoint streams Server-Sent Events. This client parses that
stream and returns the assembled answer text plus the source citations.

Usage (CLI):
    export RAG_ACCESS_KEY="the-team-access-key"
    export RAG_EMAIL="you@example.com"
    python rag_client.py "Where do SMC and WAC stormwater rules conflict?"

Usage (library):
    from rag_client import RagClient
    client = RagClient(access_key="...", email="you@example.com")
    answer, sources = client.ask("your question")

Only dependency: requests  ->  pip install requests
"""

from __future__ import annotations

import json
import os
import sys

import requests

DEFAULT_BASE_URL = "https://seattlepolicyagent.duckdns.org"


class RagClient:
    def __init__(self, access_key, email, name=None, base_url=DEFAULT_BASE_URL, timeout=120):
        self.base_url = base_url.rstrip("/")
        self.access_key = access_key
        self.email = email
        self.name = name or email.split("@")[0]
        self.timeout = timeout
        self._token = None

    # ---- auth -------------------------------------------------------------

    @property
    def _key_headers(self):
        return {"X-Access-Key": self.access_key, "Content-Type": "application/json"}

    def login(self):
        """Get a JWT. Logs in by email; registers first if the user is new."""
        r = requests.post(
            f"{self.base_url}/api/auth/login",
            headers=self._key_headers,
            json={"email": self.email},
            timeout=self.timeout,
        )
        if r.status_code == 404:  # unknown email -> register, no password needed
            r = requests.post(
                f"{self.base_url}/api/auth/register",
                headers=self._key_headers,
                json={"email": self.email, "name": self.name},
                timeout=self.timeout,
            )
        if r.status_code == 403:
            raise RuntimeError("Rejected by team gate: X-Access-Key is wrong or missing.")
        r.raise_for_status()
        self._token = r.json()["token"]
        return self._token

    # ---- chat -------------------------------------------------------------

    def ask(self, query, agency_filter=None, on_token=None, verbose=False):
        """Ask one question. Returns (answer_text, sources_list).

        agency_filter: optional list like ["SMC", "WAC"] to scope retrieval.
        on_token:      optional callback(str) called for each streamed fragment
                       (use it to print tokens live as they arrive).
        """
        if self._token is None:
            self.login()

        headers = {
            "X-Access-Key": self.access_key,
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        body = {"query": query}
        if agency_filter:
            body["agency_filter"] = agency_filter

        answer_parts = []
        sources = []

        with requests.post(
            f"{self.base_url}/api/chat",
            headers=headers,
            json=body,
            stream=True,
            timeout=self.timeout,
        ) as resp:
            if resp.status_code in (401, 403):
                raise RuntimeError(f"Auth failed ({resp.status_code}): {resp.text}")
            resp.raise_for_status()

            event = None
            data_lines = []
            for raw in resp.iter_lines(decode_unicode=True):
                # Blank line terminates one SSE event.
                if not raw:
                    if event is not None:
                        data = "\n".join(data_lines)
                        if self._handle(event, data, answer_parts, sources, on_token, verbose):
                            break  # "done" event seen
                    event, data_lines = None, []
                    continue
                if raw.startswith("event:"):
                    event = raw[len("event:"):].strip()
                elif raw.startswith("data:"):
                    data_lines.append(raw[len("data:"):].lstrip())

        return "".join(answer_parts), sources

    @staticmethod
    def _decode(data):
        """Token/sources arrive JSON-encoded; status/usage arrive as plain text."""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, ValueError):
            return data

    def _handle(self, event, data, answer_parts, sources, on_token, verbose):
        """Process one SSE event. Returns True when the stream is done."""
        if event == "token":
            text = self._decode(data)
            if isinstance(text, str):
                answer_parts.append(text)
                if on_token:
                    on_token(text)
        elif event == "sources":
            payload = self._decode(data)
            if isinstance(payload, list):
                sources.extend(payload)
        elif event == "done":
            return True
        elif verbose and event in ("status", "premise_flag", "usage"):
            print(f"[{event}] {self._decode(data)}", file=sys.stderr)
        return False


def _main():
    access_key = os.environ.get("RAG_ACCESS_KEY")
    email = os.environ.get("RAG_EMAIL")
    base_url = os.environ.get("RAG_BASE_URL", DEFAULT_BASE_URL)

    if not access_key or not email:
        print("Set RAG_ACCESS_KEY and RAG_EMAIL environment variables.", file=sys.stderr)
        sys.exit(2)
    if len(sys.argv) < 2:
        print(f'Usage: python {sys.argv[0]} "your question"', file=sys.stderr)
        sys.exit(2)

    query = " ".join(sys.argv[1:])
    client = RagClient(access_key=access_key, email=email, base_url=base_url)

    # Stream the answer to stdout as it arrives.
    answer, sources = client.ask(query, on_token=lambda t: (sys.stdout.write(t), sys.stdout.flush()), verbose=True)

    print("\n\n--- Sources ---")
    for i, s in enumerate(sources, 1):
        # Source shape comes from the pipeline; print the common fields if present.
        cite = s.get("citation") or s.get("id") or "?"
        agency = s.get("agency", "")
        print(f"{i}. {cite} {('(' + agency + ')') if agency else ''}".rstrip())


if __name__ == "__main__":
    _main()
