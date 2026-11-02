"""Banka hesap hareketi / kart ekstresi (CSV, XLSX) içe aktarma.

Bankalar farklı sütun adları ve sayı biçimleri kullandığından: başlık satırı ve sütunlar otomatik
bulunur, kullanıcı arayüzde düzeltebilir. Aynı ekstre tekrar yüklenirse kayıtlar çiftlenmez."""
import csv
import hashlib
import io
import re
from collections import Counter
from datetime import date, datetime

import analyzer as an
import database as db

_TR = str.maketrans({"İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
                     "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c"})

SYN = {  # alan -> kabul edilen başlıklar (ASCII, küçük harf, öncelik sırasıyla)
    "date": ["islem tarihi", "tarih", "islem tarih", "tarih saat", "islem zamani", "valor", "date"],
    "desc": ["aciklama", "islem aciklamasi", "isyeri", "isyeri adi", "uye isyeri", "detay", "islem",
             "description"],
    "balance": ["bakiye", "kalan bakiye", "son bakiye", "hesap bakiyesi", "balance"],
    "debit": ["borc", "borc tutari", "cikis", "gider", "debit"],
    "credit": ["alacak", "alacak tutari", "giris", "gelir", "credit"],
    "amount": ["tutar", "islem tutari", "tutar tl", "harcama tutari", "amount"],
}
CONTAINS = {"date": "tarih", "desc": "aciklama", "balance": "bakiye", "debit": "borc",
            "credit": "alacak", "amount": "tutar"}
ORDER = ["date", "desc", "balance", "debit", "credit", "amount"]


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(s or "").translate(_TR).lower()).split())


def guess_mapping(headers):
    """{'date': sütun_no|None, ...}"""
    hn = [norm(h) for h in headers]
    taken, res = set(), {}
    for key in ORDER:
        found = None
        for syn in SYN[key]:                       # 1) tam eşleşme
            for i, h in enumerate(hn):
                if h == syn and i not in taken:
                    found = i
                    break
            if found is not None:
                break
        if found is None:                          # 2) içerir
            for i, h in enumerate(hn):
                if CONTAINS[key] in h and i not in taken and not ("borc" in h and "alacak" in h):
                    found = i
                    break
        if found is not None:
            taken.add(found)
        res[key] = found
    return res


# ---------- dosya okuma ----------
def read_table(path):
    ext = path.lower().rsplit(".", 1)[-1]
    if ext in ("xlsx", "xlsm"):
        try:
            import openpyxl
        except ImportError:
            raise ValueError("Excel dosyaları için şu komutu çalıştırın:  pip install openpyxl")
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        return [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    if ext == "xls":
        raise ValueError("Eski .xls biçimi desteklenmiyor. Excel'de 'Farklı Kaydet' ile .xlsx veya CSV yapın.")
    if ext == "pdf":
        raise ValueError("PDF desteklenmiyor. Bankanızdan Excel veya CSV olarak dışa aktarın.")
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = text.splitlines()
    delim = max([";", ",", "\t", "|"], key=lambda d: sum(l.count(d) for l in lines[:30]))
    return list(csv.reader(io.StringIO(text), delimiter=delim))


def find_header(rows):
    for i, r in enumerate(rows[:40]):
        m = guess_mapping([str(c or "") for c in r])
        if m["date"] is not None and (m["amount"] is not None or m["debit"] is not None
                                      or m["credit"] is not None):
            return i
    return None


def load(path):
    """(başlıklar, veri satırları, otomatik sütun eşleşmesi)"""
    rows = read_table(path)
    hi = find_header(rows)
    if hi is None:
        hi = next((i for i, r in enumerate(rows) if any(str(c or "").strip() for c in r)), None)
        if hi is None:
            raise ValueError("Dosya boş görünüyor.")
    headers = [str(c or "").strip() for c in rows[hi]]
    data = [list(r) for r in rows[hi + 1:] if any(str(c or "").strip() for c in r)]
    return headers, data, guess_mapping(headers)


# ---------- değer ayrıştırma ----------
def parse_date(v):
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v or "").strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)", s)
        if not m:
            return None
        d, mo, y = map(int, m.groups())
        y += 2000 if y < 100 else 0
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse_amount(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).upper().replace("TL", "").replace("TRY", "").replace("₺", "")
    s = s.replace(" ", "").replace(" ", "")
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-"):
        neg, s = True, s[:-1]
    if s.startswith("-"):
        neg, s = True, s[1:]
    elif s.startswith("+"):
        s = s[1:]
    if not re.fullmatch(r"[\d.,]+", s):
        return None
    if "," in s and "." in s:                      # son ayırıcı ondalıktır
        i = max(s.rfind(","), s.rfind("."))
        s = re.sub(r"[.,]", "", s[:i]) + "." + s[i + 1:]
    elif "," in s:
        s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 2 or len(parts[1]) == 3:   # 1.234 -> binlik ayırıcı
            s = s.replace(".", "")
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def _is_card_payment(n):
    return ("kart" in n or n.startswith("kk ")) and ("odeme" in n or "borc" in n)


# ---------- ayrıştırma ----------
def parse_rows(rows, mapping, mode="account", skip_cards=True):
    """mode: 'account' (+ gelir / - gider) veya 'card' (+ harcama / - ödeme-iade).
    Dönüş: {'records': [...], 'balance': son bakiye|None}"""
    seen, records, bals = Counter(), [], []
    for r in rows:
        def get(k):
            i = mapping.get(k)
            return r[i] if i is not None and i < len(r) else None

        d = parse_date(get("date"))
        if not d:
            continue                                # alt toplam / açıklama satırları
        desc = " ".join(str(get("desc") or "").split())
        n = norm(desc)
        debit, credit, amt = parse_amount(get("debit")), parse_amount(get("credit")), parse_amount(get("amount"))
        if mapping.get("debit") is not None or mapping.get("credit") is not None:
            if debit:
                kind, val = "expense", abs(debit)
            elif credit:
                kind, val = "income", abs(credit)
            else:
                continue
        elif amt:
            kind, val = ("income" if amt > 0 else "expense", abs(amt)) if mode == "account" else ("expense", amt)
        else:
            continue
        if mode == "card" and kind == "income":     # kart ekstresinde alacak = iade/ödeme
            kind, val = "expense", -val

        reason = None
        if mode == "account" and "virman" in n and skip_cards:
            reason = "Hesaplar arası virman"
        elif mode == "account" and kind == "expense" and skip_cards and _is_card_payment(n):
            reason = "Kart borcu ödemesi"
        elif mode == "card" and val < 0 and ("odeme" in n or "tahsilat" in n or "borc" in n):
            reason = "Kart borcu ödemesi"
        key = f"{kind}|{d}|{n}|{val:.2f}"
        seen[key] += 1
        bal = parse_amount(get("balance"))
        if bal is not None:
            bals.append((d, bal))
        records.append({"date": d, "desc": desc, "amount": val, "kind": "skip" if reason else kind,
                        "reason": reason or "", "hash": hashlib.sha1(f"{key}|{seen[key]}".encode()).hexdigest()})
    balance = None
    if bals:                                        # en yeni satırın bakiyesi (dosya yeni→eski de olabilir)
        newest_first = len(bals) > 1 and bals[0][0] > bals[-1][0]
        balance = bals[0][1] if newest_first else bals[-1][1]
    return {"records": records, "balance": balance}


def import_records(records, source="ekstre"):
    res = {"expenses": 0, "incomes": 0, "duplicates": 0, "skipped": 0}
    for r in records:
        if r["kind"] == "skip":
            res["skipped"] += 1
        elif r["kind"] == "expense":
            cid = db.category_id(an.guess_category(r["desc"]))
            ok = db.add_expense(r["amount"], r["date"], r["desc"], cid, source, tx_hash=r["hash"])
            res["expenses" if ok else "duplicates"] += 1
        else:
            ok = db.add_income(r["amount"], r["date"], r["desc"], source, tx_hash=r["hash"])
            res["incomes" if ok else "duplicates"] += 1
    return res
