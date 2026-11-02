"""Telefondan iletilen banka SMS'lerini karşılayan yerel servis.

Telefona kurulan ücretsiz bir 'SMS Forwarder' uygulaması, gelen SMS'i bu adrese gönderir;
kayıt doğrudan harcamaya çevrilmez, önce gelen kutusuna düşer ve kullanıcı onaylar."""
import socket
import threading

from fastapi import FastAPI, Request

import database as db
import sms_parser

app = FastAPI(title="SMS Alıcı")
_server = None


def local_ip():
    """Telefonun bağlanacağı yerel IP adresi (paket göndermez, yalnızca arayüzü seçer)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def handle(text, sender=""):
    """Ham SMS metnini çözümleyip gelen kutusuna yazar. Aynı SMS iki kez eklenmez."""
    text = (text or "").strip()
    if not text:
        return {"ok": False, "reason": "boş mesaj"}
    p = sms_parser.parse(text)
    added = db.add_inbox("sms", text, p["amount"], p["date"],
                         p["merchant"] or sender or "SMS", p["kind"])
    return {"ok": True, "saved": added, "parsed": p}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.api_route("/sms", methods=["GET", "POST"])
async def sms(request: Request):
    """JSON, form ya da düz sorgu dizesi kabul eder (forwarder uygulamaları farklı biçim gönderir)."""
    data = dict(request.query_params)
    if request.method == "POST":
        raw = await request.body()
        try:
            body = await request.json()
            if isinstance(body, dict):
                data.update(body)
        except Exception:
            try:
                form = await request.form()
                data.update({k: str(v) for k, v in form.items()})
            except Exception:
                pass
        if not data and raw:
            data["text"] = raw.decode("utf-8", "replace")
    text = next((data[k] for k in ("text", "message", "msg", "body", "content", "sms") if data.get(k)), "")
    sender = next((data[k] for k in ("from", "sender", "address", "number") if data.get(k)), "")
    return handle(text, sender)


def start(port=8002):
    """Servisi arka planda başlatır (arayüz donmasın diye ayrı iş parçacığında)."""
    global _server
    if _server is not None:
        return False
    import uvicorn
    cfg = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
    _server = uvicorn.Server(cfg)
    _server.install_signal_handlers = lambda: None
    threading.Thread(target=_server.run, daemon=True).start()
    return True


def stop():
    global _server
    if _server is not None:
        _server.should_exit = True
        _server = None
