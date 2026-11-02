"""Akıllı Finans Asistanı — CustomTkinter arayüzü.  Çalıştırma: python app.py"""
import datetime as dt
import glob
import os
import threading
from tkinter import filedialog, messagebox

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import analyzer as an
import statement
import reconcile as rc
import insights as ins
import textparse as tp
import bank_client
import database as db
import ocr

MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz",
          "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
# (açık tema, koyu tema) renk çiftleri
BG = ("#eef0f4", "#17191c")
CARD = ("#ffffff", "#24272c")
SIDE = ("#ffffff", "#1f2226")
TEXT = ("#111827", "#f3f4f6")
MUTED = ("#6b7280", "#9aa0a6")
SOFT = ("#f3f4f6", "#2d3036")
LEVEL = {"danger": "#e74c3c", "warning": "#f39c12", "info": "#3498db", "success": "#2ecc71"}
SOURCE = {"manual": "Manuel", "ocr": "Fiş", "bank": "Demo", "ekstre": "Ekstre", "sms": "SMS",
          "eposta": "E-posta"}
KIND_TR = {"expense": "Gider", "income": "Gelir", "refund": "İade"}
PAGES = ["Panel", "Nakit Akışı", "Harcamalar", "Gelirler", "Fiş Oku", "Hesap ve Kart",
         "Mutabakat", "Bütçe", "Öneriler"]
WEEKDAYS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

fmt = lambda x: f"{x:,.2f} ₺"
fmt0 = lambda x: f"{x:,.0f} ₺"


def F(size=13, bold=False):
    return ctk.CTkFont(family="Segoe UI", size=size, weight="bold" if bold else "normal")


def bar_color(pct):
    return "#e74c3c" if pct >= 100 else "#f39c12" if pct >= 80 else "#2ecc71"


def card(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14, **kw)


def entry(parent, ph="", w=140, show=None):
    kw = {"show": show} if show else {}
    return ctk.CTkEntry(parent, placeholder_text=ph, width=w, height=36, font=F(13), **kw)


def primary(parent, text, cmd, w=120, color=None):
    kw = {"fg_color": color[0], "hover_color": color[1]} if color else {}
    return ctk.CTkButton(parent, text=text, command=cmd, width=w, height=36, font=F(13, True), **kw)


class Table(ctk.CTkFrame):
    """Kenarlıksız tablo. checkable=True ise satırlar onay kutusuyla çoklu seçilebilir."""

    def __init__(self, master, columns, weights, limit=60, checkable=False):
        super().__init__(master, fg_color=CARD, corner_radius=14)
        self.checkable = checkable
        if checkable:
            columns, weights = ("",) + tuple(columns), (1,) + tuple(weights)
        self.weights, self.limit = weights, limit
        self.selected_id, self.checked, self._frames = None, set(), {}
        head = ctk.CTkFrame(self, fg_color=("#e8ebf0", "#31353c"), corner_radius=8)
        head.pack(fill="x", padx=(10, 26), pady=(10, 4))
        self._fill(head, columns, bold=True)
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=4, pady=(0, 8))

    def _fill(self, frame, cells, bold=False):
        for i, w in enumerate(self.weights):
            frame.grid_columnconfigure(i, weight=w, uniform="c")
        labels = []
        for i, c in enumerate(cells):
            lbl = ctk.CTkLabel(frame, text=str(c), anchor="w", font=F(13, bold), text_color=TEXT)
            lbl.grid(row=0, column=i, sticky="ew", padx=10, pady=7)
            labels.append(lbl)
        return labels

    @staticmethod
    def _base(n):
        return "transparent" if n % 2 == 0 else ("#f5f6f8", "#2a2d33")

    def set_rows(self, rows):
        """rows: [(kayıt_id, [hücreler...]), ...]"""
        for w in self.body.winfo_children():
            w.destroy()
        self.selected_id, self.checked, self._frames = None, set(), {}
        if not rows:
            ctk.CTkLabel(self.body, text="Kayıt yok", text_color=MUTED, font=F(13)).pack(pady=30)
        for n, (rid, cells) in enumerate(rows[:self.limit]):
            fr = ctk.CTkFrame(self.body, fg_color=self._base(n), corner_radius=6)
            fr.pack(fill="x", padx=6, pady=1)
            labels = self._fill(fr, (("☐",) + tuple(cells)) if self.checkable else cells)
            action = self.toggle if self.checkable else self.select
            for w in [fr] + labels:
                w.bind("<Button-1>", lambda e, r=rid: action(r))
            self._frames[rid] = (fr, n, labels)

    def select(self, rid):
        if self.selected_id in self._frames:
            fr, n, _ = self._frames[self.selected_id]
            fr.configure(fg_color=self._base(n))
        self.selected_id = rid
        self._frames[rid][0].configure(fg_color=("#cfe3fa", "#2c4a73"))

    def toggle(self, rid, value=None):
        on = (rid not in self.checked) if value is None else value
        fr, n, labels = self._frames[rid]
        self.checked.add(rid) if on else self.checked.discard(rid)
        labels[0].configure(text="☑" if on else "☐")
        fr.configure(fg_color=("#cfe3fa", "#2c4a73") if on else self._base(n))

    def check_all(self, on=True):
        for rid in list(self._frames):
            self.toggle(rid, on)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        db.init_db()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Akıllı Finans Asistanı")
        self.geometry("1280x800")
        self.minsize(1100, 760)
        self.configure(fg_color=BG)
        today = dt.date.today()
        # İçinde bulunulan ayda henüz kayıt yoksa (ayın başı) boş ekran açmak yerine
        # veri bulunan en son ayı göster.
        bu_ay = today.strftime("%Y-%m")
        self.month = bu_ay
        if not db.totals_by_category(bu_ay):          # gelir var ama harcama yoksa da boş sayılır
            dolu = next((m for m in db.available_months() if db.totals_by_category(m)), None)
            self.month = dolu or bu_ay
        self.cats = db.get_categories()
        self.cat_names = [c["name"] for c in self.cats]

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.build_sidebar()
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=22, pady=16)
        head = ctk.CTkFrame(main, fg_color="transparent")
        head.pack(fill="x", pady=(0, 12))
        self.title_lbl = ctk.CTkLabel(head, text="", font=F(26, True), text_color=TEXT)
        self.title_lbl.pack(side="left")
        self.month_map = {}
        self.month_menu = ctk.CTkOptionMenu(head, values=[self.month_label(self.month)], width=170, height=34,
                                            font=F(13), command=self.on_month)
        self.month_menu.pack(side="right")
        holder = ctk.CTkFrame(main, fg_color="transparent")
        holder.pack(fill="both", expand=True)

        self.pages = {}
        builders = [self.build_dashboard, self.build_cashflow, self.build_expenses,
                    self.build_incomes, self.build_ocr,
                    self.build_bank, self.build_reconcile, self.build_budget, self.build_advice]
        for name, build in zip(PAGES, builders):
            fr = ctk.CTkFrame(holder, fg_color="transparent")
            build(fr)
            self.pages[name] = fr
        self.show("Panel")
        self.refresh_all()
        self.after(5000, self.auto_sync_loop)
        if db.get_setting("watch_on") == "1":
            self.watch_sw.select()
            self.toggle_watch()
        self.after(8000, self.watch_loop)

    # ---------- iskelet ----------
    @staticmethod
    def month_label(m):
        y, mo = m.split("-")
        return f"{MONTHS[int(mo) - 1]} {y}"

    def refresh_months(self):
        ms = sorted(set(db.available_months()) | {dt.date.today().strftime("%Y-%m"), self.month}, reverse=True)
        self.month_map = {self.month_label(m): m for m in ms}
        self.month_menu.configure(values=list(self.month_map))
        self.month_menu.set(self.month_label(self.month))

    def on_month(self, label):
        self.month = self.month_map[label]
        self.refresh_all()

    def build_sidebar(self):
        side = ctk.CTkFrame(self, width=210, corner_radius=0, fg_color=SIDE)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="Finans\nAsistanı", font=F(22, True), justify="left",
                     text_color=TEXT).pack(anchor="w", padx=22, pady=(26, 22))
        self.nav = {}
        for name in PAGES:
            b = ctk.CTkButton(side, text=name, anchor="w", height=42, corner_radius=10, font=F(14, True),
                              fg_color="transparent", text_color=TEXT,
                              hover_color=("#e3e7ee", "#2f343b"), command=lambda n=name: self.show(n))
            b.pack(fill="x", padx=14, pady=2)
            self.nav[name] = b
        self.theme_sw = ctk.CTkSwitch(side, text="Karanlık mod", font=F(13), command=self.toggle_theme)
        self.theme_sw.select()
        self.theme_sw.pack(side="bottom", anchor="w", padx=22, pady=22)

    def show(self, name):
        for n, p in self.pages.items():
            p.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        self.title_lbl.configure(text=name)
        for n, b in self.nav.items():
            b.configure(fg_color="#1f6aa5" if n == name else "transparent",
                        text_color="white" if n == name else TEXT)

    def toggle_theme(self):
        ctk.set_appearance_mode("dark" if self.theme_sw.get() else "light")
        self.draw_chart()

    def refresh_all(self):
        self.refresh_months()
        self.refresh_dashboard(); self.refresh_expenses(); self.refresh_incomes(); self.refresh_bank_list()
        self.refresh_rules()
        self.refresh_cashflow(); self.refresh_advice()

    def render_alerts(self, parent, alerts):
        for w in parent.winfo_children():
            w.destroy()
        for a in alerts:
            row = ctk.CTkFrame(parent, fg_color=SOFT, corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkFrame(row, width=5, height=1, fg_color=LEVEL[a["level"]],
                         corner_radius=3).pack(side="left", fill="y", padx=(0, 10), pady=5)
            ctk.CTkLabel(row, text=a["text"], font=F(13), anchor="w", justify="left",
                         wraplength=820, text_color=TEXT).pack(side="left", fill="x", expand=True,
                                                               pady=9, padx=(0, 10))

    # ---------- panel ----------
    def build_dashboard(self, p):
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")
        self.stat = {}
        for i, (k, t) in enumerate((("spent", "Bu Ay Harcama"), ("budget", "Toplam Bütçe"),
                                    ("remaining", "Kalan Bütçe"), ("forecast", "Ay Sonu Tahmini"))):
            row.grid_columnconfigure(i, weight=1, uniform="s")
            c = card(row)
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            ctk.CTkLabel(c, text=t, font=F(13), text_color=MUTED).pack(anchor="w", padx=16, pady=(14, 0))
            v = ctk.CTkLabel(c, text="-", font=F(26, True), text_color=TEXT)
            v.pack(anchor="w", padx=16)
            s = ctk.CTkLabel(c, text="", font=F(12), text_color=MUTED)
            s.pack(anchor="w", padx=16, pady=(0, 14))
            self.stat[k] = (v, s)

        bottom = card(p)
        bottom.pack(side="bottom", fill="x")
        ctk.CTkLabel(bottom, text="Uyarılar ve Öneriler", font=F(16, True), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(12, 2))
        self.dash_alerts = ctk.CTkFrame(bottom, fg_color="transparent")
        self.dash_alerts.pack(fill="x", padx=16, pady=(0, 12))

        mid = ctk.CTkFrame(p, fg_color="transparent")
        mid.pack(fill="both", expand=True, pady=12)
        mid.grid_rowconfigure(0, weight=1)
        mid.grid_columnconfigure(0, weight=5, uniform="m")
        mid.grid_columnconfigure(1, weight=4, uniform="m")
        left = card(mid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        ctk.CTkLabel(left, text="Harcama Dağılımı", font=F(16, True), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(14, 0))
        self.fig = Figure(figsize=(5, 3.2), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)
        right = card(mid)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        ctk.CTkLabel(right, text="Kategori Bütçeleri", font=F(16, True), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(14, 4))
        self.cat_frame = ctk.CTkFrame(right, fg_color="transparent")
        self.cat_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))


    def refresh_dashboard(self):
        sm = an.month_summary(self.month)
        inc = sm["income_actual"] or sm["income"]
        self.stat["spent"][0].configure(text=fmt0(sm["spent"]))
        self.stat["spent"][1].configure(
            text=(f"{'Gerçek' if sm['income_actual'] else 'Beklenen'} gelirin %{sm['spent'] / inc * 100:.0f} kadarı"
                  if inc else ""))
        self.stat["budget"][0].configure(text=fmt0(sm["budget"]))
        self.stat["budget"][1].configure(text=f"Ayın {sm['elapsed']}. günü / {sm['total_days']}")
        over = sm["remaining"] < 0
        self.stat["remaining"][0].configure(text=fmt0(sm["remaining"]),
                                            text_color="#e74c3c" if over else "#2ecc71")
        self.stat["remaining"][1].configure(text="Bütçe aşıldı" if over else "Harcanabilir tutar")
        warn = sm["forecast"] > sm["budget"]
        self.stat["forecast"][0].configure(text=fmt0(sm["forecast"]),
                                           text_color="#f39c12" if warn else TEXT)
        self.stat["forecast"][1].configure(text="Bütçeyi aşabilir" if warn else "Bütçe dahilinde")

        for w in self.cat_frame.winfo_children():
            w.destroy()
        for s in an.budget_status(self.month):
            r = ctk.CTkFrame(self.cat_frame, fg_color="transparent")
            r.pack(fill="x", pady=1)
            top = ctk.CTkFrame(r, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text="●", text_color=s["color"], font=F(14)).pack(side="left")
            ctk.CTkLabel(top, text=s["name"], font=F(13, True), text_color=TEXT).pack(side="left", padx=6)
            ctk.CTkLabel(top, text=f"{s['spent']:,.0f} / {s['limit']:,.0f} ₺", font=F(12),
                         text_color=MUTED).pack(side="right")
            bar = ctk.CTkProgressBar(r, height=8, progress_color=bar_color(s["pct"]))
            bar.set(min(s["pct"] / 100, 1))
            bar.pack(fill="x", pady=(2, 0))
        self.draw_chart()
        self.render_alerts(self.dash_alerts, an.generate_alerts(self.month)[:2])

    def draw_chart(self):
        dark = ctk.get_appearance_mode() == "Dark"
        bg, fg = ("#24272c", "#f3f4f6") if dark else ("#ffffff", "#111827")
        data = [s for s in an.budget_status(self.month) if s["spent"] > 0]
        self.fig.clear()
        self.fig.patch.set_facecolor(bg)
        self.canvas.get_tk_widget().configure(bg=bg)
        ax = self.fig.add_subplot(111)
        ax.set_facecolor(bg)
        if data:
            total = sum(s["spent"] for s in data)
            wedges, _ = ax.pie([s["spent"] for s in data], colors=[s["color"] for s in data],
                               startangle=90, counterclock=False,
                               wedgeprops=dict(width=0.38, edgecolor=bg, linewidth=2))
            ax.text(0, 0, f"{total:,.0f} ₺", ha="center", va="center", fontsize=15,
                    fontweight="bold", color=fg)
            ax.legend(wedges, [f"{s['name']}  %{s['spent'] / total * 100:.0f}" for s in data],
                      loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False,
                      labelcolor=fg, fontsize=11)
        else:
            ax.text(0.5, 0.5, "Henüz harcama yok", ha="center", va="center", color=fg, fontsize=13)
            ax.axis("off")
        ax.set_aspect("equal")
        self.fig.subplots_adjust(left=0.02, right=0.62, top=0.98, bottom=0.02)
        self.canvas.draw()

    # ---------- nakit akışı ----------
    def build_cashflow(self, p):
        row = ctk.CTkFrame(p, fg_color="transparent")
        row.pack(fill="x")
        self.cf_stat = {}
        for i, (k, t) in enumerate((("now", "Bugünkü Bakiye"), ("min", "En Düşük Bakiye"),
                                    ("end", "Ay Sonu Bakiyesi"))):
            row.grid_columnconfigure(i, weight=1, uniform="c")
            c = card(row)
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            ctk.CTkLabel(c, text=t, font=F(13), text_color=MUTED).pack(anchor="w", padx=16, pady=(12, 0))
            v = ctk.CTkLabel(c, text="-", font=F(24, True), text_color=TEXT)
            v.pack(anchor="w", padx=16)
            sub = ctk.CTkLabel(c, text="", font=F(12), text_color=MUTED)
            sub.pack(anchor="w", padx=16, pady=(0, 12))
            self.cf_stat[k] = (v, sub)

        self.cf_warn = ctk.CTkFrame(p, fg_color=SOFT, corner_radius=10)
        self.cf_warn_lbl = ctk.CTkLabel(self.cf_warn, text="", font=F(13), text_color=TEXT,
                                        anchor="w", justify="left", wraplength=900)
        self.cf_warn_lbl.pack(side="left", padx=14, pady=10)

        cal = card(p)
        self.cf_cal = cal
        cal.pack(fill="both", expand=True, pady=(10, 0))
        ctk.CTkLabel(cal, text="Ay boyunca para giriş ve çıkışları", font=F(16, True),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        self.cf_caption = ctk.CTkLabel(cal, text="", font=F(12), text_color=MUTED,
                                       anchor="w", justify="left", wraplength=920)
        self.cf_caption.pack(anchor="w", padx=16, pady=(0, 8))
        self.cal_grid = ctk.CTkFrame(cal, fg_color="transparent")
        self.cal_grid.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def refresh_cashflow(self):
        cf = ins.cashflow(self.month)
        fmt_or = lambda v: fmt0(v) if v is not None else "—"
        self.cf_stat["now"][0].configure(text=fmt_or(cf["start_balance"]))
        self.cf_stat["now"][1].configure(text="kayıtlı hesap bakiyeniz")
        low = cf["min_balance"]
        self.cf_stat["min"][0].configure(text=fmt_or(low),
                                         text_color="#e74c3c" if low is not None and low < 0 else TEXT)
        self.cf_stat["min"][1].configure(text=(cf["min_date"] or "") if cf["is_current"]
                                         else "yalnızca bu ay için hesaplanır")
        end = cf["end_balance"]
        self.cf_stat["end"][0].configure(text=fmt_or(end),
                                         text_color="#e74c3c" if end is not None and end < 0 else "#2ecc71"
                                         if end is not None else TEXT)
        self.cf_stat["end"][1].configure(text="tahmini" if cf["is_current"] else "")

        self.cf_warn.pack_forget()
        if cf["is_current"] and low is not None and low < 0:
            self.cf_warn.configure(fg_color=("#fde8e6", "#4a2420"))
            self.cf_warn_lbl.configure(
                text=f"Dikkat: {cf['min_date']} tarihinde bakiyeniz {fmt(low)} seviyesine düşüyor. "
                     f"O tarihten önce düşecek sabit giderleri ya da harcama hızınızı gözden geçirin.")
            self.cf_warn.pack(fill="x", pady=(10, 0), before=self.cf_cal)
        self.cf_caption.configure(
            text=f"Geçmiş günlerde gerçekleşen, gelecek günlerde beklenen hareketler gösterilir. "
                 f"Bakiye eğrisi, kayıtlı hesap bakiyenizden başlar; gelecek günlere sabit giderler "
                 f"düştükleri güne, değişken harcama ise günlük ortalama "
                 f"({fmt(cf['daily_rate'])}) olarak eklenir. Her hücrede üstte o günün hareketi, "
                 f"altta gün sonu bakiyesi yazar."
            if cf["is_current"] else
            "Geçmiş bir ay görüntüleniyor: yalnızca gerçekleşen hareketler gösterilir, bakiye tahmini yapılmaz.")

        for w in self.cal_grid.winfo_children():
            w.destroy()
        for i, wd in enumerate(WEEKDAYS):
            self.cal_grid.grid_columnconfigure(i, weight=1, uniform="d")
            ctk.CTkLabel(self.cal_grid, text=wd, font=F(12, True), text_color=MUTED).grid(
                row=0, column=i, pady=(0, 4))
        for d in cf["days"]:
            pos = cf["first_weekday"] + d["day"] - 1
            cell = ctk.CTkFrame(self.cal_grid, corner_radius=8,
                                fg_color=("#e3edfb", "#23384f") if d["today"] else SOFT)
            cell.grid(row=pos // 7 + 1, column=pos % 7, sticky="nsew", padx=2, pady=2)
            self.cal_grid.grid_rowconfigure(pos // 7 + 1, weight=1, uniform="r")
            ctk.CTkLabel(cell, text=str(d["day"]), font=F(12, True),
                         text_color=TEXT if d["past"] or d["today"] else MUTED).pack(anchor="w", padx=8,
                                                                                     pady=(5, 0))
            net = (d["in"] - d["out"]) if d["past"] else (d["exp_in"] - d["exp_out"])
            if abs(net) >= 0.005:
                ctk.CTkLabel(cell, text=("+" if net > 0 else "") + fmt0(net), font=F(13, True),
                             text_color="#2ecc71" if net > 0 else "#e74c3c").pack(anchor="w", padx=8)
            for it in d["items"][:2]:
                ctk.CTkLabel(cell, text=it["name"][:14], font=F(11), text_color=MUTED).pack(anchor="w",
                                                                                            padx=8)
            if d["balance"] is not None:
                ctk.CTkLabel(cell, text=fmt0(d["balance"]), font=F(11),
                             text_color="#e74c3c" if d["balance"] < 0 else MUTED).pack(anchor="w", padx=8,
                                                                                       pady=(0, 5))
            else:
                ctk.CTkLabel(cell, text="", font=F(11)).pack(pady=(0, 5))

    # ---------- harcamalar ----------
    def build_expenses(self, p):
        f = card(p)
        f.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=14)
        self.e_amount = entry(inner, "Tutar (₺)", 120)
        self.e_date = entry(inner, "", 120)
        self.e_date.insert(0, dt.date.today().isoformat())
        self.e_desc = entry(inner, "Açıklama (örn. Migros)", 280)
        self.e_cat = ctk.CTkOptionMenu(inner, values=["Otomatik"] + self.cat_names, width=140, height=36,
                                       font=F(13))
        for w in (self.e_amount, self.e_date, self.e_desc, self.e_cat):
            w.pack(side="left", padx=(0, 10))
        primary(inner, "Harcama Ekle", self.add_manual).pack(side="left")
        self.exp_table = Table(p, ("Tarih", "Açıklama", "Kategori", "Tutar", "Kaynak"), (2, 5, 2, 2, 1))
        self.exp_table.pack(fill="both", expand=True)
        bar = ctk.CTkFrame(p, fg_color="transparent")
        bar.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(bar, text="Seçili kaydın kategorisi:", font=F(13), text_color=MUTED).pack(side="left")
        self.fix_cat = ctk.CTkOptionMenu(bar, values=self.cat_names, width=140, height=36, font=F(13))
        self.fix_cat.pack(side="left", padx=10)
        self.fix_learn = ctk.CTkSwitch(bar, text="Bu işyerini hep böyle kategorile", font=F(13))
        self.fix_learn.select()
        self.fix_learn.pack(side="left", padx=(0, 10))
        primary(bar, "Kategoriyi Değiştir", self.change_category, 170).pack(side="left")
        primary(bar, "Seçili Harcamayı Sil", self.delete_selected, 180,
                ("#c0392b", "#962d22")).pack(side="right")

    def change_category(self):
        """Kategoriyi düzeltir; istenirse aynı işyerinin sonraki kayıtları için kural öğrenir."""
        if not self.exp_table.selected_id:
            return messagebox.showinfo("Seçim yok", "Önce listeden bir harcamaya tıklayın.")
        exp = db.get_expense(self.exp_table.selected_id)
        cat = self.fix_cat.get()
        db.set_expense_category(exp["id"], db.category_id(cat))
        msg = f"'{exp['description'][:30]}' kaydı {cat} kategorisine taşındı."
        if self.fix_learn.get():
            key = an.merchant_key(exp["description"])
            if key:
                db.set_rule(key, db.category_id(cat))
                msg += f"\n\nArtık açıklamasında '{key}' geçen harcamalar otomatik {cat} olacak."
        messagebox.showinfo("Güncellendi", msg)
        self.refresh_all()

    def add_manual(self):
        try:
            amount = float(self.e_amount.get().replace(",", "."))
            dt.date.fromisoformat(self.e_date.get())
            if amount <= 0:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Hata", "Geçerli bir tutar ve tarih (YYYY-AA-GG) girin.")
        desc, cat = self.e_desc.get(), self.e_cat.get()
        cat = an.guess_category(desc) if cat == "Otomatik" else cat
        db.add_expense(amount, self.e_date.get(), desc, db.category_id(cat), "manual")
        self.e_amount.delete(0, "end"); self.e_desc.delete(0, "end")
        self.refresh_all()

    def delete_selected(self):
        if self.exp_table.selected_id:
            db.delete_expense(self.exp_table.selected_id)
            self.refresh_all()

    def refresh_expenses(self):
        self.exp_table.set_rows([(e["id"], [e["date"], e["description"], e["category"], fmt(e["amount"]),
                                            SOURCE.get(e["source"], e["source"])])
                                 for e in db.list_expenses(self.month)])

    # ---------- gelirler ----------
    def build_incomes(self, p):
        f = card(p)
        f.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=14)
        self.i_amount = entry(inner, "Tutar (₺)", 120)
        self.i_date = entry(inner, "", 120)
        self.i_date.insert(0, dt.date.today().isoformat())
        self.i_desc = entry(inner, "Açıklama (örn. Maaş)", 280)
        for w in (self.i_amount, self.i_date, self.i_desc):
            w.pack(side="left", padx=(0, 10))
        primary(inner, "Gelir Ekle", self.add_income).pack(side="left")
        self.inc_table = Table(p, ("Tarih", "Açıklama", "Tutar", "Kaynak"), (2, 6, 2, 1))
        self.inc_table.pack(fill="both", expand=True)
        primary(p, "Seçili Geliri Sil", self.delete_income, 160, ("#c0392b", "#962d22")).pack(
            anchor="e", pady=(10, 0))

    def add_income(self):
        try:
            amount = float(self.i_amount.get().replace(",", "."))
            dt.date.fromisoformat(self.i_date.get())
            if amount <= 0:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Hata", "Geçerli bir tutar ve tarih (YYYY-AA-GG) girin.")
        db.add_income(amount, self.i_date.get(), self.i_desc.get(), "manual")
        self.i_amount.delete(0, "end"); self.i_desc.delete(0, "end")
        self.refresh_all()

    def delete_income(self):
        if self.inc_table.selected_id:
            db.delete_income(self.inc_table.selected_id)
            self.refresh_all()

    def refresh_incomes(self):
        self.inc_table.set_rows([(i["id"], [i["date"], i["description"], fmt(i["amount"]),
                                            SOURCE.get(i["source"], i["source"])])
                                 for i in db.list_incomes(self.month)])

    # ---------- OCR ----------
    def build_ocr(self, p):
        top = card(p)
        top.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(top, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=14)
        primary(inner, "Fiş Görseli Seç", self.pick_receipt, 160).pack(side="left")
        self.ocr_status = ctk.CTkLabel(inner, text="JPG/PNG bir fiş fotoğrafı seçin.", font=F(13),
                                       text_color=MUTED)
        self.ocr_status.pack(side="left", padx=16)
        form = card(p)
        form.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(form, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=14)
        self.o_amount = entry(inner, "Tutar", 120)
        self.o_date = entry(inner, "YYYY-AA-GG", 120)
        self.o_desc = entry(inner, "İşyeri", 280)
        self.o_cat = ctk.CTkOptionMenu(inner, values=["Otomatik"] + self.cat_names, width=140, height=36,
                                       font=F(13))
        for w in (self.o_amount, self.o_date, self.o_desc, self.o_cat):
            w.pack(side="left", padx=(0, 10))
        primary(inner, "Onayla ve Kaydet", self.save_ocr, 160).pack(side="left")
        raw = card(p)
        raw.pack(fill="both", expand=True)
        ctk.CTkLabel(raw, text="Okunan ham metin", font=F(14, True), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(12, 4))
        self.o_raw = ctk.CTkTextbox(raw, font=F(13), fg_color=SOFT)
        self.o_raw.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def pick_receipt(self):
        path = filedialog.askopenfilename(filetypes=[("Görüntü", "*.png *.jpg *.jpeg *.bmp *.tiff")])
        if not path:
            return
        self.ocr_status.configure(text="Okunuyor... (ilk seferde 10-20 sn sürebilir)", text_color=MUTED)
        self.update_idletasks()

        def work():
            try:
                res = ocr.read_receipt(path)
            except Exception as ex:
                msg = str(ex) or repr(ex)  # 'ex' except bloğundan sonra silinir; metni önce saklıyoruz
                self.after(0, lambda m=msg: self.show_ocr_error(m))
                return
            self.after(0, lambda: self.show_ocr_safe(res))
        threading.Thread(target=work, daemon=True).start()

    def show_ocr_safe(self, res):
        try:
            self.show_ocr(res)
        except Exception as ex:
            self.show_ocr_error(f"Sonuç gösterilemedi: {ex!r}")

    def show_ocr_error(self, msg):
        self.ocr_status.configure(text="OCR başarısız oldu.", text_color="#e74c3c")
        messagebox.showerror("OCR hatası", msg)

    def show_ocr(self, res):
        for w, v in ((self.o_amount, res["amount"]), (self.o_date, res["date"] or dt.date.today().isoformat()),
                     (self.o_desc, res["merchant"])):
            w.delete(0, "end")
            w.insert(0, "" if v is None else str(v))
        self.o_raw.delete("1.0", "end")
        self.o_raw.insert("end", res["raw_text"])
        self.ocr_status.configure(text="Okuma tamam — değerleri kontrol edip kaydedin.", text_color="#2ecc71")

    def save_ocr(self):
        try:
            amount = float(self.o_amount.get().replace(",", "."))
            dt.date.fromisoformat(self.o_date.get())
        except ValueError:
            return messagebox.showerror("Hata", "Tutar/tarih geçersiz; düzeltip tekrar deneyin.")
        cat = self.o_cat.get()
        cat = an.guess_category(self.o_desc.get()) if cat == "Otomatik" else cat
        db.add_expense(amount, self.o_date.get(), self.o_desc.get(), db.category_id(cat), "ocr")
        self.ocr_status.configure(text="Kaydedildi.", text_color="#2ecc71")
        self.refresh_all()

    # ---------- hesap ve kart ----------
    def build_bank(self, p):
        sc = ctk.CTkScrollableFrame(p, fg_color="transparent")
        sc.pack(fill="both", expand=True)

        # bakiye
        row = ctk.CTkFrame(sc, fg_color="transparent")
        row.pack(fill="x")
        self.bal = {}
        for i, (k, t) in enumerate((("balance", "Hesap Bakiyesi"), ("income", "Bu Ay Gelir"),
                                    ("spent", "Bu Ay Gider"))):
            row.grid_columnconfigure(i, weight=1, uniform="b")
            c = card(row)
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            ctk.CTkLabel(c, text=t, font=F(13), text_color=MUTED).pack(anchor="w", padx=16, pady=(12, 0))
            v = ctk.CTkLabel(c, text="-", font=F(24, True), text_color=TEXT)
            v.pack(anchor="w", padx=16, pady=(0, 12))
            self.bal[k] = v
        bf = card(sc)
        bf.pack(fill="x", pady=10)
        inner = ctk.CTkFrame(bf, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(inner, text="Bakiyeyi elle güncelle:", font=F(13), text_color=MUTED).pack(side="left")
        self.bal_entry = entry(inner, "örn. 32215,70", 150)
        self.bal_entry.pack(side="left", padx=10)
        primary(inner, "Kaydet", self.save_balance, 100).pack(side="left")
        self.bal_note = ctk.CTkLabel(bf, text="", font=F(12), text_color=MUTED, anchor="w",
                                     justify="left", wraplength=900)
        self.bal_note.pack(fill="x", padx=16, pady=(0, 12))

        wf = card(sc)
        wf.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(wf, text="Ekstreyi kendiliğinden yükle", font=F(16, True),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(wf, text="Bir klasörü izler; bankadan indirdiğiniz hesap hareketi dosyasını tanıyıp "
                              "kendisi içeri aktarır. Dosya seçmeniz gerekmez. Yalnızca borç/alacak veya "
                              "bakiye sütunu olan hesap ekstrelerini alır; tanıyamadığı dosyalara dokunmaz. "
                              "Bakiyeye dokunmaz, çünkü birden fazla hesabınız olabilir.",
                     font=F(12), text_color=MUTED, wraplength=900, justify="left").pack(anchor="w", padx=16)
        wr = ctk.CTkFrame(wf, fg_color="transparent")
        wr.pack(fill="x", padx=16, pady=10)
        self.watch_sw = ctk.CTkSwitch(wr, text="Klasörü izle", font=F(13), command=self.toggle_watch)
        self.watch_sw.pack(side="left")
        self.watch_entry = entry(wr, "izlenecek klasör", 330)
        self.watch_entry.insert(0, db.get_setting("watch_dir") or self.default_watch_dir())
        self.watch_entry.pack(side="left", padx=10)
        primary(wr, "Klasör Seç", self.pick_watch_dir, 120, ("#5b6770", "#46515a")).pack(side="left")
        self.watch_note = ctk.CTkLabel(wf, text="İzleme kapalı.", font=F(12), text_color=MUTED,
                                       anchor="w", justify="left", wraplength=900)
        self.watch_note.pack(fill="x", padx=16, pady=(0, 12))

        # ekstre içe aktarma
        imp = card(sc)
        imp.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(imp, text="Banka ekstresi yükle (CSV / Excel)", font=F(16, True), text_color=TEXT).pack(
            anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(imp, text="İnternet/mobil bankacılığınızdan indirdiğiniz hesap hareketlerini veya kart "
                               "ekstresini seçin. Aynı dosyayı tekrar yüklemek kayıtları çoğaltmaz.",
                     font=F(12), text_color=MUTED, wraplength=900, justify="left").pack(anchor="w", padx=16)
        r1 = ctk.CTkFrame(imp, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=10)
        primary(r1, "Dosya Seç", self.pick_statement, 130).pack(side="left")
        self.st_mode = ctk.CTkOptionMenu(r1, values=["Hesap hareketleri", "Kart ekstresi"], width=170,
                                         height=36, font=F(13), command=lambda _: self.preview_statement())
        self.st_mode.pack(side="left", padx=10)
        self.skip_sw = ctk.CTkSwitch(r1, text="Kart ödemesi ve virmanları atla", font=F(13),
                                     command=self.preview_statement)
        self.skip_sw.select()
        self.skip_sw.pack(side="left", padx=10)
        self.st_status = ctk.CTkLabel(imp, text="Henüz dosya seçilmedi.", font=F(13), text_color=MUTED,
                                      anchor="w", justify="left", wraplength=900)
        self.st_status.pack(fill="x", padx=16)

        self.map_menus, self.map_vals = {}, {}
        mg = ctk.CTkFrame(imp, fg_color="transparent")
        mg.pack(fill="x", padx=16, pady=8)
        for i, (k, t) in enumerate((("date", "Tarih"), ("desc", "Açıklama"), ("amount", "Tutar"),
                                    ("debit", "Borç"), ("credit", "Alacak"), ("balance", "Bakiye"))):
            mg.grid_columnconfigure(i, weight=1, uniform="m")
            ctk.CTkLabel(mg, text=t, font=F(12), text_color=MUTED).grid(row=0, column=i, sticky="w", padx=(0, 6))
            om = ctk.CTkOptionMenu(mg, values=["—"], height=32, font=F(12), dynamic_resizing=False,
                                   command=lambda _: self.preview_statement())
            om.grid(row=1, column=i, sticky="ew", padx=(0, 6))
            self.map_menus[k] = om
        ctk.CTkLabel(imp, text="Sütunlar otomatik eşleşti. Yanlışsa yukarıdan düzeltin; önizleme anında güncellenir.",
                     font=F(12), text_color=MUTED).pack(anchor="w", padx=16)

        self.st_table = Table(imp, ("Tarih", "Açıklama", "Tür", "Tutar"), (2, 5, 3, 2), limit=400)
        self.st_table.body.configure(height=240)
        self.st_table.pack(fill="x", padx=12, pady=10)
        r2 = ctk.CTkFrame(imp, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(0, 14))
        self.st_import_btn = primary(r2, "İçe Aktar", self.import_statement, 140)
        self.st_import_btn.pack(side="left")
        self.st_import_btn.configure(state="disabled")
        primary(r2, "Ekstre Kayıtlarını Sil", self.clear_statements, 190, ("#c0392b", "#962d22")).pack(side="right")
        self.st_headers, self.st_rows, self.st_parsed = [], [], None

        # demo banka servisi (geliştirme amaçlı)
        demo = card(sc)
        demo.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(demo, text="Demo banka servisi (geliştirme / sunum)", font=F(14, True),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(demo, text="Gerçek veri değildir. Açık Bankacılık (ÖHVPS) entegrasyonunun yerini tutan "
                                "FastAPI servisidir; gerçek hesabınız için yukarıdaki ekstre yüklemeyi kullanın.",
                     font=F(12), text_color=MUTED, wraplength=900, justify="left").pack(anchor="w", padx=16)
        inner = ctk.CTkFrame(demo, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)
        primary(inner, "Demo Senkronize Et", self.sync_now, 170, ("#5b6770", "#46515a")).pack(side="left")
        primary(inner, "Test Harcaması", self.simulate_tx, 150, ("#5b6770", "#46515a")).pack(side="left", padx=10)
        self.auto_sw = ctk.CTkSwitch(inner, text="Otomatik senkron (5 sn)", font=F(13))
        self.auto_sw.pack(side="left", padx=14)
        self.bank_status = ctk.CTkLabel(demo, text="", font=F(12), text_color=MUTED, anchor="w",
                                        wraplength=900, justify="left")
        self.bank_status.pack(fill="x", padx=16, pady=(0, 12))
        self.bank_table = Table(demo, ("Tarih", "İşyeri", "Kategori", "Tutar"), (2, 4, 2, 2))
        self.bank_table.body.configure(height=160)
        self.bank_table.pack(fill="x", padx=12, pady=(0, 12))

    def refresh_balance(self):
        sm = an.month_summary(self.month)
        cipa, gun, delta, adet = db.balance_detail()
        self.bal["balance"].configure(text=fmt0(cipa + delta))
        if gun and adet:
            self.bal_note.configure(
                text=f"{gun} tarihindeki {fmt(cipa)} bakiyeye, sonraki {adet} hareket işlenerek "
                     f"hesaplandı ({'+' if delta >= 0 else ''}{fmt(delta)}). Elle güncellemeniz gerekmez; "
                     f"yeni ekstre yüklediğinizde çıpa kendiliğinden ileri alınır.")
        elif gun:
            self.bal_note.configure(text=f"{gun} tarihinden bu yana kayıtlı hareket yok.")
        else:
            self.bal_note.configure(text="Bakiye girilmedi. Hesap hareketi ekstresi yüklerseniz "
                                         "dosyadan otomatik alınır.")
        self.bal["income"].configure(text=fmt0(sm["income_actual"]), text_color="#2ecc71")
        self.bal["spent"].configure(text=fmt0(sm["spent"]), text_color="#e74c3c")

    def save_balance(self):
        try:
            db.set_balance(float(self.bal_entry.get().replace(".", "").replace(",", ".")
                                 if "," in self.bal_entry.get() else self.bal_entry.get()))
        except ValueError:
            return messagebox.showerror("Hata", "Geçerli bir tutar girin.")
        self.bal_entry.delete(0, "end")
        self.refresh_all()

    # --- klasör izleme ---
    @staticmethod
    def default_watch_dir():
        yol = os.path.join(os.path.expanduser("~"), "Downloads")
        return yol if os.path.isdir(yol) else os.path.expanduser("~")

    def pick_watch_dir(self):
        yol = filedialog.askdirectory(initialdir=self.watch_entry.get() or self.default_watch_dir())
        if yol:
            self.watch_entry.delete(0, "end")
            self.watch_entry.insert(0, yol)
            db.set_setting("watch_dir", yol)

    def toggle_watch(self):
        if not self.watch_sw.get():
            db.set_setting("watch_on", "0")
            return self.watch_note.configure(text="İzleme kapalı.", text_color=MUTED)
        yol = self.watch_entry.get().strip()
        if not os.path.isdir(yol):
            self.watch_sw.deselect()
            return messagebox.showerror("Klasör yok", "Geçerli bir klasör seçin.")
        db.set_setting("watch_dir", yol)
        db.set_setting("watch_on", "1")
        self.watch_note.configure(text=f"İzleniyor: {yol}  ·  yeni ekstre indirdiğinizde kendiliğinden "
                                       f"aktarılacak.", text_color="#2ecc71")
        self.scan_watch_dir()

    def watch_loop(self):
        if self.watch_sw.get():
            self.scan_watch_dir()
        self.after(8000, self.watch_loop)

    def scan_watch_dir(self):
        """Klasördeki yeni ekstre dosyalarını arar. Dosya okuma yavaş olabileceği için ayrı
        iş parçacığında çalışır."""
        yol = self.watch_entry.get().strip()
        if not os.path.isdir(yol) or getattr(self, "_watching", False):
            return
        self._watching = True

        def work():
            sonuc = []
            try:
                adaylar = []
                for uzanti in ("*.csv", "*.xlsx", "*.xlsm", "*.txt"):
                    adaylar += glob.glob(os.path.join(yol, uzanti))
                for p in sorted(adaylar, key=os.path.getmtime)[-40:]:
                    try:
                        st_ = os.stat(p)
                        key = f"{os.path.basename(p)}|{st_.st_size}|{int(st_.st_mtime)}"
                        if db.file_seen(key):
                            continue
                        db.mark_file_seen(key)
                        basliklar, satirlar, esleme = statement.load(p)
                        # yalnızca net biçimli hesap ekstrelerini al; şüpheli dosyaya dokunma
                        if esleme["date"] is None or not (esleme["balance"] is not None
                                                          or (esleme["debit"] is not None
                                                              and esleme["credit"] is not None)):
                            continue
                        p_ = statement.parse_rows(satirlar, esleme, "account", True)
                        kayitlar = [r for r in p_["records"] if r["kind"] != "skip"]
                        if len(kayitlar) < 3:
                            continue
                        res = statement.import_records(p_["records"])
                        if res["expenses"] or res["incomes"]:
                            # Bakiyeye bilerek dokunulmuyor: birden fazla hesabınız varsa son
                            # okunan dosyanın bakiyesi toplamı değil, tek hesabı gösterirdi.
                            sonuc.append((os.path.basename(p), res))
                    except Exception:
                        continue
            finally:
                self._watching = False          # arayüz güncellenemese de tarama kilitli kalmasın
                try:
                    self.after(0, lambda: self.after_watch(sonuc))
                except Exception:
                    pass                        # pencere kapanmışsa sorun değil
        threading.Thread(target=work, daemon=True).start()

    def after_watch(self, sonuc):
        if not sonuc:
            return
        toplam_g = sum(r["expenses"] for _, r in sonuc)
        toplam_i = sum(r["incomes"] for _, r in sonuc)
        adlar = ", ".join(ad for ad, _ in sonuc)
        self.watch_note.configure(
            text=f"{dt.datetime.now():%H:%M} — {adlar} içeri aktarıldı: {toplam_g} gider, "
                 f"{toplam_i} gelir.", text_color="#2ecc71")
        self.refresh_all()
        messagebox.showinfo("Ekstre bulundu",
                            f"{adlar}\n\n{toplam_g} gider ve {toplam_i} gelir eklendi.\n"
                            f"Bakiye değiştirilmedi; işlemler güncel bakiyeye zaten yansıyor.")

    # --- ekstre ---
    def pick_statement(self):
        path = filedialog.askopenfilename(filetypes=[("Ekstre", "*.csv *.xlsx *.xlsm *.txt"), ("Tümü", "*.*")])
        if not path:
            return
        try:
            self.st_headers, self.st_rows, auto = statement.load(path)
        except Exception as ex:
            msg = str(ex) or "Dosya okunamadı."
            return messagebox.showerror("Ekstre okunamadı", msg)
        opts = ["—"] + [f"{i + 1}. {h or '(boş)'}" for i, h in enumerate(self.st_headers)]
        for k, om in self.map_menus.items():
            om.configure(values=opts)
            om.set(opts[auto[k] + 1] if auto.get(k) is not None else "—")
        card_like = auto.get("amount") is not None and auto.get("debit") is None and auto.get("balance") is None
        self.st_mode.set("Kart ekstresi" if card_like and "kart" in " ".join(self.st_headers).lower() else
                         "Hesap hareketleri")
        self.preview_statement()

    def _mapping(self):
        m = {}
        for k, om in self.map_menus.items():
            v = om.get()
            m[k] = None if v == "—" else int(v.split(".", 1)[0]) - 1
        return m

    def preview_statement(self):
        if not self.st_rows:
            return
        m = self._mapping()
        if m["date"] is None or not any(m[k] is not None for k in ("amount", "debit", "credit")):
            self.st_table.set_rows([])
            self.st_parsed = None
            self.st_import_btn.configure(state="disabled")
            return self.st_status.configure(text="Tarih ve tutar (veya borç/alacak) sütunlarını seçin.",
                                            text_color="#f39c12")
        mode = "card" if self.st_mode.get() == "Kart ekstresi" else "account"
        self.st_parsed = statement.parse_rows(self.st_rows, m, mode, bool(self.skip_sw.get()))
        recs = self.st_parsed["records"]
        names = {"expense": "Gider", "income": "Gelir"}
        self.st_table.set_rows([(n, [r["date"], r["desc"], names.get(r["kind"], "Atlanır: " + r["reason"]),
                                     fmt(r["amount"])]) for n, r in enumerate(recs)])
        cnt = {k: sum(1 for r in recs if r["kind"] == k) for k in ("expense", "income", "skip")}
        txt = f"{cnt['expense']} gider, {cnt['income']} gelir, {cnt['skip']} atlanan işlem bulundu."
        if self.st_parsed["balance"] is not None:
            txt += f"  Dosyadaki son bakiye: {fmt(self.st_parsed['balance'])}"
        self.st_status.configure(text=txt, text_color="#2ecc71" if recs else "#f39c12")
        self.st_import_btn.configure(state="normal" if recs else "disabled")

    def import_statement(self):
        if not self.st_parsed:
            return
        res = statement.import_records(self.st_parsed["records"])
        bal = self.st_parsed["balance"]
        msg = (f"{res['expenses']} gider ve {res['incomes']} gelir eklendi.\n"
               f"{res['duplicates']} kayıt zaten vardı (atlandı), {res['skipped']} işlem hariç tutuldu.")
        if bal is not None and self.st_mode.get() == "Hesap hareketleri" and abs(bal - db.get_balance()) > 0.005:
            if messagebox.askyesno("Bakiye", msg + f"\n\nHesap bakiyesi {fmt(bal)} olarak güncellensin mi?\n"
                                                   f"(Bu tarihten sonraki hareketler otomatik işlenecek.)"):
                son = max((r["date"] for r in self.st_parsed["records"]), default=None)
                db.set_balance(bal, son)
        else:
            messagebox.showinfo("İçe aktarıldı", msg)
        self.st_import_btn.configure(state="disabled")
        self.refresh_all()
        self.rc_all.select()                      # ekstre birden çok ayı kapsayabilir
        if self.scan_duplicates() and messagebox.askyesno(
                "Çift kayıt", f"{len(self._pairs)} kayıt, daha önce SMS/fiş ile girilmiş harcamalarla "
                              f"eşleşiyor.\n\nMutabakat sayfasına gidilsin mi?"):
            self.show("Mutabakat")

    def clear_statements(self):
        if messagebox.askyesno("Onay", "Ekstreden içe aktarılan tüm harcama ve gelirler silinsin mi?\n"
                                       "(Elle girilen, fişten okunan kayıtlar silinmez.)"):
            n = db.delete_by_source("ekstre") + db.delete_incomes_by_source("ekstre")
            messagebox.showinfo("Silindi", f"{n} kayıt silindi.")
            self.refresh_all()

    # --- demo banka ---
    def sync_now(self):
        def work():
            try:
                n = bank_client.sync()
                self.after(0, lambda: self.after_sync(n))
            except Exception:
                self.after(0, lambda: self.bank_status.configure(
                    text="Demo servise ulaşılamadı (gerçek ekstre yüklemek için gerekmez). Çalıştırmak için:  "
                         "python -m uvicorn mock_bank:app --port 8001", text_color="#e74c3c"))
        threading.Thread(target=work, daemon=True).start()

    def after_sync(self, n):
        self.bank_status.configure(text=f"{dt.datetime.now():%H:%M:%S} — {n} yeni demo işlem alındı",
                                   text_color="#2ecc71")
        if n:
            self.refresh_all()

    def simulate_tx(self):
        try:
            bank_client.simulate()
            self.sync_now()
        except Exception:
            self.bank_status.configure(text="Demo servise ulaşılamadı.", text_color="#e74c3c")

    def auto_sync_loop(self):
        if self.auto_sw.get():
            self.sync_now()
        self.after(5000, self.auto_sync_loop)

    def refresh_bank_list(self):
        self.refresh_balance()
        rows = [e for e in db.list_expenses(self.month) if e["source"] == "bank"]
        self.bank_table.set_rows([(e["id"], [e["date"], e["description"], e["category"], fmt(e["amount"])])
                                  for e in rows])

    # ---------- mutabakat ----------
    def build_reconcile(self, p):
        top = card(p)
        top.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(top, text="Çift kayıt denetimi", font=F(16, True),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(14, 2))
        ctk.CTkLabel(top, text="Aynı harcama birden çok yoldan girebilir: SMS anında gelir, fişi aynı gün "
                               "okutursunuz, ekstre ise ay sonunda yüklenir. Bu sayfa aynı işlemi gösteren "
                               "kayıtları eşleştirir ve bankanın resmi kaydını (ekstre) asıl kabul edip "
                               "diğerini siler. Böylece harcamanız iki kez sayılmaz.",
                     font=F(12), text_color=MUTED, wraplength=900, justify="left").pack(anchor="w", padx=16)
        r1 = ctk.CTkFrame(top, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=10)
        primary(r1, "Çiftleri Tara", self.scan_duplicates, 150).pack(side="left")
        self.rc_all = ctk.CTkSwitch(r1, text="Tüm aylarda ara", font=F(13))
        self.rc_all.pack(side="left", padx=14)
        self.rc_status = ctk.CTkLabel(top, text="Henüz tarama yapılmadı.", font=F(12), text_color=MUTED,
                                      anchor="w", wraplength=900, justify="left")
        self.rc_status.pack(fill="x", padx=16, pady=(0, 12))

        lst = card(p)
        lst.pack(fill="both", expand=True)
        ctk.CTkLabel(lst, text="Eşleşen kayıtlar", font=F(14, True),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 4))
        self.rc_table = Table(lst, ("Olasılık", "Silinecek kayıt", "Kalacak kayıt (asıl)", "Tutar"),
                              (2, 5, 5, 3), limit=200, checkable=True)
        self.rc_table.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        r2 = ctk.CTkFrame(lst, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=(0, 14))
        primary(r2, "Tümünü Seç", lambda: self.rc_table.check_all(True), 120,
                ("#5b6770", "#46515a")).pack(side="left")
        primary(r2, "Seçilenleri Birleştir", self.merge_duplicates, 190).pack(side="left", padx=10)
        self._pairs = []

    def scan_duplicates(self, silent=False):
        month = None if self.rc_all.get() else self.month
        self._pairs = rc.find_duplicates(month)
        self.refresh_reconcile()
        scope = "tüm aylarda" if month is None else f"{self.month_label(self.month)} ayında"
        if self._pairs:
            total = sum(p["drop"]["amount"] for p in self._pairs)
            self.rc_status.configure(
                text=f"{scope} {len(self._pairs)} olası çift kayıt bulundu; toplam {fmt(total)} fazladan "
                     f"sayılıyor. Satırlara tıklayıp seçin ve birleştirin.", text_color="#f39c12")
        else:
            self.rc_status.configure(text=f"{scope} çift kayıt bulunamadı; veriler tutarlı görünüyor.",
                                     text_color="#2ecc71")
        return len(self._pairs)

    def refresh_reconcile(self):
        rows = []
        for i, p in enumerate(self._pairs):
            d, k = p["drop"], p["keep"]
            gap = "aynı gün" if p["gap"] == 0 else f"+{p['gap']} gün"
            rows.append((i, [f"%{p['score'] * 100:.0f}",
                             f"{rc.SOURCE_TR.get(d['source'], d['source'])} · {d['description'][:24]} · {d['date']}",
                             f"{rc.SOURCE_TR.get(k['source'], k['source'])} · {k['description'][:24]} · {k['date']}",
                             f"{fmt(d['amount'])} · {gap}"]))
        self.rc_table.set_rows(rows)

    def merge_duplicates(self):
        chosen = [self._pairs[i] for i in sorted(self.rc_table.checked) if i < len(self._pairs)]
        if not chosen:
            return messagebox.showinfo("Seçim yok", "Birleştirmek istediğiniz satırlara tıklayarak seçin.")
        total = sum(p["drop"]["amount"] for p in chosen)
        if not messagebox.askyesno("Onay", f"{len(chosen)} çift birleştirilecek; her çiftte düşük öncelikli "
                                           f"kayıt silinecek.\nToplam {fmt(total)} fazladan sayım "
                                           f"düzeltilecek.\n\nDevam edilsin mi?"):
            return
        n = rc.merge(chosen)
        self._pairs = []
        self.refresh_all()
        self.scan_duplicates()
        messagebox.showinfo("Birleştirildi", f"{n} çift kayıt birleştirildi.")

    # ---------- bütçe ----------
    def build_budget(self, p):
        c = card(p)
        c.pack(anchor="nw")
        ctk.CTkLabel(c, text="Aylık gelir ve kategori limitleri (₺)", font=F(16, True), text_color=TEXT).pack(
            anchor="w", padx=20, pady=(16, 6))
        grid = ctk.CTkFrame(c, fg_color="transparent")
        grid.pack(padx=20, pady=4)
        self.b_entries = {}
        ctk.CTkLabel(grid, text="Beklenen aylık gelir", font=F(14, True), text_color=TEXT).grid(
            row=0, column=0, padx=(0, 20), pady=6, sticky="w")
        self.income_e = entry(grid, "", 160)
        self.income_e.insert(0, db.get_setting("monthly_income", "0"))
        self.income_e.grid(row=0, column=1)
        for i, cat in enumerate(self.cats, 1):
            ctk.CTkLabel(grid, text="●  " + cat["name"], font=F(14), text_color=TEXT).grid(
                row=i, column=0, padx=(0, 20), pady=6, sticky="w")
            e = entry(grid, "", 160)
            e.insert(0, f"{cat['monthly_limit']:.0f}")
            e.grid(row=i, column=1)
            self.b_entries[cat["id"]] = e
        primary(c, "Kaydet", self.save_budget, 140).pack(anchor="w", padx=20, pady=16)

        rl = card(p)
        rl.pack(fill="both", expand=True, pady=(10, 0))
        ctk.CTkLabel(rl, text="Öğrenilen kategori kuralları", font=F(14, True),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(rl, text="Harcamalar sayfasında bir kaydın kategorisini düzelttiğinizde, aynı işyerinin "
                              "sonraki harcamaları otomatik olarak o kategoriye atanır.",
                     font=F(12), text_color=MUTED, wraplength=820, justify="left").pack(anchor="w", padx=16)
        self.rule_list = ctk.CTkScrollableFrame(rl, fg_color="transparent", height=150)
        self.rule_list.pack(fill="both", expand=True, padx=12, pady=10)

    def refresh_rules(self):
        for w in self.rule_list.winfo_children():
            w.destroy()
        rules = db.get_rules()
        if not rules:
            return ctk.CTkLabel(self.rule_list, text="Henüz öğrenilmiş kural yok.", font=F(13),
                                text_color=MUTED).pack(pady=16)
        for pattern, name, _ in rules:
            row = ctk.CTkFrame(self.rule_list, fg_color=SOFT, corner_radius=8)
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"'{pattern}'  →  {name}", font=F(13), text_color=TEXT,
                         anchor="w").pack(side="left", padx=12, pady=8)
            primary(row, "Sil", lambda q=pattern: (db.delete_rule(q), self.refresh_all()), 70,
                    ("#c0392b", "#962d22")).pack(side="right", padx=8, pady=5)

    def save_budget(self):
        try:
            db.set_setting("monthly_income", float(self.income_e.get()))
            for cid, e in self.b_entries.items():
                db.set_limit(cid, float(e.get()))
        except ValueError:
            return messagebox.showerror("Hata", "Sayısal değer girin.")
        self.refresh_all()

    # ---------- öneriler ----------
    def build_advice(self, p):
        primary(p, "Analizi Yenile", self.refresh_all, 150).pack(anchor="w", pady=(0, 10))
        fx = card(p)
        fx.pack(fill="x", pady=(0, 10))
        head = ctk.CTkFrame(fx, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(12, 2))
        ctk.CTkLabel(head, text="Aylık sabit giderler", font=F(16, True),
                     text_color=TEXT).pack(side="left")
        self.fixed_total_lbl = ctk.CTkLabel(head, text="", font=F(16, True), text_color="#f39c12")
        self.fixed_total_lbl.pack(side="right")
        ctk.CTkLabel(fx, text="Geçmişte her ay tekrar eden ve tutarı değişmeyen ödemeler. Bunlar ay sonu "
                              "tahmininde günlük harcamaya yayılmaz, düşecekleri gün beklenir.",
                     font=F(12), text_color=MUTED, wraplength=880, justify="left").pack(anchor="w", padx=16)
        self.fixed_list = ctk.CTkFrame(fx, fg_color="transparent")
        self.fixed_list.pack(fill="x", padx=16, pady=(6, 12))
        self.advice_box = ctk.CTkScrollableFrame(p, fg_color=CARD, corner_radius=14)
        self.advice_box.pack(fill="both", expand=True)

    def refresh_advice(self):
        for w in self.fixed_list.winfo_children():
            w.destroy()
        items = ins.active_fixed(self.month)
        self.fixed_total_lbl.configure(text=fmt(sum(r["amount"] for r in items)) + " / ay" if items else "")
        if not items:
            ctk.CTkLabel(self.fixed_list, text="Henüz tekrarlayan ödeme bulunamadı. En az iki aylık veri "
                                               "yükleyince abonelikleriniz burada listelenir.",
                         font=F(13), text_color=MUTED).pack(anchor="w", pady=8)
        paid = {tp.merchant_key(e["description"]) for e in db.list_expenses(self.month, limit=2000)}
        for r in items:
            row = ctk.CTkFrame(self.fixed_list, fg_color=SOFT, corner_radius=8)
            row.pack(fill="x", pady=2)
            durum = "ödendi" if r["key"] in paid else f"her ayın {r['day']}. günü bekleniyor"
            ctk.CTkLabel(row, text=f"{r['name'][:34]}", font=F(13, True), text_color=TEXT,
                         anchor="w").pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(row, text=fmt(r["amount"]), font=F(13, True),
                         text_color=TEXT).pack(side="right", padx=12)
            ctk.CTkLabel(row, text=durum, font=F(12),
                         text_color="#2ecc71" if r["key"] in paid else MUTED).pack(side="right", padx=12)
        self.render_alerts(self.advice_box, an.generate_alerts(self.month))


if __name__ == "__main__":
    print(f"Veritabanı: {db.DB_PATH}")      # hangi dosyanın açıldığı net görünsün
    App().mainloop()
