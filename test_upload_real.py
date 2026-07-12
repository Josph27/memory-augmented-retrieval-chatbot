import requests


def test_upload():
    # Login
    session = requests.Session()
    r = session.post("http://localhost:8000/login", data={"username": "local", "password": "local"})
    print("Login:", r.status_code)

    # Simulate uploadFile endpoint
    # We need a valid session_id!
    # Let's get the valid session_id from the browser log
    with open("logs/browser.log", "r") as f:
        lines = f.readlines()

    session_id = None
    for line in reversed(lines):
        if "RESUME_THREAD" in line:
            # Format: RESUME_THREAD: thread_id session_id
            parts = line.split("RESUME_THREAD:")[1].strip().split()
            session_id = parts[1]
            break

    if not session_id:
        print("Could not find session_id in logs!")
        return

    print("Found session_id in logs:", session_id)
    r = session.post(
        f"http://localhost:8000/project/file?session_id={session_id}",
        files={"file": ("test.txt", b"Hello World", "text/plain")},
    )
    print("Upload status:", r.status_code)
    print("Upload response:", r.text)


if __name__ == "__main__":
    test_upload()
