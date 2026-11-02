"""Fiş görüntüsünden tutar / tarih / işyeri çıkarma (Tesseract OCR)."""
import re
from datetime import date

AMOUNT_RE = re.compile(r"\d{1,3}(?:[.,\s]\d{3})*[.,]\d{2}(?!\d)|\d+[.,]\d{2}(?!\d)")
DATE_RE = re.compile(r"(\d{2})[./-](\d{2})[./-](\d{4}|\d{2})")
TOTAL_WORDS = ("TOPLAM", "TUTAR", "TOTAL", "ÖDENECEK", "ODENECEK")


def _to_float(s):
    """Son ayırıcı ondalık, öncekiler binliktir: '1.358,94', '1,598,84' ve '12.50' doğru okunur."""
    s = s.replace(" ", "")
    i = max(s.rfind(","), s.rfind("."))
    return float(re.sub(r"[.,]", "", s[:i]) + "." + s[i + 1:])


def parse_receipt_text(text):
    """OCR metninden {'amount','date','merchant'} çıkarır (bulunamayan alan None)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    totals, allnums = [], []
    for line in lines:
        up = line.upper().replace("İ", "I")
        nums = [_to_float(n) for n in AMOUNT_RE.findall(line)]
        allnums += nums
        if nums and "KDV" not in up and any(w.replace("İ", "I") in up for w in TOTAL_WORDS):
            totals.append(max(nums))
    amount = max(totals) if totals else (max(allnums) if allnums else None)

    parsed_date = None
    m = DATE_RE.search(text)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        y += 2000 if y < 100 else 0
        try:
            parsed_date = date(y, mo, d).isoformat()
        except ValueError:
            pass
    merchant = lines[0][:40] if lines else None
    return {"amount": amount, "date": parsed_date, "merchant": merchant}


def _find_tesseract():
    """Tesseract PATH'te yoksa Windows'taki olağan kurulum yollarında arar."""
    import os
    import shutil
    import pytesseract
    if shutil.which("tesseract"):
        return True
    for p in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
              os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")):
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False


def read_receipt(path):
    """Görüntüyü ön işleyip OCR uygular ve parse_receipt_text sonucunu döner."""
    import pytesseract
    if not _find_tesseract():
        raise RuntimeError(
            "Tesseract OCR programı bulunamadı.\n\n"
            "1) https://github.com/UB-Mannheim/tesseract/wiki adresinden kurun "
            "(kurulumda 'Turkish' dilini işaretleyin).\n"
            "2) Uygulamayı kapatıp yeniden açın.")
    from PIL import Image, ImageOps
    img = ImageOps.autocontrast(ImageOps.grayscale(Image.open(path)))
    if img.width < 1000:
        scale = 1000 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    try:  # Türkçe paketi kuruluysa kullan, yoksa yalnızca İngilizce
        lang = "tur+eng" if "tur" in pytesseract.get_languages(config="") else "eng"
    except Exception:
        lang = "eng"
    try:
        text = pytesseract.image_to_string(img, lang=lang, timeout=90)
    except pytesseract.TesseractError:
        text = pytesseract.image_to_string(img, timeout=90)
    result = parse_receipt_text(text)
    result["raw_text"] = text
    return result
