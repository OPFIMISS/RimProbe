import json
import socket
import threading
import unittest

from rimprobe.errors import ProbeError
from rimprobe.protocol import MAX_MESSAGE_BYTES, request


class ProtocolTests(unittest.TestCase):
    def serve_once(self, transform):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]

        def serve():
            try:
                with listener:
                    connection, _ = listener.accept()
                    with connection:
                        connection.settimeout(2)
                        with connection.makefile("rb") as stream:
                            received = json.loads(stream.readline())
                        response = transform(received)
                        try:
                            connection.sendall(response)
                        except ConnectionError:
                            pass
            finally:
                listener.close()

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 3)
        return port

    @staticmethod
    def envelope(received, **updates):
        response = {"protocol": 1, "id": received["id"], "session_id": received["session_id"],
                    "ok": True, "result": {"map_ready": True, "tick": 42}}
        response.update(updates)
        return json.dumps(response).encode() + b"\n"

    def test_round_trip(self):
        port = self.serve_once(self.envelope)
        self.assertEqual(request(port, "session", "token", "get_state")["tick"], 42)

    def test_rejects_wrong_session(self):
        port = self.serve_once(lambda received: self.envelope(received, session_id="another"))
        with self.assertRaises(ProbeError) as raised:
            request(port, "session", "token", "get_state")
        self.assertEqual(raised.exception.code, "response_mismatch")

    def test_rejects_wrong_request_id(self):
        port = self.serve_once(lambda received: self.envelope(received, id="old"))
        with self.assertRaises(ProbeError) as raised:
            request(port, "session", "token", "get_state")
        self.assertEqual(raised.exception.code, "response_mismatch")

    def test_propagates_structured_agent_error(self):
        port = self.serve_once(lambda received: self.envelope(
            received, ok=False, error={"code": "main_thread_timeout", "message": "busy"}))
        with self.assertRaises(ProbeError) as raised:
            request(port, "session", "token", "get_state")
        self.assertEqual(raised.exception.code, "main_thread_timeout")

    def test_rejects_invalid_json(self):
        port = self.serve_once(lambda received: b"not-json\n")
        with self.assertRaises(ProbeError) as raised:
            request(port, "session", "token", "get_state")
        self.assertEqual(raised.exception.code, "invalid_response")

    def test_rejects_oversized_response(self):
        port = self.serve_once(lambda received: b"x" * (MAX_MESSAGE_BYTES + 1))
        with self.assertRaises(ProbeError) as raised:
            request(port, "session", "token", "get_state")
        self.assertEqual(raised.exception.code, "response_too_large")


if __name__ == "__main__":
    unittest.main()
