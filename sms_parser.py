"""Türk bankalarının harcama bildirim SMS'lerini çözümler.

Bankaların metinleri farklıdır; bu yüzden sabit bir kalıp yerine şu yöntem kullanılır:
tutar bağlama göre puanlanarak seçilir, gelir/gider yönü anahtar kelimelerden belirlenir,
işyeri adı önce bilinen kalıplardan, bulunamazsa büyük harfli sözcük öbeğinden alınır."""
import re

import textparse as tp

INCOME_WORDS = ("hesabiniza", "kartiniza", "yatmistir", "yatirilmistir", "gelmistir", "gecmistir",
                "maas", "alacak", "gelen fast", "gelen eft", "gelen havale", "para geldi", "aktarilmistir")
EXPENSE_WORDS = ("hesabinizdan", "harcama", "alisveris", "odeme", "cekim", "gonderildi", "borclandir",
                 "islem gerceklesti", "islem gerceklesmistir", "provizyon", "pos", "satis")
REFUND_WORDS = ("iade", "iptal", "ters islem", "red")


def has(n, word):
    """Tam sözcük araması: 'kredi' içindeki 'red' yüzünden iade sanılmasını önler."""
    return re.search(rf"\b{re.escape(word)}\b", n) is not None

# işyeri adı geçmeyen para girişi SMS'leri için anlamlı etiketler
INCOME_LABELS = (("maas", "Maaş"), ("gelen fast", "Gelen FAST"), ("fast", "Gelen FAST"),
                 ("eft", "Gelen EFT"), ("havale", "Gelen havale"), ("iade", "İade"))

CARD_RE = re.compile(r"(?:\*+|x+|X+)?(\d{4})\s*(?:nolu|no'?lu|numarali|numaralı)", re.IGNORECASE)
CARD_RE2 = re.compile(r"(?:\*{2,}|x{2,}|X{2,})\s*(\d{4})")
# "MIGROS'ta", "BIM'den", "A101 MAGAZA'da" gibi ek almış işyeri adları
SUFFIX_RE = re.compile(rf"([{tp.UPPER}][{tp.UPPER}0-9&.\- ]{{2,30}}?)\s*['’]?\s*(?:d[ae]|t[ae])n?\b")
DASH_RE = re.compile(rf"[-–]\s*([{tp.UPPER}][{tp.UPPER}0-9&.\- ]{{2,30}}?)\s*[-–]")


def _merchant(text, near):
    for rx in (DASH_RE, SUFFIX_RE):
        for m in rx.finditer(text):
            name = " ".join(m.group(1).split()).strip(".-")
            words = [w for w in name.split() if w.upper() not in tp.STOP_WORDS]
            if words and len(" ".join(words)) >= 3:
                return " ".join(words)
    return tp.find_caps_name(text, near)


def parse(text):
    """{'amount','date','merchant','card','kind','ok'} döner.
    kind: 'expense' | 'income' | 'refund'. 'ok' alanı tutarın bulunup bulunmadığını belirtir."""
    text = (text or "").strip()
    n = tp.norm(text)
    amount = tp.find_amount(text)
    near = None
    if amount is not None:
        m = tp.AMOUNT_RE.search(text)
        near = m.start() if m else None

    if any(has(n, w) for w in REFUND_WORDS):
        kind = "refund"
    else:
        inc = sum(has(n, w) for w in INCOME_WORDS)
        exp = sum(has(n, w) for w in EXPENSE_WORDS)
        kind = "income" if inc > exp else "expense"

    card = None
    for rx in (CARD_RE, CARD_RE2):
        m = rx.search(text)
        if m:
            card = m.group(1)
            break

    merchant = _merchant(text, near)
    if not merchant and kind == "income":
        merchant = next((lbl for key, lbl in INCOME_LABELS if has(n, key)), "Gelen para")

    return {"amount": amount, "date": tp.find_date(text), "merchant": merchant,
            "card": card, "kind": kind, "ok": amount is not None}
