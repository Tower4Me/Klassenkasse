"""
Klassenkasse - Klassenkassen-Verwaltung
Requires: pip install pystray pillow
Start ohne CMD-Fenster: klassenkasse.pyw (auf Windows mit pythonw.exe)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import os
import sys
import threading
import traceback
import logging
from datetime import datetime
from PIL import Image, ImageDraw

# --------------------------------------------------------------------------- #
#  Logging (Fehler in Datei schreiben statt CMD)
# --------------------------------------------------------------------------- #

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "klassenkasse.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)


def log_exception(exc_type, exc_value, exc_tb):
    """Ungefangene Exceptions in Log-Datei schreiben statt abstürzen."""
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
    messagebox.showerror(
        "Unerwarteter Fehler",
        f"{exc_type.__name__}: {exc_value}\n\nDetails in: {LOG_PATH}",
    )


sys.excepthook = log_exception


# --------------------------------------------------------------------------- #
#  Datenbank
# --------------------------------------------------------------------------- #

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "klassenkasse.db")


def db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")   # robuster bei gleichzeitigem Zugriff
    con.execute("PRAGMA foreign_keys=ON")
    return con


def db_init():
    con = db_connect()
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS schueler (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT    NOT NULL,
            bezahlt INTEGER NOT NULL DEFAULT 0 CHECK (bezahlt IN (0,1)),
            betrag  REAL    NOT NULL DEFAULT 10.0 CHECK (betrag >= 0)
        );
        CREATE TABLE IF NOT EXISTS events (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            titel        TEXT NOT NULL,
            datum        TEXT NOT NULL,
            kosten       REAL NOT NULL DEFAULT 0.0 CHECK (kosten >= 0),
            beschreibung TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS notizen (
            id   INTEGER PRIMARY KEY CHECK (id = 1),
            text TEXT NOT NULL DEFAULT ''
        );
        INSERT OR IGNORE INTO settings VALUES ('standard_betrag', '10.0');
        INSERT OR IGNORE INTO notizen (id, text) VALUES (1, '');
    """)
    con.commit()
    con.close()


# --------------------------------------------------------------------------- #
#  Tray-Icon
# --------------------------------------------------------------------------- #

def _make_tray_image() -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, size - 2, size - 2], fill="#2d6a4f")
    # Euro-Zeichen als einfaches Rechteck-Muster
    d.rectangle([20, 20, 44, 44], fill="#2d6a4f", outline="white", width=3)
    d.text((16, 16), "KK", fill="white")
    return img


def setup_tray(app_window: tk.Tk):
    try:
        import pystray

        def show_window(icon, item):
            app_window.after(0, app_window.deiconify)
            app_window.after(50, app_window.lift)

        def quit_app(icon, item):
            icon.stop()
            app_window.after(0, app_window.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("Öffnen", show_window, default=True),
            pystray.MenuItem("Beenden", quit_app),
        )
        icon = pystray.Icon(
            "Klassenkasse", _make_tray_image(), "Klassenkasse", menu
        )
        t = threading.Thread(target=icon.run, daemon=True)
        t.start()
        return icon
    except Exception:
        logging.exception("Tray-Icon konnte nicht gestartet werden")
        return None


# --------------------------------------------------------------------------- #
#  Design-Konstanten
# --------------------------------------------------------------------------- #

C = {
    "bg":       "#1a1a2e",
    "panel":    "#16213e",
    "accent":   "#2d6a4f",
    "accent2":  "#40916c",
    "text":     "#e8f5e9",
    "sub":      "#95d5b2",
    "green":    "#40916c",
    "red":      "#e63946",
    "row_even": "#1e2d40",
    "row_odd":  "#16213e",
    "border":   "#2d4a6e",
    "cb_check": "#d4edda",   # Checkbox-Hintergrund wenn angehakt (helles Grün)
}

FH  = ("Segoe UI", 13, "bold")
FB  = ("Segoe UI", 10)
FL  = ("Segoe UI", 28, "bold")
FS  = ("Segoe UI", 9)


def _entry(parent, textvariable, width=10, **kw) -> tk.Entry:
    return tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg=C["bg"], fg=C["text"],
        font=FB,
        insertbackground=C["text"],
        relief="flat",
        highlightthickness=1,
        highlightbackground=C["border"],
        **kw,
    )


def _btn(parent, text, command, color=None, **kw) -> tk.Button:
    kw.setdefault("font", FB)
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=color or C["accent"],
        fg="white",
        relief="flat",
        cursor="hand2",
        padx=10,
        pady=4,
        **kw,
    )


# --------------------------------------------------------------------------- #
#  Haupt-Applikation
# --------------------------------------------------------------------------- #

class KlassenkasseApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Klassenkasse")
        self.geometry("980x700")
        self.minsize(880, 620)
        self.configure(bg=C["bg"])
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        # Interne Zustandsvariablen
        self._check_vars: dict[int, tk.BooleanVar] = {}
        self._select_all_var = tk.BooleanVar(value=False)

        db_init()
        self._build_ui()
        self.tray = setup_tray(self)
        self._refresh_all()

    # ------------------------------------------------------------------ #
    #  UI-Aufbau
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        hdr = tk.Frame(self, bg=C["accent"], pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Klassenkasse", font=("Segoe UI", 16, "bold"),
                 bg=C["accent"], fg="white").pack(side="left", padx=16)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=C["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=C["panel"],
                        foreground=C["sub"], padding=[14, 6], font=FB)
        style.map("TNotebook.Tab",
                  background=[("selected", C["accent"])],
                  foreground=[("selected", "white")])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_kasse  = tk.Frame(nb, bg=C["bg"])
        self.tab_events = tk.Frame(nb, bg=C["bg"])
        self.tab_notiz  = tk.Frame(nb, bg=C["bg"])

        nb.add(self.tab_kasse,  text="  Kasse & Schüler  ")
        nb.add(self.tab_events, text="  Eventplan  ")
        nb.add(self.tab_notiz,  text="  Notizen  ")

        self._build_kasse_tab()
        self._build_events_tab()
        self._build_notizen_tab()

    # ------------------------------------------------------------------ #
    #  Tab: Kasse & Schüler
    # ------------------------------------------------------------------ #

    def _build_kasse_tab(self):
        f = self.tab_kasse

        # --- Kennzahlen-Leiste ---
        top = tk.Frame(f, bg=C["panel"], pady=12)
        top.pack(fill="x", padx=6, pady=(6, 0))

        for col, (lbl, attr, farbe) in enumerate([
            ("Kassenstand",    "lbl_gesamt", C["text"]),
            ("Offen",          "lbl_offen",  C["red"]),
            ("Schüler bezahlt","lbl_count",  C["green"]),
        ]):
            tk.Label(top, text=lbl, font=FB, bg=C["panel"], fg=C["sub"]).grid(
                row=0, column=col, padx=24)
            lbl_w = tk.Label(top, text="–", font=FL, bg=C["panel"], fg=farbe)
            lbl_w.grid(row=1, column=col, padx=24)
            setattr(self, attr, lbl_w)

        tk.Label(top, text="Standard €/Schüler", font=FS,
                 bg=C["panel"], fg=C["sub"]).grid(row=0, column=3, padx=20)
        self.var_std_betrag = tk.StringVar(value="10.00")
        _entry(top, self.var_std_betrag, width=8).grid(row=1, column=3, padx=20)
        _btn(top, "Speichern", self._save_std_betrag, font=FS,
             padx=6, pady=2).grid(row=1, column=4, padx=4)

        # --- Neuen Schüler hinzufügen ---
        mid = tk.Frame(f, bg=C["bg"])
        mid.pack(fill="x", padx=6, pady=6)

        tk.Label(mid, text="Name:", bg=C["bg"], fg=C["sub"], font=FB).pack(side="left")
        self.var_neuer_name = tk.StringVar()
        e_name = _entry(mid, self.var_neuer_name, width=20)
        e_name.pack(side="left", padx=6)
        # Enter-Taste im Namen-Feld → Schüler hinzufügen
        e_name.bind("<Return>", lambda _: self._add_schueler())

        tk.Label(mid, text="Betrag €:", bg=C["bg"], fg=C["sub"], font=FB).pack(side="left")
        self.var_neuer_betrag = tk.StringVar(value="10.00")
        _entry(mid, self.var_neuer_betrag, width=8).pack(side="left", padx=6)

        _btn(mid, "+ Schüler", self._add_schueler).pack(side="left", padx=6)
        _btn(mid, "Ausgewählte löschen", self._del_schueler,
             color="#5c2e2e").pack(side="left", padx=6)

        # --- CSV + Reset ---
        csv_row = tk.Frame(f, bg=C["bg"])
        csv_row.pack(fill="x", padx=6, pady=(0, 4))

        for txt, cmd in [("CSV Import", self._csv_import),
                         ("CSV Export", self._csv_export)]:
            tk.Button(csv_row, text=txt, command=cmd,
                      bg=C["panel"], fg=C["sub"], font=FS,
                      relief="flat", cursor="hand2",
                      padx=8, pady=3).pack(side="left", padx=2)

        tk.Button(csv_row, text="Alle zurücksetzen", command=self._reset_alle,
                  bg=C["panel"], fg=C["sub"], font=FS,
                  relief="flat", cursor="hand2",
                  padx=8, pady=3).pack(side="right", padx=2)

        # --- Schülerliste ---
        list_frame = tk.Frame(f, bg=C["bg"])
        list_frame.pack(fill="both", expand=True, padx=6, pady=4)

        sb = tk.Scrollbar(list_frame, bg=C["panel"])
        sb.pack(side="right", fill="y")

        self.canvas = tk.Canvas(list_frame, bg=C["bg"],
                                yscrollcommand=sb.set, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        sb.config(command=self.canvas.yview)

        self.schueler_frame = tk.Frame(self.canvas, bg=C["bg"])
        self._cw = self.canvas.create_window(
            (0, 0), window=self.schueler_frame, anchor="nw")

        self.schueler_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self._cw, width=e.width))

        # Mausrad-Scrolling
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _bind_mousewheel(self, _event=None):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------ #
    #  Tab: Eventplan
    # ------------------------------------------------------------------ #

    def _build_events_tab(self):
        f = self.tab_events

        inp = tk.Frame(f, bg=C["panel"], pady=10)
        inp.pack(fill="x", padx=6, pady=6)

        self.var_ev_titel  = tk.StringVar()
        self.var_ev_datum  = tk.StringVar(
            value=datetime.today().strftime("%d.%m.%Y"))
        self.var_ev_kosten = tk.StringVar(value="0.00")
        self.var_ev_desc   = tk.StringVar()

        fields = [
            ("Titel",               self.var_ev_titel,  20),
            ("Datum (TT.MM.JJJJ)", self.var_ev_datum,  14),
            ("Kosten €",           self.var_ev_kosten,  8),
            ("Beschreibung",       self.var_ev_desc,   24),
        ]
        for col, (lbl, var, w) in enumerate(fields):
            tk.Label(inp, text=lbl, bg=C["panel"], fg=C["sub"],
                     font=FS).grid(row=0, column=col, padx=8, sticky="w")
            _entry(inp, var, width=w).grid(row=1, column=col, padx=8, sticky="w")

        _btn(inp, "+ Event", self._add_event).grid(row=1, column=len(fields), padx=10)

        # Tabelle
        style = ttk.Style()
        style.configure("Ev.Treeview",
                        background=C["panel"], foreground=C["text"],
                        fieldbackground=C["panel"], font=FB, rowheight=28)
        style.configure("Ev.Treeview.Heading",
                        background=C["accent"], foreground="white", font=FB)
        style.map("Ev.Treeview", background=[("selected", C["accent2"])])

        cols = ("Titel", "Datum", "Kosten", "Beschreibung")
        self.tree_events = ttk.Treeview(f, columns=cols, show="headings",
                                        style="Ev.Treeview", height=14)
        self.tree_events.heading("Titel",        text="Titel")
        self.tree_events.heading("Datum",        text="Datum")
        self.tree_events.heading("Kosten",       text="Kosten")
        self.tree_events.heading("Beschreibung", text="Beschreibung")
        self.tree_events.column("Titel",        width=200)
        self.tree_events.column("Datum",        width=110)
        self.tree_events.column("Kosten",       width=90)
        self.tree_events.column("Beschreibung", width=350)
        self.tree_events.pack(fill="both", expand=True, padx=6, pady=4)

        btn_row = tk.Frame(f, bg=C["bg"])
        btn_row.pack(fill="x", padx=6, pady=4)

        _btn(btn_row, "Ausgewähltes Event löschen", self._del_event,
             color="#5c2e2e", font=FS, padx=8, pady=3).pack(side="left")

        # Restbetrag (rechts, prominent)
        self.lbl_event_diff = tk.Label(
            btn_row, text="Restbetrag: –",
            bg=C["bg"], fg=C["green"], font=FH)
        self.lbl_event_diff.pack(side="right", padx=16)

        self.lbl_event_summe = tk.Label(
            btn_row, text="Geplante Kosten: –",
            bg=C["bg"], fg=C["sub"], font=FB)
        self.lbl_event_summe.pack(side="right", padx=10)

    # ------------------------------------------------------------------ #
    #  Tab: Notizen
    # ------------------------------------------------------------------ #

    def _build_notizen_tab(self):
        f = self.tab_notiz
        tk.Label(f, text="Notizen", font=FH,
                 bg=C["bg"], fg=C["sub"]).pack(anchor="w", padx=10, pady=(10, 4))

        self.txt_notiz = tk.Text(
            f,
            bg=C["panel"], fg=C["text"],
            font=("Segoe UI", 11),
            insertbackground=C["text"],
            relief="flat",
            padx=10, pady=10,
            wrap="word",
            undo=True,
            highlightthickness=1,
            highlightbackground=C["border"],
        )
        self.txt_notiz.pack(fill="both", expand=True, padx=10, pady=4)

        # Strg+S zum Speichern
        self.txt_notiz.bind("<Control-s>", lambda _: self._save_notiz())

        _btn(f, "Notizen speichern", self._save_notiz,
             padx=12, pady=6).pack(pady=6)

    # ------------------------------------------------------------------ #
    #  Schüler – Render
    # ------------------------------------------------------------------ #

    def _refresh_schueler(self):
        for w in self.schueler_frame.winfo_children():
            w.destroy()
        self._check_vars.clear()

        con = db_connect()
        rows = con.execute(
            "SELECT id, name, bezahlt, betrag FROM schueler ORDER BY name"
        ).fetchall()
        con.close()

        # ---- Header-Zeile mit "Alle auswählen"-Checkbox ----
        header_bg = C["accent"]

        # Alle-auswählen Checkbox
        self._select_all_var.set(False)
        tk.Checkbutton(
            self.schueler_frame,
            variable=self._select_all_var,
            command=self._toggle_select_all,
            bg=header_bg, activebackground=header_bg,
            selectcolor=C["cb_check"],
        ).grid(row=0, column=0, padx=4, pady=2)

        for col, (txt, w) in enumerate([
            ("Name",          22),
            ("Betrag €",      9),
            ("Bezahlt",       10),
            ("Betrag ändern", 14),
            ("",              4),
        ], start=1):
            tk.Label(
                self.schueler_frame,
                text=txt, width=w,
                bg=header_bg, fg="white",
                font=FS, anchor="w",
            ).grid(row=0, column=col, padx=2, pady=2, sticky="w")

        # ---- Schüler-Zeilen ----
        for i, (sid, name, bezahlt, betrag) in enumerate(rows):
            bg = C["row_even"] if i % 2 == 0 else C["row_odd"]

            # Auswahl-Checkbox (für Löschen)
            sel_var = tk.BooleanVar(value=False)
            self._check_vars[sid] = sel_var
            tk.Checkbutton(
                self.schueler_frame,
                variable=sel_var,
                command=self._update_select_all_state,
                bg=bg, activebackground=bg,
                selectcolor=C["cb_check"],
            ).grid(row=i + 1, column=0, padx=4)

            tk.Label(
                self.schueler_frame,
                text=name, font=FB,
                bg=bg, fg=C["text"],
                anchor="w", width=22,
            ).grid(row=i + 1, column=1, padx=6, pady=3, sticky="w")

            tk.Label(
                self.schueler_frame,
                text=f"{betrag:.2f} €", font=FB,
                bg=bg, fg=C["sub"],
                width=9, anchor="w",
            ).grid(row=i + 1, column=2, padx=4, sticky="w")

            # Bezahlt-Checkbox
            bez_var = tk.BooleanVar(value=bool(bezahlt))

            def _make_toggle(sid_=sid, var_=bez_var):
                return lambda: self._toggle_bezahlt(sid_, var_.get())

            tk.Checkbutton(
                self.schueler_frame,
                variable=bez_var,
                command=_make_toggle(),
                bg=bg, activebackground=bg,
                selectcolor=C["cb_check"],
                text="bezahlt",
                fg=C["green"] if bezahlt else C["red"],
                font=FB,
            ).grid(row=i + 1, column=3, padx=6, sticky="w")

            # Betrag ändern
            b_var = tk.StringVar(value=f"{betrag:.2f}")

            def _make_update(sid_=sid, var_=b_var):
                return lambda: self._update_betrag(sid_, var_.get())

            b_entry = _entry(self.schueler_frame, b_var, width=7, font=FS)
            b_entry.grid(row=i + 1, column=4, padx=4, pady=2)
            b_entry.bind("<Return>", lambda _, f=_make_update(): f())

            _btn(self.schueler_frame, "OK", _make_update(),
                 font=FS, padx=4, pady=1).grid(row=i + 1, column=5, padx=2)

        self._refresh_summen()

    def _toggle_select_all(self):
        val = self._select_all_var.get()
        for var in self._check_vars.values():
            var.set(val)

    def _update_select_all_state(self):
        """Setzt die Alle-Checkbox auf indeterminate / checked / unchecked."""
        vals = [v.get() for v in self._check_vars.values()]
        if not vals:
            self._select_all_var.set(False)
        elif all(vals):
            self._select_all_var.set(True)
        else:
            self._select_all_var.set(False)

    # ------------------------------------------------------------------ #
    #  Schüler – Logik
    # ------------------------------------------------------------------ #

    def _refresh_summen(self):
        con = db_connect()
        rows = con.execute("SELECT bezahlt, betrag FROM schueler").fetchall()
        event_kosten = con.execute(
            "SELECT COALESCE(SUM(kosten), 0) FROM events"
        ).fetchone()[0]
        con.close()

        kasse   = sum(b for bez, b in rows if bez)
        offen   = sum(b for bez, b in rows if not bez)
        bez_n   = sum(1 for bez, _ in rows if bez)
        total_n = len(rows)
        diff    = kasse - event_kosten

        self.lbl_gesamt.config(text=f"{kasse:.2f} €")
        self.lbl_offen.config(text=f"{offen:.2f} €")
        self.lbl_count.config(text=f"{bez_n} / {total_n}")

        if hasattr(self, "lbl_event_summe"):
            self.lbl_event_summe.config(
                text=f"Geplante Kosten: {event_kosten:.2f} €")
        if hasattr(self, "lbl_event_diff"):
            farbe = C["green"] if diff >= 0 else C["red"]
            self.lbl_event_diff.config(
                text=f"Restbetrag: {diff:+.2f} €",
                fg=farbe,
            )

    def _toggle_bezahlt(self, sid: int, value: bool):
        try:
            con = db_connect()
            con.execute(
                "UPDATE schueler SET bezahlt=? WHERE id=?", (int(value), sid))
            con.commit()
            con.close()
        except Exception:
            logging.exception("_toggle_bezahlt fehlgeschlagen")
            messagebox.showerror("Fehler", "Zahlungsstatus konnte nicht gespeichert werden.")
        self._refresh_summen()

    def _update_betrag(self, sid: int, value: str):
        try:
            betrag = float(value.replace(",", "."))
            if betrag < 0:
                raise ValueError("Negativ")
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiger Betrag (muss eine positive Zahl sein).")
            return
        try:
            con = db_connect()
            con.execute("UPDATE schueler SET betrag=? WHERE id=?", (betrag, sid))
            con.commit()
            con.close()
        except Exception:
            logging.exception("_update_betrag fehlgeschlagen")
            messagebox.showerror("Fehler", "Betrag konnte nicht gespeichert werden.")
            return
        self._refresh_schueler()

    def _add_schueler(self):
        name = self.var_neuer_name.get().strip()
        if not name:
            messagebox.showwarning("Hinweis", "Name darf nicht leer sein.")
            return
        try:
            betrag = float(self.var_neuer_betrag.get().replace(",", "."))
            if betrag < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiger Betrag.")
            return
        try:
            con = db_connect()
            con.execute(
                "INSERT INTO schueler (name, betrag) VALUES (?, ?)", (name, betrag))
            con.commit()
            con.close()
        except Exception:
            logging.exception("_add_schueler fehlgeschlagen")
            messagebox.showerror("Fehler", "Schüler konnte nicht hinzugefügt werden.")
            return
        self.var_neuer_name.set("")
        self._refresh_schueler()

    def _del_schueler(self):
        ids = [sid for sid, var in self._check_vars.items() if var.get()]
        if not ids:
            messagebox.showinfo("Hinweis", "Keine Schüler ausgewählt.")
            return
        if not messagebox.askyesno("Löschen", f"{len(ids)} Schüler wirklich löschen?"):
            return
        try:
            con = db_connect()
            con.executemany(
                "DELETE FROM schueler WHERE id=?", [(i,) for i in ids])
            con.commit()
            con.close()
        except Exception:
            logging.exception("_del_schueler fehlgeschlagen")
            messagebox.showerror("Fehler", "Löschen fehlgeschlagen.")
            return
        self._refresh_schueler()

    def _reset_alle(self):
        if not messagebox.askyesno(
            "Zurücksetzen",
            "Alle Zahlungsstatus auf 'nicht bezahlt' setzen?\n"
            "Die Beträge bleiben erhalten.",
        ):
            return
        try:
            con = db_connect()
            con.execute("UPDATE schueler SET bezahlt=0")
            con.commit()
            con.close()
        except Exception:
            logging.exception("_reset_alle fehlgeschlagen")
            messagebox.showerror("Fehler", "Zurücksetzen fehlgeschlagen.")
            return
        self._refresh_schueler()

    def _save_std_betrag(self):
        try:
            val = float(self.var_std_betrag.get().replace(",", "."))
            if val < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Fehler", "Ungültiger Betrag.")
            return
        try:
            con = db_connect()
            con.execute(
                "INSERT OR REPLACE INTO settings VALUES ('standard_betrag', ?)",
                (str(val),),
            )
            con.commit()
            con.close()
        except Exception:
            logging.exception("_save_std_betrag fehlgeschlagen")
            messagebox.showerror("Fehler", "Einstellung konnte nicht gespeichert werden.")
            return
        self.var_neuer_betrag.set(f"{val:.2f}")

    # ------------------------------------------------------------------ #
    #  CSV
    # ------------------------------------------------------------------ #

    def _csv_import(self):
        path = filedialog.askopenfilename(
            title="CSV importieren",
            filetypes=[("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")],
        )
        if not path:
            return
        count = 0
        errors = []
        try:
            con = db_connect()
            with open(path, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                for lineno, row in enumerate(reader, start=2):
                    name = (
                        row.get("name") or row.get("Name") or ""
                    ).strip()
                    if not name:
                        continue
                    raw_betrag = (
                        row.get("betrag") or row.get("Betrag") or "10"
                    ).strip()
                    try:
                        betrag = float(raw_betrag.replace(",", "."))
                        if betrag < 0:
                            raise ValueError
                    except ValueError:
                        errors.append(f"Zeile {lineno}: ungültiger Betrag '{raw_betrag}'")
                        betrag = 10.0
                    con.execute(
                        "INSERT INTO schueler (name, betrag) VALUES (?, ?)",
                        (name, betrag),
                    )
                    count += 1
            con.commit()
            con.close()
        except Exception:
            logging.exception("CSV-Import fehlgeschlagen")
            messagebox.showerror("Fehler", f"Import fehlgeschlagen:\n{traceback.format_exc()[-300:]}")
            return

        msg = f"{count} Schüler importiert."
        if errors:
            msg += f"\n\nWarnungen:\n" + "\n".join(errors[:10])
        messagebox.showinfo("Import abgeschlossen", msg)
        self._refresh_schueler()

    def _csv_export(self):
        path = filedialog.asksaveasfilename(
            title="CSV exportieren",
            defaultextension=".csv",
            filetypes=[("CSV-Dateien", "*.csv")],
        )
        if not path:
            return
        try:
            con = db_connect()
            rows = con.execute(
                "SELECT name, bezahlt, betrag FROM schueler ORDER BY name"
            ).fetchall()
            con.close()
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(["name", "bezahlt", "betrag"])
                writer.writerows(rows)
        except Exception:
            logging.exception("CSV-Export fehlgeschlagen")
            messagebox.showerror("Fehler", "Export fehlgeschlagen.")
            return
        messagebox.showinfo("Export abgeschlossen", f"{len(rows)} Schüler exportiert.")

    # ------------------------------------------------------------------ #
    #  Events
    # ------------------------------------------------------------------ #

    def _refresh_events(self):
        self.tree_events.delete(*self.tree_events.get_children())
        try:
            con = db_connect()
            rows = con.execute(
                "SELECT id, titel, datum, kosten, beschreibung "
                "FROM events ORDER BY datum"
            ).fetchall()
            con.close()
        except Exception:
            logging.exception("_refresh_events fehlgeschlagen")
            return

        for sid, titel, datum, kosten, desc in rows:
            self.tree_events.insert(
                "", "end", iid=str(sid),
                values=(titel, datum, f"{kosten:.2f} €", desc),
            )
        self._refresh_summen()

    def _add_event(self):
        titel = self.var_ev_titel.get().strip()
        datum = self.var_ev_datum.get().strip()
        desc  = self.var_ev_desc.get().strip()
        if not titel:
            messagebox.showwarning("Hinweis", "Titel ist ein Pflichtfeld.")
            return
        if not datum:
            messagebox.showwarning("Hinweis", "Datum ist ein Pflichtfeld.")
            return
        try:
            kosten = float(self.var_ev_kosten.get().replace(",", "."))
            if kosten < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Fehler", "Ungültige Kosten (muss eine positive Zahl sein).")
            return
        try:
            con = db_connect()
            con.execute(
                "INSERT INTO events (titel, datum, kosten, beschreibung) "
                "VALUES (?,?,?,?)",
                (titel, datum, kosten, desc),
            )
            con.commit()
            con.close()
        except Exception:
            logging.exception("_add_event fehlgeschlagen")
            messagebox.showerror("Fehler", "Event konnte nicht gespeichert werden.")
            return
        self.var_ev_titel.set("")
        self.var_ev_kosten.set("0.00")
        self.var_ev_desc.set("")
        self._refresh_events()

    def _del_event(self):
        sel = self.tree_events.selection()
        if not sel:
            messagebox.showinfo("Hinweis", "Kein Event ausgewählt.")
            return
        if not messagebox.askyesno("Löschen", f"{len(sel)} Event(s) wirklich löschen?"):
            return
        try:
            con = db_connect()
            for iid in sel:
                con.execute("DELETE FROM events WHERE id=?", (int(iid),))
            con.commit()
            con.close()
        except Exception:
            logging.exception("_del_event fehlgeschlagen")
            messagebox.showerror("Fehler", "Löschen fehlgeschlagen.")
            return
        self._refresh_events()

    # ------------------------------------------------------------------ #
    #  Notizen
    # ------------------------------------------------------------------ #

    def _refresh_notiz(self):
        try:
            con = db_connect()
            text = con.execute(
                "SELECT text FROM notizen WHERE id=1"
            ).fetchone()[0]
            con.close()
        except Exception:
            logging.exception("_refresh_notiz fehlgeschlagen")
            return
        self.txt_notiz.delete("1.0", "end")
        self.txt_notiz.insert("1.0", text)

    def _save_notiz(self):
        text = self.txt_notiz.get("1.0", "end-1c")
        try:
            con = db_connect()
            con.execute("UPDATE notizen SET text=? WHERE id=1", (text,))
            con.commit()
            con.close()
        except Exception:
            logging.exception("_save_notiz fehlgeschlagen")
            messagebox.showerror("Fehler", "Notizen konnten nicht gespeichert werden.")
            return
        messagebox.showinfo("Gespeichert", "Notizen wurden gespeichert.")

    # ------------------------------------------------------------------ #
    #  Settings
    # ------------------------------------------------------------------ #

    def _load_settings(self):
        try:
            con = db_connect()
            val = con.execute(
                "SELECT value FROM settings WHERE key='standard_betrag'"
            ).fetchone()
            con.close()
        except Exception:
            logging.exception("_load_settings fehlgeschlagen")
            return
        if val:
            self.var_std_betrag.set(val[0])
            self.var_neuer_betrag.set(val[0])

    # ------------------------------------------------------------------ #
    #  Alles laden
    # ------------------------------------------------------------------ #

    def _refresh_all(self):
        self._load_settings()
        self._refresh_schueler()
        self._refresh_events()
        self._refresh_notiz()

    # ------------------------------------------------------------------ #
    #  Tray
    # ------------------------------------------------------------------ #

    def _hide_to_tray(self):
        self.withdraw()


# --------------------------------------------------------------------------- #
#  Entry Point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    app = KlassenkasseApp()
    app.mainloop()
