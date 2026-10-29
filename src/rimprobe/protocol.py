import json
import socket
import time
import uuid

from .errors import ProbeError

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 65536


def request(port: int, session_id: str, token: str, command: str, timeout: float = 5, parameters: dict | None = None) -> dict:
    deadline = time.monotonic() + timeout
    request_id = uuid.uuid4().hex
    payload = {
        "protocol": PROTOCOL_VERSION,
        "id": request_id,
        "session_id": session_id,
        "token": token,
        "command": command,
    }
    if parameters is not None:
        payload["parameters"] = parameters
    encoded = json.dumps(payload).encode("utf-8") + b"\n"
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ProbeError("request_too_large", "Request exceeds the protocol limit.")
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(encoded)
            buffer = bytearray()
            while b"\n" not in buffer:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Agent response deadline expired.")
                connection.settimeout(remaining)
                chunk = connection.recv(min(4096, MAX_MESSAGE_BYTES + 1 - len(buffer)))
                if not chunk:
                    raise ProbeError("bridge_disconnected", "Agent disconnected before a complete response.")
                buffer.extend(chunk)
                if len(buffer) > MAX_MESSAGE_BYTES:
                    raise ProbeError("response_too_large", "Agent response exceeds the protocol limit.")
    except (OSError, TimeoutError) as error:
        raise ProbeError("bridge_unreachable", str(error)) from error
    try:
        response = json.loads(buffer.split(b"\n", 1)[0])
    except (UnicodeError, ValueError) as error:
        raise ProbeError("invalid_response", "Agent returned invalid JSON.") from error
    if not isinstance(response, dict):
        raise ProbeError("invalid_response", "Agent response must be an object.")
    if (
        response.get("protocol") != PROTOCOL_VERSION
        or response.get("id") != request_id
        or not isinstance(response.get("session_id"), str)
        or response["session_id"] != session_id
    ):
        raise ProbeError("response_mismatch", "Agent response does not match this request/session.")
    if response.get("ok") is not True:
        error = response.get("error")
        if not isinstance(error, dict):
            raise ProbeError("invalid_response", "Agent omitted the structured error.")
        raise ProbeError(str(error.get("code", "agent_error")), str(error.get("message", "Agent failed.")))
    if not isinstance(response.get("result"), dict):
        raise ProbeError("invalid_response", "Agent result must be an object.")
    return response["result"]
