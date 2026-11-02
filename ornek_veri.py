"""Örnek veri üreteci — uygulamayı dolu bir veritabanıyla denemek için.

Çalıştırma:  python ornek_veri.py

Son dört ay için gerçekçi bir harcama geçmişi üretir: maaş, kira, aboneliklerle
sabit giderler; market, restoran ve ulaşımda değişken harcamalar. Ayrıca
uygulamanın analiz özelliklerinin görünmesi için bilerek birkaç durum kurar:
bir aboneliğe zam, iptal edilmiş bir abonelik, olağan dışı büyüklükte bir
harcama ve mutabakat sayfasında bulunacak iki çift kayıt."""
import random
from datetime import date

import analyzer as an
import database as db

SEED = 20261101
MAAS = 48000.0

# (işyeri, kategori, ayın günü, tutar) — her ay aynı şekilde tekrar eden sabit giderler
SABIT = [
    ("KİRA ÖDEMESİ EV SAHİBİ", "Fatura", 2, 19500.0),
    ("TÜRK TELEKOM İNTERNET", "Fatura", 10, 549.0),
    ("VODAFONE FATURA", "Fatura", 12, 420.0),
]
MARKETLER = ["ŞOK MARKET", "BİM MAĞAZA", "MİGROS ANKARA", "A101 MAĞAZA", "CARREFOURSA"]
RESTORANLAR = ["YEMEKSEPETİ", "STARBUCKS KIZILAY", "LEZZET DURAĞI", "BURGER KING", "KAHVE DÜNYASI"]
ULASIM = ["OPET AKARYAKIT", "UBER TRIP", "İETT AKBİL", "BİTAKSİ"]
DIGER = [("ECZANE ŞİFA", "Sağlık", 200, 900), ("LCW MAĞAZA", "Giyim", 600, 2200),
         ("CINEMAXIMUM", "Eğlence", 280, 480), ("DEFACTO", "Giyim", 500, 1800)]


def ay_ekle(yil, ay, fark):
    t = yil * 12 + (ay - 1) + fark
    return t // 12, t % 12 + 1


def gun(yil, ay, g, son_gun=None):
    """Tarihi ISO biçiminde döner; ay bitmemişse son_gun'u aşan tarihler atlanır."""
    if son_gun is not None and g > son_gun:
        return None
    return f"{yil}-{ay:02d}-{min(g, 28):02d}"


def uret():
    rnd = random.Random(SEED)
    bugun = date.today()
    aylar = [ay_ekle(bugun.year, bugun.month, -i) for i in range(3, -1, -1)]
    gider = gelir = 0

    for idx, (y, m) in enumerate(aylar):
        son = bugun.day if (y, m) == (bugun.year, bugun.month) else None
        guncel_ay = son is not None

        d = gun(y, m, 1, son)
        if d:
            db.add_income(MAAS, d, "MAAŞ ÖDEMESİ ÖRNEK A.Ş.", "ekstre")
            gelir += 1

        for ad, kat, g, tutar in SABIT:
            d = gun(y, m, g, son)
            if d:
                db.add_expense(tutar, d, ad, db.category_id(kat), "ekstre")
                gider += 1

        # elektrik: her ay var ama tutarı mevsime göre değişir
        d = gun(y, m, 18, son)
        if d:
            db.add_expense(round(rnd.uniform(850, 1650), 2), d, "ENERJİSA ELEKTRİK FATURA",
                           db.category_id("Fatura"), "ekstre")
            gider += 1

        # Netflix: son tam ayda zam geldi
        d = gun(y, m, 9, son)
        if d:
            db.add_expense(229.0 if idx < 2 else 279.0, d, "NETFLIX.COM",
                           db.category_id("Eğlence"), "ekstre")
            gider += 1

        # Spotify: ilk iki ay var, sonra iptal edilmiş
        if idx < 2:
            d = gun(y, m, 15, son)
            if d:
                db.add_expense(99.99, d, "SPOTIFY", db.category_id("Eğlence"), "ekstre")
                gider += 1

        # değişken harcamalar
        for _ in range(rnd.randint(7, 11) if not guncel_ay else max(bugun.day // 3, 1)):
            d = gun(y, m, rnd.randint(1, 28), son)
            if d:
                ad = rnd.choice(MARKETLER)
                db.add_expense(round(rnd.uniform(250, 1400), 2), d, ad,
                               db.category_id(an.guess_category(ad)), "ekstre")
                gider += 1
        for _ in range(rnd.randint(4, 7) if not guncel_ay else max(bugun.day // 6, 1)):
            d = gun(y, m, rnd.randint(1, 28), son)
            if d:
                ad = rnd.choice(RESTORANLAR)
                db.add_expense(round(rnd.uniform(200, 900), 2), d, ad,
                               db.category_id(an.guess_category(ad)), "ekstre")
                gider += 1
        for _ in range(rnd.randint(4, 8) if not guncel_ay else max(bugun.day // 5, 1)):
            d = gun(y, m, rnd.randint(1, 28), son)
            if d:
                ad = rnd.choice(ULASIM)
                tutar = rnd.uniform(900, 2200) if "OPET" in ad else rnd.uniform(60, 400)
                db.add_expense(round(tutar, 2), d, ad, db.category_id(an.guess_category(ad)), "ekstre")
                gider += 1
        for ad, kat, lo, hi in DIGER:
            if rnd.random() < (0.4 if not guncel_ay else 0.15):
                d = gun(y, m, rnd.randint(1, 28), son)
                if d:
                    db.add_expense(round(rnd.uniform(lo, hi), 2), d, ad, db.category_id(kat), "ekstre")
                    gider += 1

    # --- analiz özelliklerinin görünmesi için kurulan özel durumlar ---
    oy, om = aylar[-2]                       # son tamamlanmış ay
    db.add_expense(24500.0, f"{oy}-{om:02d}-22", "TEKNOSA BİLGİSAYAR",
                   db.category_id("Diğer"), "ekstre")          # olağan dışı harcama
    gider += 1

    # mutabakat için: aynı harcama hem ekstreden hem SMS/fişten girmiş gibi
    db.add_expense(640.50, f"{oy}-{om:02d}-07", "MİGROS ANKARA", db.category_id("Market"), "ekstre")
    db.add_expense(640.50, f"{oy}-{om:02d}-07", "MIGROS", db.category_id("Market"), "sms")
    db.add_expense(1180.00, f"{oy}-{om:02d}-19", "ŞOK MARKET", db.category_id("Market"), "ekstre")
    db.add_expense(1180.00, f"{oy}-{om:02d}-17", "SOK", db.category_id("Market"), "ocr")
    gider += 4

    # bütçe limitlerini üretilen veriye göre ayarla, yoksa her kategori kırmızı görünür
    db.set_setting("monthly_income", MAAS)
    aylik = {}
    for ay_str in db.available_months():
        for cid, toplam in db.totals_by_category(ay_str).items():
            aylik.setdefault(cid, []).append(toplam)
    for c in db.get_categories():
        vals = aylik.get(c["id"])
        if vals:
            ort = sum(vals) / len(vals)
            db.set_limit(c["id"], round(ort * 1.15, -2))
    db.set_balance(45000.0)
    return gider, gelir


if __name__ == "__main__":
    db.init_db()
    print(f"Veritabanı: {db.DB_PATH}")
    mevcut = len(db.list_expenses(limit=5))
    if mevcut:
        c = input("Veritabanında kayıt var. Örnek veri yine de EKLENSİN mi? (e/h): ").strip().lower()
        if c != "e":
            raise SystemExit("İptal edildi.")
    g, i = uret()
    print(f"\n{g} harcama ve {i} gelir kaydı eklendi.")
    print(f"Aylar: {', '.join(db.available_months())}")
    print("Hesap bakiyesi 45.000 ₺, aylık gelir 48.000 ₺ olarak ayarlandı.")
    print("Kategori limitleri üretilen veriye göre güncellendi.")
    print("\nUygulamayı açıp şunlara bakın:")
    print("  Öneriler    -> sabit giderler, Netflix zammı, iptal edilen Spotify, olağan dışı harcama")
    print("  Nakit Akışı -> ayın gün gün akışı ve bakiye tahmini")
    print("  Mutabakat   -> bilerek eklenmiş 2 çift kaydı bulup birleştirin")
