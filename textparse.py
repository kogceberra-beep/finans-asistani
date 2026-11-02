"""SMS ve e-posta metinlerinden tutar, tarih ve işyeri adı çıkarmak için ortak yardımcılar."""
import re
from datetime import date, datetime

_TR = str.maketrans({"İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
                     "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c", "Â": "a", "â": "a"})

UPPER = "A-ZÇĞİÖŞÜ"
# "1.234,56 TL" / "245,50TL" / "99 TRY" / "1.299,00 ₺"
AMOUNT_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:TL|TRY|₺)\b",
                       re.IGNORECASE)
DATE_RE = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})(?!\d)")
ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

# tutarın yanında geçerse o tutarın asıl işlem tutarı olmadığını gösteren kelimeler
NEGATIVE_CTX = ("limit", "bakiye", "kalan", "asgari", "ekstre borc", "guncel borc", "nakit avans limiti",
                "puan", "mil", "taksit sayisi", "kampanya", "indirim", "kargo")
POSITIVE_CTX = ("tutarinda", "tutari", "harcama", "alisveris", "islem", "odeme", "toplam",
                "cekildi", "yatirildi", "gonderildi", "lik", "degerinde")
# fiş ve faturalarda asıl tutarı gösteren, ara toplamdan güçlü etiketler
STRONG_CTX = ("genel toplam", "odenecek", "toplam tutar", "tahsil edilen", "odenen tutar",
              "islem tutari", "tutar tl", "net tutar")

STOP_WORDS = {
    "TL", "TRY", "KK", "KKT", "FAST", "EFT", "ATM", "POS", "SMS", "IBAN", "VKN", "TCKN", "TR", "AS", "LTD",
    "STI", "ÜYE", "İŞYERİ", "KREDİ", "KARTI", "KART", "BANKA", "BANKASI", "HESAP", "HESABINIZDAN",
    "HESABINIZA", "SAYIN", "MÜŞTERİMİZ", "BİLGİ", "DETAY", "TUTARINDA", "TUTARI", "İŞLEM", "HARCAMA",
    "ALIŞVERİŞ", "GERÇEKLEŞMİŞTİR", "YAPILMIŞTIR", "NOLU", "NUMARALI", "İLE", "VE", "ADET", "TAKSİT",
    "LİMİT", "BAKİYE", "TOPLAM", "TARİH", "SAAT", "NO", "REF", "ONAY", "KODU", "WWW", "COM", "AŞ",
}


def norm(s):
    """Türkçe harfleri sadeleştirip küçük harfe çevirir; karşılaştırma için kullanılır."""
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(s or "").translate(_TR).lower()).split())


def to_float(s):
    """'1.234,56' -> 1234.56 ; '245,50' -> 245.5 ; '1,234.56' -> 1234.56  (son ayırıcı ondalıktır)."""
    s = str(s).replace(" ", "")
    i = max(s.rfind(","), s.rfind("."))
    if i == -1:
        return float(s)
    frac = s[i + 1:]
    if len(frac) == 3:                       # 1.234 -> binlik ayırıcı, ondalık yok
        return float(re.sub(r"[.,]", "", s))
    return float(re.sub(r"[.,]", "", s[:i]) + "." + frac)


def find_amount(text):
    """Metindeki en olası işlem tutarını döner; limit/bakiye gibi tutarları eler."""
    best, best_score = None, -99.0
    for m in AMOUNT_RE.finditer(text or ""):
        try:
            val = to_float(m.group(1))
        except ValueError:
            continue
        if val <= 0:
            continue
        # etiket, tutarla aynı satırda olur: önceki satırlara bakmak yanlış eşleşme üretir
        line_start = (text or "").rfind("\n", 0, m.start()) + 1
        before = norm(text[max(line_start, m.start() - 60):m.start()])
        after = norm(text[m.end():m.end() + 25])
        score = 0.0
        if any(w in before for w in NEGATIVE_CTX) or any(w in after for w in NEGATIVE_CTX):
            score -= 10
        if any(w in before for w in STRONG_CTX):
            score += 6
        elif any(w in before or w in after for w in POSITIVE_CTX):
            score += 3
        score -= m.start() / 10000.0         # eşitlikte metinde önce geçen kazansın
        if score > best_score:
            best, best_score = val, score
    # yalnızca limit/bakiye/asgari tutar içeren bilgilendirme mesajlarında işlem tutarı yoktur
    return best if best_score > -5 else None


def find_date(text, default_today=True):
    """gg.aa.yyyy / gg/aa/yy / yyyy-aa-gg biçimlerini tarar."""
    t = text or ""
    m = ISO_RE.search(t)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = DATE_RE.search(t)
        if not m:
            return date.today().isoformat() if default_today else None
        d, mo, y = map(int, m.groups())
        y += 2000 if y < 100 else 0
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return date.today().isoformat() if default_today else None


def find_caps_name(text, near=None):
    """Büyük harfle yazılmış işyeri adını bulur (Türk banka SMS'lerinde yaygın kalıp)."""
    tokens = list(re.finditer(rf"[{UPPER}][{UPPER}0-9&'’.\-]{{1,}}", text or ""))
    runs, cur = [], []
    for i, tk in enumerate(tokens):
        if cur and tk.start() - tokens[i - 1].end() > 2:   # araya başka şey girmişse yeni grup
            runs.append(cur)
            cur = []
        cur.append(tk)
    if cur:
        runs.append(cur)
    best, best_score = None, -99
    for run in runs:
        words = [t.group(0).strip(".'’-") for t in run]
        words = [w for w in words if len(w) >= 2 and w.upper() not in STOP_WORDS]
        if not words:
            continue
        name = " ".join(words)
        if len(name) < 3 or name.isdigit():
            continue
        score = min(len(words), 4)
        if near is not None:                               # tutara yakın olan ad daha olasıdır
            score -= abs(run[0].start() - near) / 200.0
        if score > best_score:
            best, best_score = name, score
    return best


def strip_html(html):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", html or "")
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|h[1-6])>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
                 ("&#39;", "'")):
        s = s.replace(a, b)
    return "\n".join(ln.strip() for ln in s.splitlines() if ln.strip())


def merchant_key(text):
    """İşyeri adından marka anahtarı üretir; şubeden bağımsızdır.
    'MİGROS ANKARA' -> 'migros' ,  'A101 MAĞAZA' -> 'a101' ,  'BP PETROL' -> 'bp petrol'."""
    t = (text or "").replace("İ", "i").lower()
    words = [w for w in re.findall(r"[a-zçğıöşü0-9]+", t) if len(w) >= 2]
    if not words:
        return t.strip()
    return words[0] if len(words[0]) >= 3 else " ".join(words[:2])
