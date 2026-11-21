"""Fake KiCad IPC socket that replays recorded request/response exchanges.

The fake server binds a pynng ``Rep0`` socket at an ``ipc://`` path, receives
the raw ``ApiRequest`` envelopes produced by kipy, and returns the raw
``ApiResponse`` envelopes captured by ``record_ipc_fixture.py``.  No live KiCad
instance is needed.

The recorded exchanges are replayed in order.  By default the request payloads
are also verified, so a test fails if the MCP tool changes the IPC command it
sends rather than merely returning a different response.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import pynng
from kipy.proto.common import ApiRequest, ApiResponse, ApiStatusCode

from tests.test_harness.record_ipc_fixture import Exchange


@dataclass(frozen=True)
class ServedRequest:
    """A request observed by the fake server and its response."""

    request: ApiRequest
    response: ApiResponse


class FakeKiCadSocket:
    """Replay recorded KiCad IPC exchanges over a real fake socket."""

    def __init__(
        self,
        exchanges: list[Exchange],
        *,
        socket_path: str | Path | None = None,
        verify_requests: bool = True,
        recv_timeout_ms: int = 100,
    ) -> None:
        if not exchanges:
            raise ValueError("at least one recorded exchange is required")

        self._exchanges = list(exchanges)
        self._verify_requests = verify_requests
        self._recv_timeout_ms = recv_timeout_ms
        self._index = 0
        self._served: list[ServedRequest] = []
        self._mismatches: list[str] = []
        self._errors: list[str] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: pynng.Rep0 | None = None

        if socket_path is None:
            self._directory: Path | None = Path(tempfile.mkdtemp(prefix="kicad-fake-"))
            self._socket_path = self._directory / "api.sock"
        else:
            self._directory = None
            self._socket_path = Path(socket_path)

    @property
    def socket_path(self) -> Path:
        return self._socket_path

    @property
    def socket_url(self) -> str:
        return f"ipc://{self._socket_path}"

    @property
    def served(self) -> list[ServedRequest]:
        return list(self._served)

    @property
    def mismatches(self) -> list[str]:
        return list(self._mismatches)

    @property
    def errors(self) -> list[str]:
        return list(self._errors)

    @property
    def remaining(self) -> int:
        return len(self._exchanges) - self._index

    def start(self) -> Self:
        """Bind the socket and start the replay thread."""
        if self._socket is not None:
            raise RuntimeError("fake KiCad socket is already started")

        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()

        self._socket = pynng.Rep0(
            listen=self.socket_url,
            recv_timeout=self._recv_timeout_ms,
            send_timeout=2000,
        )
        self._thread = threading.Thread(
            target=self._serve,
            name="fake-kicad-ipc",
            daemon=True,
        )
        self._thread.start()

        deadline = time.monotonic() + 5.0
        while not self._socket_path.is_socket():
            if time.monotonic() >= deadline:
                self.close()
                raise RuntimeError(
                    f"fake KiCad socket was not created at {self._socket_path}"
                )
            time.sleep(0.01)

        return self

    def close(self) -> None:
        """Stop the replay thread and remove the socket."""
        self._stop.set()

        if self._socket is not None:
            self._socket.close()
            self._socket = None

        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

        if self._socket_path.exists():
            self._socket_path.unlink()

        if self._directory is not None:
            shutil.rmtree(self._directory, ignore_errors=True)
            self._directory = None

    def assert_complete(self) -> None:
        """Fail if the tool did not consume every recorded exchange cleanly."""
        if self._errors:
            raise AssertionError("fake KiCad socket errors: " + "; ".join(self._errors))
        if self._mismatches:
            raise AssertionError(
                "fake KiCad request mismatch: " + "; ".join(self._mismatches)
            )
        if self._index != len(self._exchanges):
            raise AssertionError(
                f"fake KiCad socket served {self._index} of "
                f"{len(self._exchanges)} recorded exchanges"
            )

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _serve(self) -> None:
        assert self._socket is not None

        while not self._stop.is_set():
            try:
                message = self._socket.recv_msg()
            except pynng.exceptions.Timeout:
                continue
            except pynng.exceptions.Closed:
                break
            except Exception as exc:  # noqa: BLE001 - surfaced via assert_complete
                self._errors.append(f"receive failed: {type(exc).__name__}: {exc}")
                break

            try:
                reply = self._reply_for(bytes(message.bytes))
            except Exception as exc:  # noqa: BLE001 - surfaced via assert_complete
                self._errors.append(
                    f"request handling failed: {type(exc).__name__}: {exc}"
                )
                break

            try:
                self._socket.send(reply)
            except pynng.exceptions.Closed:
                break
            except Exception as exc:  # noqa: BLE001 - surfaced via assert_complete
                self._errors.append(f"send failed: {type(exc).__name__}: {exc}")
                break

    def _reply_for(self, raw_request: bytes) -> bytes:
        request = ApiRequest.FromString(raw_request)

        if self._index >= len(self._exchanges):
            self._errors.append(
                f"unexpected request {request.message.TypeName()!r} after all "
                f"{len(self._exchanges)} recorded exchanges"
            )
            return _error_response(request, "fake KiCad socket has no recording left")

        exchange = self._exchanges[self._index]
        expected_request = ApiRequest.FromString(exchange.request)
        expected_response = ApiResponse.FromString(exchange.response)

        expected_type = expected_request.message.TypeName()
        actual_type = request.message.TypeName()
        if expected_type != actual_type:
            self._mismatches.append(
                f"exchange {self._index}: expected {expected_type}, got {actual_type}"
            )
        elif (
            self._verify_requests
            and request.message.value != expected_request.message.value
        ):
            self._mismatches.append(
                f"exchange {self._index}: {actual_type} payload differs"
            )

        self._served.append(ServedRequest(request=request, response=expected_response))
        self._index += 1
        return exchange.response


def _error_response(request: ApiRequest, error_message: str) -> bytes:
    response = ApiResponse()
    response.header.kicad_token = request.header.kicad_token
    response.status.status = ApiStatusCode.AS_INTERNAL_ERROR
    response.status.error_message = error_message
    return response.SerializeToString()
