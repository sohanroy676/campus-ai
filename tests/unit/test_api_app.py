"""The demo API over HTTP: a real server on a free local port, driven with urllib."""

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest
import uvicorn

from smartcampus.api.app import create_app


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app("ac-failure"), host="127.0.0.1", port=port, log_level="error")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started:
        if time.monotonic() > deadline:  # pragma: no cover
            raise RuntimeError("demo server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


def call(url: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            kind = response.headers.get("content-type", "")
            return response.status, json.loads(raw) if "json" in kind else raw.decode()
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_serves_the_dashboard_and_its_assets(base_url: str) -> None:
    status, page = call(f"{base_url}/")
    assert status == 200 and "Solution Comparison" in page and "/static/app.js" in page
    for asset in ("app.js", "style.css"):
        assert call(f"{base_url}/static/{asset}")[0] == 200


def test_full_demo_flow_over_http(base_url: str) -> None:
    status, reset = call(f"{base_url}/api/reset", {"scenario": "ac-failure"})
    assert status == 200 and reset["state"]["version"] == 0

    status, err = call(f"{base_url}/api/plan/joint", {})
    assert status == 400 and "incident" in err["detail"]
    assert call(f"{base_url}/api/plan/oracle", {})[0] == 404
    status, err = call(
        f"{base_url}/api/incident",
        {"room_id": "Mars-1", "kind": "ac_failure", "start_min": 2040, "end_min": 2280},
    )
    assert status == 400 and "unknown room" in err["detail"]

    status, out = call(
        f"{base_url}/api/incident",
        {"room_id": "AI-Lab-01", "kind": "ac_failure", "start_min": 2040, "end_min": 2280},
    )
    assert status == 200 and out["state"]["impact"]["affected"] == ["ml-lab"]
    assert out["steps"][0]["agent"] == "Maintenance agent"

    for method in ("greedy", "joint"):
        status, out = call(f"{base_url}/api/plan/{method}", {})
        assert status == 200 and out["state"]["proposals"][method]["ok"]
    assert out["state"]["recommended"] == "joint"

    status, out = call(f"{base_url}/api/apply/joint", {})
    assert status == 200 and out["state"]["version"] == 2
    assert [e["type"] for e in out["state"]["events"]] == ["fault_occurred", "plan_applied"]
    assert call(f"{base_url}/api/apply/joint", {})[0] == 400  # nothing left to apply

    status, state = call(f"{base_url}/api/state")
    assert status == 200 and state["applied"][0]["method"] == "joint"
