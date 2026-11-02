"""Gmail'den fiş / fatura / sipariş e-postalarını okuyup harcamaya çevirir.

Google Cloud projesi ve OAuth gerektirmemesi için IMAP + uygulama şifresi kullanılır:
Google Hesabı > Güvenlik > 2 Adımlı Doğrulama açıkken 'Uygulama şifreleri' bölümünden
16 haneli bir şifre üretilir. Posta kutusu yalnızca OKUNUR; hiçbir e-posta değiştirilmez."""
import email
import imaplib
import re
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

import textparse as tp

IMAP_HOST = "imap.gmail.com"
MAX_MESSAGES = 400

# konu ya da gönderende bunlardan biri geçen e-postalar aday sayılır
HINTS = ("fatura", "fis", "e arsiv", "earsiv", "e-arsiv", "makbuz", "siparis", "odeme", "tahsilat",
         "alisveris", "satin alma", "receipt", "invoice", "order", "payment", "purchase", "biletiniz")
# reklam / bilgilendirme e-postalarını elemek için
EXCLUDE = ("kampanya", "indirim firsati", "firsatlari", "newsletter", "bulten", "anket", "sepetinizde",
           "iptal edildi", "kargoya verildi", "unsubscribe", "sifre", "dogrulama kodu")


class GmailError(Exception):
    pass


def _decode(value):
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:
        return value or ""


def _body_text(msg):
    """E-postanın düz metnini döner; yalnızca HTML varsa etiketleri temizler."""
    plain, html = [], []
    for part in msg.walk():
        if part.get_content_maintype() != "text" or part.get_filename():
            continue
        try:
            raw = part.get_payload(decode=True) or b""
            txt = raw.decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        (plain if part.get_content_subtype() == "plain" else html).append(txt)
    if plain:
        return "\n".join(plain)
    return tp.strip_html("\n".join(html))


def _pdf_text(msg):
    """PDF ekleri varsa metnini çıkarmaya çalışır (pypdf kuruluysa)."""
    try:
        import io

        from pypdf import PdfReader
    except ImportError:
        return ""
    out = []
    for part in msg.walk():
        name = _decode(part.get_filename() or "")
        if not name.lower().endswith(".pdf"):
            continue
        try:
            data = part.get_payload(decode=True) or b""
            reader = PdfReader(io.BytesIO(data))
            out.append("\n".join((p.extract_text() or "") for p in reader.pages[:5]))
        except Exception:
            continue
    return "\n".join(out)


def _is_candidate(subject, sender):
    hay = tp.norm(subject + " " + sender)
    if any(w in hay for w in EXCLUDE):
        return False
    return any(w in hay for w in HINTS)


def scan(user, app_password, days=30, host=IMAP_HOST, only_candidates=True):
    """Son `days` gün içindeki fiş/fatura e-postalarını çözümleyip liste döner."""
    try:
        imap = imaplib.IMAP4_SSL(host)
    except Exception as ex:
        raise GmailError(f"Sunucuya bağlanılamadı: {ex}")
    try:
        try:
            imap.login(user, app_password.replace(" ", ""))
        except imaplib.IMAP4.error:
            raise GmailError(
                "Giriş reddedildi.\n\nNormal Gmail şifreniz çalışmaz; 16 haneli bir UYGULAMA ŞİFRESİ "
                "gerekir.\n1) Google Hesabı > Güvenlik > 2 Adımlı Doğrulama'yı açın.\n"
                "2) Aynı sayfadaki 'Uygulama şifreleri' bölümünden yeni bir şifre üretin.\n"
                "3) O 16 haneli şifreyi buraya yazın.")
        imap.select("INBOX", readonly=True)
        since = (date.today() - timedelta(days=max(days, 1))).strftime("%d-%b-%Y")
        typ, data = imap.search(None, "SINCE", since)
        if typ != "OK":
            raise GmailError("Posta kutusu okunamadı.")
        ids = data[0].split()[-MAX_MESSAGES:]
        results = []
        for num in reversed(ids):
            typ, raw = imap.fetch(num, "(RFC822)")
            if typ != "OK" or not raw or not isinstance(raw[0], tuple):
                continue
            msg = email.message_from_bytes(raw[0][1])
            subject = _decode(msg.get("Subject"))
            name, addr = parseaddr(_decode(msg.get("From")))
            sender = name or addr
            if only_candidates and not _is_candidate(subject, f"{sender} {addr}"):
                continue
            text = _body_text(msg)
            pdf = _pdf_text(msg)
            amount = tp.find_amount(subject) or tp.find_amount(text) or tp.find_amount(pdf)
            try:
                when = parsedate_to_datetime(msg.get("Date")).date().isoformat()
            except Exception:
                when = date.today().isoformat()
            results.append({"date": tp.find_date(subject, False) or when,
                            "merchant": (sender or addr or "E-posta")[:60],
                            "subject": subject[:120], "amount": amount, "kind": "expense",
                            "raw": f"{sender} | {subject}"})
        return results
    finally:
        try:
            imap.logout()
        except Exception:
            pass
