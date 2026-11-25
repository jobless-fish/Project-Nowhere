"""One-time Gmail authorization (read-only). Run on your own PC:

    set GMAIL_CLIENT_ID=...   set GMAIL_CLIENT_SECRET=...   (an OAuth "Desktop app" client from your own Google Cloud project)
    python scripts/gmail_auth.py

A browser opens, you approve `gmail.readonly`, and the refresh token is PRINTED (never written to a file). Put it in the environment variable
GMAIL_REFRESH_TOKEN. Revoke any time at https://myaccount.google.com/permissions.
"""
import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser

import httpx

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def main() -> int:
    cid, sec = os.getenv("GMAIL_CLIENT_ID"), os.getenv("GMAIL_CLIENT_SECRET")
    if not (cid and sec):
        print("GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET 환경변수를 먼저 설정해 주세요.")
        return 1
    got, state = {}, secrets.token_urlsafe(16)

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers()
            self.wfile.write("인증이 끝났어요. 이 창을 닫고 터미널로 돌아가세요.".encode())
        def log_message(self, *a): pass

    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    redirect = f"http://127.0.0.1:{srv.server_port}"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(
        {"client_id": cid, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE, "access_type": "offline", "prompt": "consent", "state": state})
    t = threading.Thread(target=srv.handle_request); t.start()
    print("브라우저에서 허용해 주세요:\n", url); webbrowser.open(url); t.join(300)
    if got.get("state") != state or "code" not in got:
        print("인증이 완료되지 않았어요."); return 1
    r = httpx.post("https://oauth2.googleapis.com/token", data={"code": got["code"], "client_id": cid, "client_secret": sec, "redirect_uri": redirect, "grant_type": "authorization_code"})
    tok = r.json().get("refresh_token")
    if not tok:
        print("refresh token을 받지 못했어요:", r.status_code); return 1
    print("\nGMAIL_REFRESH_TOKEN =", tok, "\n(파일에 저장하지 말고 환경변수로만 설정하세요.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
