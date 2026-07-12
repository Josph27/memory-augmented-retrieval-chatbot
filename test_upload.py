import asyncio
import socketio
import aiohttp
import uuid


async def test_socket_upload():
    async with aiohttp.ClientSession() as http_session:
        # Login
        resp = await http_session.post(
            "http://localhost:8000/login", data={"username": "local", "password": "local"}
        )
        print("Login status:", resp.status)
        cookies = http_session.cookie_jar.filter_cookies("http://localhost:8000")
        cookie_header = "; ".join(f"{c.key}={c.value}" for c in cookies.values())
        print("Cookies:", cookie_header)

        session_id = str(uuid.uuid4())
        sio = socketio.AsyncClient()

        @sio.on("connect", namespace="/")
        async def on_connect():
            print("Socket connected!")

            # Now try uploading
            resp = await http_session.post(
                f"http://localhost:8000/project/file?session_id={session_id}",
                data={"file": b"hello world"},
            )
            print("Upload status:", resp.status)
            print("Upload response:", await resp.text())
            await sio.disconnect()

        @sio.on("connect_error", namespace="/")
        def on_connect_error(data):
            print("Connect Error:", data)

        print("Connecting to socket...")
        await sio.connect(
            "http://localhost:8000",
            socketio_path="/ws/socket.io",
            transports=["websocket"],
            auth={"clientType": "webapp", "sessionId": session_id, "threadId": "", "userEnv": "{}"},
            headers={"Cookie": cookie_header},
        )
        await sio.wait()


if __name__ == "__main__":
    asyncio.run(test_socket_upload())
