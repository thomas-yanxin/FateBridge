"""Exercise real process contention and error-body retention without JPL calls."""

import io
import json
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from email.message import Message

import pytest

from scripts import astrodice_horizons_transport as transport


def request():
    return urllib.request.Request(
        "https://ssd.jpl.nasa.gov/api/horizons.api?format=json"
    )


class Response(io.BytesIO):
    status = 200


def test_separate_processes_never_overlap_until_response_bodies_are_closed(tmp_path):
    program = """
import json,os,ssl,sys,time,urllib.request
from pathlib import Path
from scripts import astrodice_horizons_transport as t
timeline=Path(sys.argv[1]); state=Path(sys.argv[2])
def event(kind):
 with timeline.open('a') as stream: stream.write(json.dumps([kind,os.getpid(),time.time()])+'\\n')
class Response:
 status=200
 def __enter__(self): event('enter'); return self
 def read(self): time.sleep(0.08); event('body_read'); return b'full body'
 def __exit__(self,*args): event('closed')
t.urllib.request.urlopen=lambda *args,**kwargs: Response()
with t.open_horizons(urllib.request.Request('https://ssd.jpl.nasa.gov/api/horizons.api'),context=ssl.create_default_context(),state_path=state) as response:
 assert response.read()==b'full body'
"""
    timeline, state = tmp_path / "timeline", tmp_path / "state"
    processes = [
        subprocess.Popen([sys.executable, "-c", program, str(timeline), str(state)])
        for _ in range(3)
    ]
    assert [process.wait(timeout=15) for process in processes] == [0, 0, 0]
    rows = [json.loads(line) for line in timeline.read_text().splitlines()]
    assert [row[0] for row in rows] == ["enter", "body_read", "closed"] * 3
    assert len({row[1] for row in rows}) == 3
    assert rows[3][2] - rows[2][2] >= 0.95
    assert rows[6][2] - rows[5][2] >= 0.95


@pytest.mark.parametrize(
    "header,expected_delay", [("120", 120), (None, 30), ("bad", 30)]
)
def test_error_body_is_archivable_and_next_process_obeys_shared_cooldown(
    monkeypatch, tmp_path, header, expected_delay
):
    clock = [1000.0]
    monkeypatch.setattr(transport.time, "time", lambda: clock[0])
    monkeypatch.setattr(
        transport.time, "sleep", lambda delay: clock.__setitem__(0, clock[0] + delay)
    )
    headers = Message()
    if header is not None:
        headers["Retry-After"] = header
    calls = []

    def opener(*args, **kwargs):
        calls.append(clock[0])
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                args[0].full_url, 503, "busy", headers, io.BytesIO(b"original 503 body")
            )
        return Response(b"success")

    monkeypatch.setattr(transport.urllib.request, "urlopen", opener)
    state = tmp_path / "shared"
    receipt = {}
    with pytest.raises(urllib.error.HTTPError) as error:
        with transport.open_horizons(
            request(),
            context=ssl.create_default_context(),
            state_path=state,
            receipt=receipt,
        ):
            pytest.fail("503 cannot become a successful response")
    assert error.value.read() == b"original 503 body"
    assert calls == [1000.0]  # This layer never starts an automatic retry.
    with transport.open_horizons(
        request(), context=ssl.create_default_context(), state_path=state
    ) as response:
        assert response.read() == b"success"
    assert calls == [1000.0, 1000.0 + expected_delay]
    assert receipt["not_before_next_request_unix_seconds"] == 1000.0 + expected_delay


def test_insecure_context_is_rejected_before_a_network_call(monkeypatch, tmp_path):
    monkeypatch.setattr(
        transport.urllib.request,
        "urlopen",
        lambda *a, **k: pytest.fail("network called"),
    )
    context = ssl._create_unverified_context()
    with pytest.raises(ValueError, match="Unverified"):
        with transport.open_horizons(
            request(), context=context, state_path=tmp_path / "state"
        ):
            pass


def test_user_agent_identifies_version_and_public_contact(monkeypatch, tmp_path):
    agents = []

    def opener(value, **kwargs):
        agents.append(value.get_header("User-agent"))
        return Response(b"ok")

    monkeypatch.setattr(transport.urllib.request, "urlopen", opener)
    with transport.open_horizons(
        request(), context=ssl.create_default_context(), state_path=tmp_path / "state"
    ) as response:
        response.read()
    assert agents == [
        "FateBridge-reference/1.0 (+https://github.com/thomas-yanxin/FateBridge/issues)"
    ]


def test_retry_after_http_date_is_honored():
    assert transport.retry_after_seconds("Thu, 01 Jan 1970 00:20:00 GMT", 1000) == 200
