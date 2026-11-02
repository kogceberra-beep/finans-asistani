"""Harcama geçmişinden örüntü çıkaran analizler.

Üç soruya cevap verir: hangi ödemeler her ay tekrar ediyor (sabit gider / abonelik),
hangi harcama alışılmışın dışında, ve sabit giderler dikkate alındığında ay sonunda
gerçekte ne kadar harcamış olacağız."""
import calendar
from collections import Counter
from datetime import date
from statistics import median

import database as db
import textparse as tp

STABLE_RATIO = 1.35        # en büyük/en küçük tutar oranı bunun altındaysa "sabit tutarlı"
                           # (bir abonelige zam gelse de abonelik olmaya devam eder)
MAX_DAY_SPREAD = 4         # düzenli ödeme her ay aynı güne yakın düşer
MERCHANT_MIN = 4           # işyeri geçmişiyle kıyas için gereken en az kayıt
MIN_MONTHS = 2
ANOMALY_FACTOR = 3.0       # medyanın kaç katı "olağan dışı" sayılsın
MERCHANT_FACTOR = 3.0      # aynı işyerindeki geçmişle kıyaslama eşiği
ANOMALY_FLOOR = 500.0      # küçük tutarlar için uyarı üretme


def _m(d):
    return d[:7]


def _d(d):
    return int(d[8:10])


def month_diff(a, b):
    ya, ma = map(int, a.split("-"))
    yb, mb = map(int, b.split("-"))
    return (ya - yb) * 12 + (ma - mb)


def _detect(records, min_months):
    """Kayıtları marka anahtarına göre gruplayıp her ay tekrar edenleri bulur.
    Hem harcamalar hem gelirler için kullanılır."""
    groups = {}
    for r in records:
        if r["amount"] <= 0:
            continue
        k = tp.merchant_key(r["description"])
        if k:
            groups.setdefault(k, []).append(r)
    out = []
    for key, items in groups.items():
        by_month = {}
        for e in items:
            by_month.setdefault(_m(e["date"]), []).append(e)
        if len(by_month) < min_months:
            continue
        months = sorted(by_month)
        per_month = [median(x["amount"] for x in by_month[m]) for m in months]
        lo, hi = min(per_month), max(per_month)
        ratio = hi / lo if lo > 0 else 99
        # Düzenli ödemenin ayırt edici özelliği tutarı değil, TAKVİMİDİR: her ay bir kez,
        # hep aynı güne yakın düşer. Markete ayda birkaç kez rastgele günlerde gidilir.
        single = all(len(v) == 1 for v in by_month.values())
        gunler = [_d(by_month[m][0]["date"]) for m in months] if single else []
        regular = single and (max(gunler) - min(gunler)) <= MAX_DAY_SPREAD
        out.append({
            "regular": regular,
            "key": key, "name": Counter(e["description"] for e in items).most_common(1)[0][0],
            "category": items[0].get("category", ""),
            "amount": median(per_month), "day": int(median(_d(e["date"]) for e in items)),
            "months": months, "count": len(by_month), "per_month": per_month,
            "first_amount": per_month[0], "last_amount": per_month[-1],
            "last_month": months[-1], "ratio": ratio,
            # stable: tutarı da değişmeyen abonelikler (Netflix). regular ama stable olmayanlar
            # tutarı değişen düzenli faturalardır (elektrik) — takvimde yine beklenir.
            "stable": regular and ratio <= STABLE_RATIO,
        })
    out.sort(key=lambda r: -r["amount"])
    return out


def recurring(min_months=MIN_MONTHS):
    """Birden çok ayda tekrar eden ödemeler.
    stable=True olanlar abonelik/kira gibi sabit tutarlı giderlerdir."""
    return _detect(db.list_expenses(None, limit=5000), min_months)


def recurring_income(min_months=MIN_MONTHS):
    """Her ay tekrar eden gelirler (maaş gibi). Nakit akışı takvimi için gerekir."""
    return [r for r in _detect(db.list_incomes(None, limit=5000), min_months) if r["stable"]]


def fixed_items():
    """Her ay aynı güne yakın düşen ödemeler: kira, abonelikler ve tutarı değişse de
    düzenli olan faturalar. Nakit akışı ve tahmin bunları ayrı ele alır."""
    return [r for r in recurring() if r["regular"]]


def active_fixed(month):
    """Hâlâ yürürlükte olan sabit giderler; iptal edilmiş abonelikler sayılmaz."""
    return [r for r in fixed_items() if month_diff(month, r["last_month"]) <= 1]


def fixed_total(month):
    """O ay için aylık sabit gider toplamı."""
    return sum(r["amount"] for r in active_fixed(month))


def _charged_keys(month):
    """Bu ay hangi markalara ödeme yapılmış."""
    return {tp.merchant_key(e["description"]) for e in db.list_expenses(month, limit=2000)
            if e["amount"] > 0}


def pending(month):
    """Bu ay henüz düşmemiş sabit giderler. İptal edilmiş abonelikler beklenenler arasına girmez."""
    done = _charged_keys(month)
    return [r for r in active_fixed(month) if r["key"] not in done]


def forecast(month):
    """Ay sonu tahmini.

    Düz orantı yanıltır: ayın 2'sinde ödenen kira, 'günlük harcama hızını' olduğundan
    çok yüksek gösterir. Bunun yerine sabit giderler ayrılır, yalnızca değişken harcama
    günlük hıza çevrilir ve ay içinde düşmesi beklenen sabit giderler sonradan eklenir."""
    spent = sum(db.totals_by_category(month).values())
    y, mo = map(int, month.split("-"))
    total_days = calendar.monthrange(y, mo)[1]
    today = date.today()
    if (today.year, today.month) != (y, mo):
        return spent                                   # geçmiş ay zaten tamamlanmış
    elapsed = max(today.day, 1)
    fixed_keys = {r["key"] for r in fixed_items()}
    fixed_paid = sum(e["amount"] for e in db.list_expenses(month, limit=2000)
                     if e["amount"] > 0 and tp.merchant_key(e["description"]) in fixed_keys)
    variable_rate = max(spent - fixed_paid, 0) / elapsed
    return spent + variable_rate * (total_days - elapsed) + sum(r["amount"] for r in pending(month))


def anomalies(month, factor=ANOMALY_FACTOR, floor=ANOMALY_FLOOR):
    """Kendi geçmişine göre olağan dışı büyüklükteki harcamalar.

    Önce aynı işyerindeki geçmişe bakılır: 1.200 ₺'lik market alışverişi, o markette hep
    1.000 ₺ civarı harcıyorsanız olağan dışı değildir. İşyeri geçmişi yoksa kategori
    geçmişi kullanılır. Kira ve abonelikler yüksek ama normaldir, elenir."""
    fixed_keys = {r["key"] for r in fixed_items()}
    all_exp = [e for e in db.list_expenses(None, limit=5000) if e["amount"] > 0]
    by_cat, by_merchant = {}, {}
    for e in all_exp:
        by_cat.setdefault(e["category"], []).append(e["amount"])
        by_merchant.setdefault(tp.merchant_key(e["description"]), []).append(e["amount"])
    out = []
    for e in (x for x in all_exp if _m(x["date"]) == month):
        key = tp.merchant_key(e["description"])
        if key in fixed_keys:
            continue
        own = list(by_merchant.get(key, []))
        own.remove(e["amount"])                        # kendisi medyanı yukarı çekmesin
        if len(own) >= MERCHANT_MIN:
            basis, values, f = "merchant", own, MERCHANT_FACTOR
        else:
            values = list(by_cat.get(e["category"], []))
            values.remove(e["amount"])
            if len(values) < 3:
                continue
            basis, f = "category", factor
        med = median(values)
        if med > 0 and e["amount"] >= max(f * med, floor):
            out.append({"expense": e, "median": med, "ratio": e["amount"] / med, "basis": basis})
    out.sort(key=lambda x: -x["ratio"])
    return out


def price_changes(threshold=0.05):
    """Tutarı değişen tekrarlayan ödemeler (zam veya indirim)."""
    out = []
    for r in recurring():              # "zam" yalnızca tutarı normalde sabit olan ödemelerde anlamlı
        if not r["stable"] or r["count"] < 2 or r["first_amount"] <= 0:
            continue
        change = (r["last_amount"] - r["first_amount"]) / r["first_amount"]
        if abs(change) >= threshold and abs(r["last_amount"] - r["first_amount"]) >= 5:
            out.append({**r, "change": change})
    return sorted(out, key=lambda r: -abs(r["change"]))


def stopped(month, min_count=2):
    """En az iki ay düzenli düşen, sonra kesilen ödemeler (iptal edilmiş abonelikler)."""
    out = []
    for r in fixed_items():
        if r["count"] >= min_count and month_diff(month, r["last_month"]) >= 2:
            out.append({**r, "gap": month_diff(month, r["last_month"])})
    return out


def _daily_variable(month):
    """Sabit giderler dışında kalan günlük ortalama harcama.

    Ayın ilk günlerinde yalnızca birkaç güne bakmak oynak sonuç verir (tek bir büyük
    alışveriş ortalamayı ikiye katlar). Bu yüzden ay ilerleyene kadar geçen ayın
    ortalamasıyla harmanlanır."""
    fixed_keys = {r["key"] for r in fixed_items()}

    def rate(m, days):
        rows = [e for e in db.list_expenses(m, limit=2000) if e["amount"] > 0]
        if not rows or days <= 0:
            return None
        # tek seferlik büyük alımlar (bilgisayar, mobilya) günlük hızı temsil etmez
        atlanacak = {a["expense"]["id"] for a in anomalies(m)}
        variable = sum(e["amount"] for e in rows
                       if tp.merchant_key(e["description"]) not in fixed_keys
                       and e["id"] not in atlanacak)
        return variable / days

    y, mo = map(int, month.split("-"))
    today = date.today()
    elapsed = today.day if (today.year, today.month) == (y, mo) else calendar.monthrange(y, mo)[1]
    cur = rate(month, elapsed)
    prev_m = _prev(month)
    py, pmo = map(int, prev_m.split("-"))
    prev = rate(prev_m, calendar.monthrange(py, pmo)[1])
    if cur is None:
        return prev or 0.0
    if prev is None:
        return cur
    w = min(elapsed / 10.0, 1.0)          # 10. günden sonra tamamen bu aya güven
    return w * cur + (1 - w) * prev


def _prev(month):
    y, mo = map(int, month.split("-"))
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def cashflow(month):
    """Ayın gün gün nakit akışı: geçmiş günlerde gerçekleşen, gelecek günlerde beklenen
    hareketler ve bakiyenin nasıl seyredeceği.

    Bakiye eğrisi yalnızca içinde bulunulan ay için çizilir; geçmiş aylarda kayıtlı
    bakiye o aya ait olmadığından yalnızca gerçekleşen hareketler gösterilir."""
    y, mo = map(int, month.split("-"))
    first_weekday, total_days = calendar.monthrange(y, mo)
    today = date.today()
    is_current = (today.year, today.month) == (y, mo)

    days = [{"day": d, "date": f"{month}-{d:02d}", "out": 0.0, "in": 0.0,
             "exp_out": 0.0, "exp_in": 0.0, "items": [],
             "past": (d <= today.day) if is_current else date(y, mo, d) < today,
             "today": is_current and d == today.day, "balance": None}
            for d in range(1, total_days + 1)]
    idx = {d["day"]: d for d in days}

    for e in db.list_expenses(month, limit=3000):
        idx[_d(e["date"])]["out"] += e["amount"]
    for i in db.list_incomes(month, limit=3000):
        idx[_d(i["date"])]["in"] += i["amount"]

    # gelecekte beklenen sabit hareketler
    charged = _charged_keys(month)
    received = {tp.merchant_key(i["description"]) for i in db.list_incomes(month, limit=2000)}
    for r in active_fixed(month):
        if r["key"] in charged:
            continue
        d = idx[min(r["day"], total_days)]
        if not d["past"]:
            d["exp_out"] += r["amount"]
            d["items"].append({"name": r["name"], "amount": r["amount"], "kind": "out"})
    for r in recurring_income():
        if r["key"] in received or month_diff(month, r["last_month"]) > 1:
            continue
        d = idx[min(r["day"], total_days)]
        if not d["past"]:
            d["exp_in"] += r["amount"]
            d["items"].append({"name": r["name"], "amount": r["amount"], "kind": "in"})

    rate = _daily_variable(month) if is_current else 0.0
    balance = db.get_balance() if is_current else None
    low, low_day = None, None
    if is_current and balance is not None:
        # bugünden geriye: kayıtlı bakiyeden geçmiş hareketleri çıkararak gün sonlarını bul
        run = balance
        for d in reversed([x for x in days if x["past"]]):
            d["balance"] = run
            run -= d["in"] - d["out"]
        run = balance
        for d in [x for x in days if not x["past"]]:
            run += d["exp_in"] - d["exp_out"] - rate
            d["balance"] = run
            if low is None or run < low:
                low, low_day = run, d["date"]
    return {"days": days, "first_weekday": first_weekday, "total_days": total_days,
            "is_current": is_current, "start_balance": db.get_balance(),
            "daily_rate": rate, "min_balance": low, "min_date": low_day,
            "end_balance": days[-1]["balance"] if is_current else None}
