"""Kurgusal banka servisi.  Çalıştırma:  uvicorn mock_bank:app --port 8001
Başlangıçta ~45 günlük geçmiş işlem üretir, ardından her 15 sn'de yeni bir
elektronik harcama 'düşer'. /simulate ile anında işlem oluşturulabilir."""
import asyncio
import random
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI

MERCHANTS = [  # (işyeri, min, max)
    ("MİGROS", 80, 900), ("A101", 50, 500), ("BİM", 40, 400), ("STARBUCKS", 90, 250),
    ("YEMEKSEPETİ", 150, 600), ("UBER", 70, 300), ("NETFLIX", 199, 199),
    ("ENERJİSA", 450, 1100), ("ECZANE ŞİFA", 60, 400), ("ZARA", 500, 2500),
    ("SPOTIFY", 60, 60), ("İETT", 20, 150), ("OPET", 500, 1500), ("CINEMAXIMUM", 150, 450),
]
TX: list[dict] = []


def _new_tx(day=None):
    name, lo, hi = random.choice(MERCHANTS)
    TX.append({"id": len(TX) + 1, "date": (day or date.today()).isoformat(),
               "merchant": name, "amount": round(random.uniform(lo, hi), 2), "currency": "TRY"})
    return TX[-1]


async def _producer():
    while True:
        await asyncio.sleep(15)
        _new_tx()


@asynccontextmanager
async def lifespan(app):
    random.seed(7)
    today = date.today()
    for offset in range(45, 0, -1):
        for _ in range(random.choice([0, 1, 1, 2])):
            _new_tx(today - timedelta(days=offset))
    task = asyncio.create_task(_producer())
    yield
    task.cancel()


app = FastAPI(title="Mock Banka API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "tx_count": len(TX)}


@app.get("/transactions")
def transactions(after_id: int = 0):
    return {"transactions": [t for t in TX if t["id"] > after_id]}


@app.post("/simulate")
def simulate():
    return _new_tx()
