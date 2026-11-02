"""Kaynaklar arası mutabakat: aynı harcamanın iki kez sayılmasını önler.

Gerçek bir banka API'si olmadığı için aynı işlem birden çok yoldan girebilir:
SMS anında gelir, fiş aynı gün okutulur, ekstre ise ay sonunda yüklenir. Bu modül
bu kayıtları eşleştirip hangisinin asıl kayıt sayılacağına karar verir."""
from datetime import date
from difflib import SequenceMatcher

import database as db
import textparse as tp

# Hangi kaynak daha güvenilir: ekstre bankanın resmi kaydıdır, en üstte yer alır.
AUTHORITY = {"ekstre": 4, "bank": 3, "sms": 2, "ocr": 1, "manual": 0}
SOURCE_TR = {"ekstre": "Ekstre", "bank": "Demo", "sms": "SMS", "ocr": "Fiş", "manual": "Manuel"}
DAY_TOLERANCE = 3          # kart harcaması ekstreye 1-3 gün gecikmeli düşebilir
AMOUNT_TOLERANCE = 0.01


def _similar(a, b):
    """İşyeri adlarının benzerliği (0-1). 'MIGROS ANKARA' ile 'MİGROS' yüksek puan alır."""
    x, y = tp.norm(a), tp.norm(b)
    if not x or not y:
        return 0.0
    if x in y or y in x:
        return 1.0
    tx, ty = set(x.split()), set(y.split())
    if tx & ty:
        return max(0.7, len(tx & ty) / max(len(tx), len(ty)))
    return SequenceMatcher(None, x, y).ratio()


def _score(a, b):
    """Aynı işlem olma olasılığı. Tutar eşitliği ön koşuldur; tarih ve ad yakınlığı puanı belirler."""
    gap = abs((date.fromisoformat(a["date"]) - date.fromisoformat(b["date"])).days)
    sim = _similar(a["description"], b["description"])
    score = 0.45 + (0.25 if gap == 0 else 0.15 if gap <= 1 else 0.0)
    score += 0.30 * sim
    return min(score, 0.99), gap, sim


def find_duplicates(month=None, min_score=0.55):
    """Farklı kaynaklardan gelen, aynı işlem olması muhtemel kayıt çiftlerini bulur.
    Her kayıt en fazla bir çiftte yer alır; en güçlü eşleşmeler önce alınır."""
    rows = [e for e in db.list_expenses(month, limit=2000) if e["amount"] > 0]
    pairs = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["source"] == b["source"]:          # aynı kaynaktan iki kayıt gerçekten iki işlemdir
                continue
            if abs(a["amount"] - b["amount"]) > AMOUNT_TOLERANCE:
                continue
            if abs((date.fromisoformat(a["date"]) - date.fromisoformat(b["date"])).days) > DAY_TOLERANCE:
                continue
            score, gap, sim = _score(a, b)
            if score < min_score:
                continue
            keep, drop = sorted((a, b), key=lambda r: AUTHORITY.get(r["source"], 0), reverse=True)
            pairs.append({"keep": keep, "drop": drop, "score": score, "gap": gap, "similar": sim})
    pairs.sort(key=lambda p: -p["score"])
    used, out = set(), []
    for p in pairs:
        ids = {p["keep"]["id"], p["drop"]["id"]}
        if ids & used:
            continue
        used |= ids
        out.append(p)
    return out


def merge(pairs):
    """Her çiftte düşük yetkili kaydı siler; asıl kayıt (genelde ekstre) kalır."""
    for p in pairs:
        db.delete_expense(p["drop"]["id"])
    return len(pairs)


def describe(p):
    """Çifti kullanıcıya tek satırda anlatır."""
    k, d = p["keep"], p["drop"]
    gap = "aynı gün" if p["gap"] == 0 else f"{p['gap']} gün fark"
    return (f"{SOURCE_TR.get(d['source'], d['source'])}: {d['description'][:28]} ({d['date']})  →  "
            f"{SOURCE_TR.get(k['source'], k['source'])}: {k['description'][:28]} ({k['date']})  ·  {gap}")
