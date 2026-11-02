"""Akıllı analiz ve öneri motoru."""
import calendar
from datetime import date, datetime

import database as db
import insights as ins
import textparse as tp

merchant_key = tp.merchant_key      # geriye dönük uyumluluk

KEYWORDS = {
    "Market": ["migros", "a101", "bim", "şok", "carrefour", "market", "bakkal"],
    "Restoran": ["yemeksepeti", "starbucks", "restoran", "cafe", "kafe", "burger", "kebap", "lokanta", "yemek"],
    "Ulaşım": ["uber", "bitaksi", "iett", "akbil", "opet", "shell", "benzin", "taksi", "otobüs", "petrol", "akaryak", "bp "],
    "Fatura": ["enerjisa", "igdaş", "iski", "turkcell", "vodafone", "telekom", "fatura", "elektrik", "kira", "aidat", "doğalgaz"],
    "Eğlence": ["netflix", "spotify", "sinema", "cinemaximum", "steam", "bilet"],
    "Sağlık": ["eczane", "hastane", "klinik", "medikal"],
    "Giyim": ["zara", "lcw", "h&m", "koton", "defacto", "mavi", "trendyol", "hepsiburada", "giyim"],
}


def guess_category(text):
    """Önce kullanıcının öğrettiği kurallara, sonra yerleşik anahtar kelimelere bakar."""
    t = (text or "").replace("İ", "i").lower()
    for pattern, name, _ in db.get_rules():
        if pattern and pattern in t:
            return name
    for cat, words in KEYWORDS.items():
        if any(w in t for w in words):
            return cat
    return "Diğer"


def _prev_month(month):
    y, m = map(int, month.split("-"))
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _days(month):
    """(geçen gün, ayın toplam günü)"""
    y, m = map(int, month.split("-"))
    total = calendar.monthrange(y, m)[1]
    today = date.today()
    if (today.year, today.month) == (y, m):
        return today.day, total
    return total, total


def budget_status(month):
    spent = db.totals_by_category(month)
    out = []
    for c in db.get_categories():
        s = spent.get(c["id"], 0.0)
        lim = c["monthly_limit"]
        out.append({"id": c["id"], "name": c["name"], "color": c["color"], "limit": lim,
                    "spent": s, "pct": (s / lim * 100) if lim else 0})
    return out


def month_summary(month):
    st = budget_status(month)
    spent = sum(s["spent"] for s in st)
    budget = sum(s["limit"] for s in st)
    elapsed, total_days = _days(month)
    forecast = ins.forecast(month)      # sabit giderleri ayrı hesaplayan tahmin
    income = float(db.get_setting("monthly_income", 0))
    return {"income_actual": db.month_income(month), "spent": spent, "budget": budget, "income": income, "forecast": forecast,
            "remaining": budget - spent, "elapsed": elapsed, "total_days": total_days}


def trends(month):
    """Önceki aya göre kategori bazlı değişim.

    Ay henüz bitmemişse geçen ayın tamamıyla kıyaslamak yanıltır: ayın 5'inde
    "harcamanızı %90 azalttınız" demek anlamsızdır. Bu yüzden geçen ay da aynı
    güne kadar kesilerek karşılaştırılır."""
    elapsed, total_days = _days(month)
    max_day = elapsed if elapsed < total_days else None
    prev = db.totals_by_category(_prev_month(month), max_day)
    cur = db.totals_by_category(month)
    res = []
    for c in db.get_categories():
        p, n = prev.get(c["id"], 0), cur.get(c["id"], 0)
        if p > 0:
            res.append({"name": c["name"], "prev": p, "cur": n, "change_pct": (n - p) / p * 100})
    return res


def generate_alerts(month):
    """[{'level': danger|warning|info|success, 'text': ...}] — dinamik uyarı ve öneriler."""
    fmt = lambda x: f"{x:,.0f} ₺"
    alerts = []
    sm, st = month_summary(month), budget_status(month)
    inc = sm["income_actual"] or sm["income"]       # ekstreden gelen gerçek gelir, yoksa beklenen gelir

    for s in st:
        if s["limit"] and s["pct"] >= 100:
            alerts.append({"level": "danger", "text":
                f"{s['name']} bütçesi aşıldı: {fmt(s['spent'])} / {fmt(s['limit'])} (%{s['pct']:.0f})."})
        elif s["limit"] and s["pct"] >= 80:
            alerts.append({"level": "warning", "text":
                f"{s['name']} bütçesinin %{s['pct']:.0f} kadarını kullandınız; ay sonuna kadar {fmt(s['limit'] - s['spent'])} kaldı."})

    if sm["budget"] and sm["forecast"] > sm["budget"]:
        alerts.append({"level": "warning", "text":
            f"Bu tempoyla ay sonu tahmini harcamanız {fmt(sm['forecast'])}; toplam bütçenizi "
            f"{fmt(sm['forecast'] - sm['budget'])} aşabilir."})
    left_days = sm["total_days"] - sm["elapsed"]
    if sm["remaining"] > 0 and left_days > 0:
        alerts.append({"level": "info", "text":
            f"Bütçenizi korumak için günlük ortalama {fmt(sm['remaining'] / left_days)} altında kalmalısınız."})
    if inc and sm["spent"] > inc * 0.9:
        alerts.append({"level": "danger", "text": "Harcamalarınız aylık gelirinizin %90 sınırını geçti!"})

    # Ayın ilk günlerinde tek günlük veriyle "geçen aya göre %100 azalttınız" demek yanıltır.
    if sm["elapsed"] >= 7 or sm["elapsed"] == sm["total_days"]:
        for t in trends(month):
            if t["change_pct"] >= 30 and t["cur"] - t["prev"] >= 100:
                alerts.append({"level": "info", "text":
                    f"{t['name']} harcaması geçen aya göre %{t['change_pct']:.0f} arttı "
                    f"({fmt(t['prev'])} → {fmt(t['cur'])})."})
            elif t["change_pct"] <= -30 and t["prev"] - t["cur"] >= 100:
                alerts.append({"level": "success", "text":
                    f"Tebrikler! {t['name']} harcamasını geçen aya göre %{abs(t['change_pct']):.0f} azalttınız."})

        if sm["spent"] > 0:
            top = max(st, key=lambda s: s["spent"])
            share = top["spent"] / sm["spent"] * 100
            if share >= 35:
                alerts.append({"level": "info", "text":
                    f"Harcamalarınızın %{share:.0f} kadarı {top['name']} kategorisinde. "
                    f"Burada %10 tasarruf aylık {fmt(top['spent'] * 0.1)} kazandırır."})

    # --- geçmişten çıkarılan örüntüler ---
    fixed = ins.active_fixed(month)
    if fixed:
        ft = sum(r["amount"] for r in fixed)
        text = f"Aylık sabit giderleriniz {fmt(ft)} ({len(fixed)} kalem: " \
               f"{', '.join(r['name'][:18] for r in fixed[:3])}{'...' if len(fixed) > 3 else ''})."
        if inc:
            text += f" Gelirinize oranı: %{ft / inc * 100:.0f}."
        alerts.append({"level": "info", "text": text})

    for p in ins.pending(month):
        alerts.append({"level": "info", "text":
            f"{p['name'][:24]} ödemesi ({fmt(p['amount'])}) bu ay henüz düşmedi; genelde her ayın "
            f"{p['day']}. günü çekiliyor."})

    for p in ins.price_changes():
        yon = "yükseldi" if p["change"] > 0 else "düştü"
        alerts.append({"level": "warning" if p["change"] > 0 else "success", "text":
            f"{p['name'][:24]} ödemeniz {fmt(p['first_amount'])} seviyesinden {fmt(p['last_amount'])} "
            f"seviyesine {yon} (%{abs(p['change']) * 100:.0f})."})

    for s in ins.stopped(month):
        alerts.append({"level": "info", "text":
            f"{s['name'][:24]} ({fmt(s['amount'])}) son {s['gap']} aydır düşmüyor; "
            f"aboneliği iptal etmiş olabilirsiniz."})

    for an_ in ins.anomalies(month)[:3]:
        e = an_["expense"]
        nerede = "bu işyerindeki" if an_["basis"] == "merchant" else f"{e['category']} kategorisindeki"
        alerts.append({"level": "warning", "text":
            f"{e['date']} tarihinde {e['description'][:24]} harcamanız {fmt(e['amount'])} — "
            f"{nerede} olağan harcamanızın {an_['ratio']:.0f} katı. Beklenen bir ödeme değilse kontrol edin."})

    cf = ins.cashflow(month)
    if cf["is_current"] and cf["min_balance"] is not None and cf["min_balance"] < 0:
        alerts.append({"level": "danger", "text":
            f"Nakit akışı uyarısı: bu gidişle {cf['min_date']} tarihinde bakiyeniz "
            f"{fmt(cf['min_balance'])} seviyesine düşüyor. Takvim sayfasından o tarihe kadar "
            f"düşecek sabit giderleri görebilirsiniz."})

    if not alerts:
        alerts.append({"level": "success", "text": "Her şey yolunda, bütçeniz dengeli görünüyor."})
    return alerts
