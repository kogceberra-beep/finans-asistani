"""SQLite veritabanı katmanı: harcamalar, gelirler, kategoriler, hedefler, ayarlar."""
import os
import sqlite3
from contextlib import contextmanager

# Veritabanı her zaman proje klasöründe durur. Göreli yol kullanılsaydı, Python'u hangi
# klasörden çalıştırdığınıza göre (terminal, VS Code'un Run düğmesi, kısayol) farklı bir
# finance.db açılır ve veriler kaybolmuş gibi görünürdü.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("FINANCE_DB") or os.path.join(BASE_DIR, "finance.db")

DEFAULT_CATEGORIES = [  # (ad, aylık limit, renk)
    ("Market", 3000, "#4CAF50"), ("Restoran", 1500, "#FF9800"),
    ("Ulaşım", 1000, "#2196F3"), ("Fatura", 2500, "#9C27B0"),
    ("Eğlence", 800, "#E91E63"), ("Sağlık", 600, "#00BCD4"),
    ("Giyim", 1000, "#FFC107"), ("Diğer", 500, "#9E9E9E"),
]

EXPENSES_DDL = """
CREATE TABLE expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL,                     -- iadeler negatif olabilir
    date TEXT NOT NULL,                       -- YYYY-MM-DD
    description TEXT DEFAULT '',
    category_id INTEGER NOT NULL REFERENCES categories(id),
    source TEXT NOT NULL DEFAULT 'manual',    -- manual | ocr | bank | ekstre
    bank_tx_id TEXT UNIQUE,                   -- mock bankadan gelenlerin tekrarını önler
    tx_hash TEXT UNIQUE                       -- ekstreden gelenlerin tekrarını önler
);"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    monthly_limit REAL NOT NULL DEFAULT 0,
    color TEXT NOT NULL DEFAULT '#9E9E9E'
);
""" + EXPENSES_DDL.replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS") + """
CREATE INDEX IF NOT EXISTS idx_exp_date ON expenses(date);
CREATE TABLE IF NOT EXISTS incomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL NOT NULL CHECK (amount > 0),
    date TEXT NOT NULL,
    description TEXT DEFAULT '',
    source TEXT NOT NULL DEFAULT 'ekstre',
    tx_hash TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_inc_date ON incomes(date);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS seen_files (
    key TEXT PRIMARY KEY,                     -- dosya adı + boyut + değişim zamanı
    seen_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS merchant_rules (
    pattern TEXT PRIMARY KEY,                 -- küçük harfe indirgenmiş işyeri anahtarı
    category_id INTEGER NOT NULL REFERENCES categories(id)
);
CREATE TABLE IF NOT EXISTS inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,                     -- sms | eposta
    received_at TEXT NOT NULL,
    raw_text TEXT DEFAULT '',
    amount REAL,
    date TEXT,
    merchant TEXT DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'expense',     -- expense | income | refund
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | imported | ignored
    tx_hash TEXT UNIQUE
);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def _migrate(c):
    """Eski sürümdeki expenses tablosunu (CHECK amount>0, tx_hash yok) yeni şemaya taşır."""
    row = c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='expenses'").fetchone()
    cols = [r["name"] for r in c.execute("PRAGMA table_info(expenses)")]
    if "tx_hash" in cols and "amount > 0" not in row["sql"]:
        return
    c.executescript("ALTER TABLE expenses RENAME TO expenses_old;" + EXPENSES_DDL + """
        INSERT INTO expenses(id,amount,date,description,category_id,source,bank_tx_id)
            SELECT id,amount,date,description,category_id,source,bank_tx_id FROM expenses_old;
        DROP TABLE expenses_old;
        CREATE INDEX IF NOT EXISTS idx_exp_date ON expenses(date);""")


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        _migrate(c)
        if c.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            c.executemany("INSERT INTO categories(name, monthly_limit, color) VALUES (?,?,?)",
                          DEFAULT_CATEGORIES)
        c.execute("INSERT OR IGNORE INTO settings VALUES ('monthly_income', '25000')")


# ---------- kategoriler ----------
def get_categories():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM categories ORDER BY id")]


def category_id(name):
    with conn() as c:
        r = c.execute("SELECT id FROM categories WHERE name=?", (name,)).fetchone()
        return r["id"] if r else category_id("Diğer")


def set_limit(cat_id, limit):
    with conn() as c:
        c.execute("UPDATE categories SET monthly_limit=? WHERE id=?", (limit, cat_id))


# ---------- harcamalar ----------
def add_expense(amount, date, description, cat_id, source="manual", bank_tx_id=None, tx_hash=None):
    """Kayıt eklenirse True; bank_tx_id/tx_hash zaten varsa False döner."""
    with conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO expenses(amount,date,description,category_id,source,bank_tx_id,tx_hash) "
            "VALUES (?,?,?,?,?,?,?)", (amount, date, description, cat_id, source, bank_tx_id, tx_hash))
        return cur.rowcount > 0


def list_expenses(month=None, limit=300):
    q = "SELECT e.*, c.name AS category FROM expenses e JOIN categories c ON c.id=e.category_id "
    args = []
    if month:
        q += "WHERE strftime('%Y-%m', e.date)=? "
        args.append(month)
    q += "ORDER BY e.date DESC, e.id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def delete_expense(exp_id):
    with conn() as c:
        c.execute("DELETE FROM expenses WHERE id=?", (exp_id,))


def delete_by_source(source):
    with conn() as c:
        return c.execute("DELETE FROM expenses WHERE source=?", (source,)).rowcount


def totals_by_category(month, max_day=None):
    """{kategori_id: toplam} döner. max_day verilirse ayın yalnızca o gününe kadarı sayılır
    (yarım ayı geçen tam ayla kıyaslamak yanıltıcı olduğu için gerekir)."""
    q = "SELECT category_id, SUM(amount) t FROM expenses WHERE strftime('%Y-%m', date)=? "
    args = [month]
    if max_day:
        q += "AND CAST(strftime('%d', date) AS INTEGER) <= ? "
        args.append(max_day)
    with conn() as c:
        return {r["category_id"]: r["t"] for r in c.execute(q + "GROUP BY category_id", args)}


def last_bank_id():
    with conn() as c:
        r = c.execute("SELECT MAX(CAST(bank_tx_id AS INTEGER)) m FROM expenses "
                      "WHERE source='bank'").fetchone()
        return r["m"] or 0


def available_months():
    with conn() as c:
        rows = c.execute("SELECT strftime('%Y-%m', date) m FROM expenses UNION "
                         "SELECT strftime('%Y-%m', date) FROM incomes")
        return sorted((r["m"] for r in rows if r["m"]), reverse=True)


# ---------- gelirler ----------
def add_income(amount, date, description, source="ekstre", tx_hash=None):
    with conn() as c:
        cur = c.execute("INSERT OR IGNORE INTO incomes(amount,date,description,source,tx_hash) "
                        "VALUES (?,?,?,?,?)", (amount, date, description, source, tx_hash))
        return cur.rowcount > 0


def list_incomes(month=None, limit=300):
    q, args = "SELECT * FROM incomes ", []
    if month:
        q += "WHERE strftime('%Y-%m', date)=? "
        args.append(month)
    q += "ORDER BY date DESC, id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def delete_income(inc_id):
    with conn() as c:
        c.execute("DELETE FROM incomes WHERE id=?", (inc_id,))


def delete_incomes_by_source(source):
    with conn() as c:
        return c.execute("DELETE FROM incomes WHERE source=?", (source,)).rowcount


def month_income(month):
    with conn() as c:
        r = c.execute("SELECT COALESCE(SUM(amount),0) t FROM incomes "
                      "WHERE strftime('%Y-%m', date)=?", (month,)).fetchone()
        return r["t"]


# ---------- gelen kutusu (SMS / e-posta) ----------
def add_inbox(source, raw_text, amount, date, merchant, kind, tx_hash=None):
    """Çözümlenmiş bildirimi onay kuyruğuna ekler. Aynı bildirim iki kez girmez."""
    import hashlib
    if tx_hash is None:
        key = f"{source}|{date}|{amount}|{(merchant or '').lower()}|{(raw_text or '')[:120]}"
        tx_hash = hashlib.sha1(key.encode()).hexdigest()
    with conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO inbox(source,received_at,raw_text,amount,date,merchant,kind,tx_hash) "
            "VALUES (?,datetime('now','localtime'),?,?,?,?,?,?)",
            (source, raw_text, amount, date, merchant, kind, tx_hash))
        return cur.rowcount > 0


def list_inbox(source=None, status="pending", limit=300):
    q, args = "SELECT * FROM inbox WHERE 1=1 ", []
    if source:
        q += "AND source=? "
        args.append(source)
    if status:
        q += "AND status=? "
        args.append(status)
    q += "ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with conn() as c:
        return [dict(r) for r in c.execute(q, args)]


def set_inbox_status(ids, status):
    with conn() as c:
        c.executemany("UPDATE inbox SET status=? WHERE id=?", [(status, i) for i in ids])


def clear_inbox(source, status=None):
    q, args = "DELETE FROM inbox WHERE source=?", [source]
    if status:
        q += " AND status=?"
        args.append(status)
    with conn() as c:
        return c.execute(q, args).rowcount


# ---------- işyeri kuralları (öğrenen kategori) ----------
def set_rule(pattern, cat_id):
    """Kullanıcının düzelttiği kategoriyi bu işyeri için kalıcı kural yapar."""
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO merchant_rules(pattern, category_id) VALUES (?,?)",
                  (pattern.strip().lower(), cat_id))


def get_rules():
    """[(kalıp, kategori_adı, kategori_id)] — uzun kalıp önce denenir ki özel kural geneli ezsin."""
    with conn() as c:
        return [(r["pattern"], r["name"], r["category_id"]) for r in c.execute(
            "SELECT m.pattern, m.category_id, c.name FROM merchant_rules m "
            "JOIN categories c ON c.id = m.category_id ORDER BY LENGTH(m.pattern) DESC")]


def delete_rule(pattern):
    with conn() as c:
        c.execute("DELETE FROM merchant_rules WHERE pattern=?", (pattern,))


def set_expense_category(exp_id, cat_id):
    with conn() as c:
        c.execute("UPDATE expenses SET category_id=? WHERE id=?", (cat_id, exp_id))


def get_expense(exp_id):
    with conn() as c:
        r = c.execute("SELECT * FROM expenses WHERE id=?", (exp_id,)).fetchone()
        return dict(r) if r else None


# ---------- izlenen dosyalar ----------
def file_seen(key):
    with conn() as c:
        return c.execute("SELECT 1 FROM seen_files WHERE key=?", (key,)).fetchone() is not None


def mark_file_seen(key):
    with conn() as c:
        c.execute("INSERT OR IGNORE INTO seen_files(key, seen_at) VALUES (?, datetime('now','localtime'))",
                  (key,))


# ---------- ayarlar / bakiye ----------
def get_setting(key, default=None):
    with conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default


def set_setting(key, value):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))


def set_balance(value, as_of=None):
    """Bakiyeyi bir 'çıpa' olarak kaydeder: şu tarihte bakiye şu kadardı.
    Güncel bakiye bundan sonraki hareketlerle hesaplanır, böylece elle güncellemek gerekmez."""
    from datetime import date as _date
    set_setting("balance_anchor", value)
    set_setting("balance_anchor_date", as_of or _date.today().isoformat())


def balance_detail():
    """(çıpa tutarı, çıpa tarihi, sonraki hareketlerin net etkisi, işlem sayısı)"""
    from datetime import date as _date
    anchor = get_setting("balance_anchor")
    if anchor is None:                         # eski sürümden gelen tek sayılık bakiye
        eski = get_setting("account_balance")
        if eski is None:
            return 0.0, None, 0.0, 0
        anchor = eski
        set_balance(float(eski), _date.today().isoformat())
    day = get_setting("balance_anchor_date") or _date.today().isoformat()
    with conn() as c:
        gelir = c.execute("SELECT COALESCE(SUM(amount),0) t FROM incomes WHERE date > ?",
                          (day,)).fetchone()["t"]
        gider = c.execute("SELECT COALESCE(SUM(amount),0) t FROM expenses WHERE date > ?",
                          (day,)).fetchone()["t"]
        adet = c.execute("SELECT (SELECT COUNT(*) FROM incomes WHERE date > ?) + "
                         "(SELECT COUNT(*) FROM expenses WHERE date > ?) n", (day, day)).fetchone()["n"]
    return float(anchor), day, gelir - gider, adet


def get_balance():
    """Çıpa tarihinden sonraki harcama ve gelirler işlenmiş güncel bakiye."""
    anchor, _day, delta, _n = balance_detail()
    return anchor + delta
