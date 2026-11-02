"""Ana uygulamanın mock banka servisine bağlanan istemcisi."""
import os
import requests
import analyzer as an
import database as db

BASE_URL = os.getenv("BANK_API_URL", "http://127.0.0.1:8001")


def sync():
    """Henüz alınmamış banka işlemlerini çeker, kategorileyip kaydeder. Eklenen sayıyı döner."""
    r = requests.get(f"{BASE_URL}/transactions", params={"after_id": db.last_bank_id()}, timeout=5)
    r.raise_for_status()
    added = 0
    for tx in r.json()["transactions"]:
        cat = db.category_id(an.guess_category(tx["merchant"]))
        if db.add_expense(tx["amount"], tx["date"], tx["merchant"], cat, "bank", str(tx["id"])):
            added += 1
    return added


def simulate():
    requests.post(f"{BASE_URL}/simulate", timeout=5).raise_for_status()
