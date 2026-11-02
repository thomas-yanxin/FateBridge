"""Coordinate the reference collectors under JPL's one-request-at-a-time rule.

This guard covers callers using this module, including separate checkouts and
processes for one OS user. Historical collectors and external programs are not
claimed to share the guard. No network request is retried here.
"""

import getpass
import io
import json
import math
import os
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from pathlib import Path

METHOD = "jpl_horizons_serial_backoff_v1"
USER_AGENT = (
    "FateBridge-reference/1.0 " "(+https://github.com/thomas-yanxin/FateBridge/issues)"
)


def default_state_path():
    identity = str(os.getuid()) if hasattr(os, "getuid") else getpass.getuser()
    return Path(tempfile.gettempdir()) / (
        "fatebridge-jpl-horizons-v1-" + identity + ".lock"
    )


@contextmanager
def locked_state(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield stream
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def retry_after_seconds(header, now):
    if header is None:
        return 0.0
    try:
        seconds = float(header)
    except ValueError:
        seconds = parsedate_to_datetime(header).timestamp() - now
    if not math.isfinite(seconds):
        raise ValueError("Invalid Retry-After")
    return max(0.0, seconds)


@contextmanager
def open_horizons(request, *, context, timeout=40, receipt=None, state_path=None):
    parsed = urllib.parse.urlsplit(request.full_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"ssd.jpl.nasa.gov", "ssd-api.jpl.nasa.gov"}
        or parsed.path != "/api/horizons.api"
        or context.verify_mode != ssl.CERT_REQUIRED
        or not context.check_hostname
    ):
        raise ValueError("Unverified or undeclared Horizons transport")
    request.add_header("User-Agent", USER_AGENT)
    receipt = receipt if receipt is not None else {}
    receipt.update(transport_method_id=METHOD, verification_disabled=False)
    started = time.time()
    with locked_state(state_path or default_state_path()) as state_file:
        encoded = state_file.read()
        state = json.loads(encoded) if encoded else {}
        not_before = float(state.get("not_before_unix_seconds", 0))
        while time.time() < not_before:
            time.sleep(max(0, min(1, not_before - time.time())))
        receipt["guard_wait_seconds"] = max(0.0, time.time() - started)

        def save(failed, retry_after=0.0):
            failures = int(state.get("consecutive_failures", 0)) + 1 if failed else 0
            delay = (
                max(min(300, 30 * 2 ** min(failures - 1, 4)), retry_after)
                if failed
                else 1
            )
            state.update(
                method_id=METHOD,
                consecutive_failures=failures,
                not_before_unix_seconds=time.time() + delay,
            )
            state_file.seek(0)
            state_file.write((json.dumps(state) + "\n").encode())
            state_file.truncate()
            state_file.flush()
            os.fsync(state_file.fileno())
            receipt["not_before_next_request_unix_seconds"] = state[
                "not_before_unix_seconds"
            ]

        try:
            with urllib.request.urlopen(
                request, context=context, timeout=timeout
            ) as response:
                receipt["network_request_performed"] = True
                yield response
        except urllib.error.HTTPError as error:
            # Consume and close the network body while holding the lock. The
            # caller can still archive the exact bytes from an in-memory error.
            with error:
                raw = error.read()
            try:
                retry_after = retry_after_seconds(
                    error.headers.get("Retry-After"), time.time()
                )
            except (ValueError, TypeError, OverflowError):
                retry_after = 0
                receipt["invalid_retry_after_header"] = error.headers.get("Retry-After")
            save(error.code in {429, 500, 502, 503, 504}, retry_after)
            receipt["network_request_performed"] = True
            raise urllib.error.HTTPError(
                error.url, error.code, error.reason, error.headers, io.BytesIO(raw)
            ) from error
        except (TimeoutError, urllib.error.URLError):
            save(True)
            raise
        else:
            save(False)
