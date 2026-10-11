"""AnkiConnector가 SSH 터널 너머의 AnkiConnect와도 연속 호출에 성공하는지.

AnkiConnect는 응답 뒤 연결을 닫는데, SSH 터널(-L)을 거치면 Mac 쪽 소켓은 열린 채로
남는다. 클라이언트가 그 연결을 다시 쓰면 응답 없이 끊긴다 (2026-10-11 실측: 공유 세션
10회 중 5회 실패). 아래 가짜 서버는 그 동작을 흉내 낸다. 실제 Anki에는 붙지 않는다.
"""
import json
import socket
import threading

import pytest

from integrations import anki_connect


class _TunnelLikeServer:
    """연결마다 첫 요청에만 답하고, 같은 연결로 온 다음 요청은 답 없이 끊는다."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        self.connections = 0
        self.actions = []
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            self.connections += 1
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    @staticmethod
    def _read_request(conn):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(65536)
            if not chunk:
                return None
            data += chunk
        head, body = data.split(b"\r\n\r\n", 1)
        length = 0
        for line in head.split(b"\r\n")[1:]:
            name, _, value = line.partition(b":")
            if name.strip().lower() == b"content-length":
                length = int(value.strip())
        while len(body) < length:
            body += conn.recv(65536)
        return json.loads(body)

    def _serve(self, conn):
        with conn:
            payload = self._read_request(conn)
            if payload is None:
                return
            self.actions.append(payload["action"])
            body = json.dumps({"result": 6, "error": None}).encode()
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
            )
            # 터널처럼 연결은 열어 둔 채, 같은 연결로 다음 요청이 오면 답 없이 끊는다.
            self._read_request(conn)

    def close(self):
        self.sock.close()


@pytest.fixture
def tunnel_server():
    server = _TunnelLikeServer()
    yield server
    server.close()


@pytest.fixture(autouse=True)
def _block_real_anki(monkeypatch, tunnel_server):
    """conftest의 차단을 대신한다: 이 파일의 호출은 가짜 서버로만 간다."""
    monkeypatch.setattr(anki_connect, "ANKI_URL", f"http://127.0.0.1:{tunnel_server.port}")


def test_consecutive_calls_survive_connection_closed_by_tunnel(tunnel_server):
    results = [anki_connect.AnkiConnector.invoke("version") for _ in range(5)]

    assert results == [6] * 5
    assert tunnel_server.actions == ["version"] * 5


def test_each_call_opens_its_own_connection(tunnel_server):
    for _ in range(3):
        anki_connect.AnkiConnector.invoke("version")

    # 재시도로 메우지 않는다: 요청 하나에 연결 하나, 서버가 받은 요청도 정확히 3개
    assert tunnel_server.connections == 3
    assert tunnel_server.actions == ["version"] * 3
