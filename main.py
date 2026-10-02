"""Projeto Fusion Jiu Jitsu — administração local em Python/Tkinter."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
import sqlite3
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageOps, ImageTk
except ModuleNotFoundError:
    Image = ImageOps = ImageTk = None


APP_TITLE = "Projeto Fusion Jiu Jitsu"
INSTRUCTOR_NAME = "Professor Maikon Douglas"
INSTRUCTOR_RANK = "Faixa Preta 1º Grau"
DB_PATH = Path(__file__).with_name("fusion_jiu_jitsu.db")
PROFILE_DIR = Path(__file__).with_name("profile_photos")
INFO_BANNER_DIR = Path(__file__).with_name("info_banners")
MASTER_PASSWORD = "Fusion@2026"
BG = "#10151D"
PANEL = "#171F2A"
PANEL_ALT = "#1D2835"
ACCENT = "#E0B64F"
RED = "#922B32"
TEXT = "#F3F4F6"
MUTED = "#9AA7B5"
GREEN = "#42B883"
THEME_COLORS = {
    "escuro": {
        "BG": "#10151D", "PANEL": "#171F2A", "PANEL_ALT": "#1D2835", "ACCENT": "#E0B64F",
        "RED": "#922B32", "TEXT": "#F3F4F6", "MUTED": "#9AA7B5", "GREEN": "#42B883",
        "SIDE": "#121922", "SIDE_ACTIVE": "#3A252B", "SIDE_TEXT": "#C2CBD5", "ENTRY_BG": "#202B38",
        "BORDER": "#344255", "SELECTED": "#34465A", "SUBTLE": "#7F8C9B", "DIVIDER": "#293444",
        "SIDE_MUTED": "#657385", "SIDE_EMPTY": "#8290A0", "CANVAS": "#080B10",
        "ACCENT_TEXT": "#151515", "ACCENT_ACTIVE": "#E7B95E", "DANGER_BG": "#542C31", "DANGER_TEXT": "#FFB4B4",
    },
    "claro": {
        "BG": "#F2F4F7", "PANEL": "#FFFFFF", "PANEL_ALT": "#E7EBF0", "ACCENT": "#9A6B00",
        "RED": "#922B32", "TEXT": "#202631", "MUTED": "#5B6572", "GREEN": "#168653",
        "SIDE": "#E5E9EF", "SIDE_ACTIVE": "#F8E9C2", "SIDE_TEXT": "#354052", "ENTRY_BG": "#F7F8FA",
        "BORDER": "#C9D0D9", "SELECTED": "#D4E1F2", "SUBTLE": "#657385", "DIVIDER": "#C8D0DA",
        "SIDE_MUTED": "#657385", "SIDE_EMPTY": "#657385", "CANVAS": "#E7EBF0",
        "ACCENT_TEXT": "#FFFFFF", "ACCENT_ACTIVE": "#805800", "DANGER_BG": "#F5DEDF", "DANGER_TEXT": "#8B242B",
    },
}
BELTS = [
    "Branca",
    "Cinza e branca (listra branca)", "Cinza (sólida)", "Cinza e preta (listra preta)",
    "Amarela e branca (listra branca)", "Amarela (sólida)", "Amarela e preta (listra preta)",
    "Laranja e branca (listra branca)", "Laranja (sólida)", "Laranja e preta (listra preta)",
    "Verde e branca (listra branca)", "Verde (sólida)", "Verde e preta (listra preta)",
    "Azul", "Roxa", "Marrom", "Preta", "Vermelha e preta", "Vermelha e branca", "Vermelha",
]
MONTHS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
          "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, expected = stored.split(":", 1)
        actual = hash_password(password, bytes.fromhex(salt_hex)).split(":", 1)[1]
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class Database:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.setup()

    def setup(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('Professor', 'Instrutor')),
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                belt TEXT NOT NULL DEFAULT 'Branca',
                phone TEXT DEFAULT '',
                birth_date TEXT,
                photo_path TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                attended_on TEXT NOT NULL,
                class_number INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS class_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_date TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS student_access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
                student_name TEXT NOT NULL,
                student_code TEXT NOT NULL,
                accessed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS information_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                image_path TEXT,
                created_at TEXT NOT NULL
            );
        """)
        student_columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(students)")}
        if "birth_date" not in student_columns:
            self.conn.execute("ALTER TABLE students ADD COLUMN birth_date TEXT")
        if "photo_path" not in student_columns:
            self.conn.execute("ALTER TABLE students ADD COLUMN photo_path TEXT")
        # Upgrade databases created by earlier versions, where each student could
        # only have one attendance record per day. Preserve all historical rows.
        table_sql = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='attendance'"
        ).fetchone()[0]
        compact_sql = "".join(table_sql.split()).lower()
        if "unique(student_id,attended_on)" in compact_sql:
            self.conn.execute("ALTER TABLE attendance RENAME TO attendance_legacy")
            self.conn.execute("""CREATE TABLE attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                attended_on TEXT NOT NULL,
                class_number INTEGER NOT NULL DEFAULT 1
            )""")
            self.conn.execute("""INSERT INTO attendance(id,student_id,attended_on,class_number)
                SELECT id,student_id,attended_on,1 FROM attendance_legacy""")
            self.conn.execute("DROP TABLE attendance_legacy")
        migrated = self.conn.execute(
            "SELECT 1 FROM app_meta WHERE key='class_days_migrated'"
        ).fetchone()
        if not migrated:
            self.conn.execute(
                "INSERT OR IGNORE INTO class_days(class_date) SELECT DISTINCT attended_on FROM attendance"
            )
            self.conn.execute(
                "INSERT INTO app_meta(key,value) VALUES('class_days_migrated','1')"
            )
        initial = [
            ("professor", "Professor Fusion", "Professor", "Fusion@2026"),
            ("instrutor", "Instrutor Fusion", "Instrutor", "Fusion@2026"),
        ]
        for username, name, role, password in initial:
            self.conn.execute(
                "INSERT OR IGNORE INTO staff(username,full_name,role,password_hash) VALUES(?,?,?,?)",
                (username, name, role, hash_password(password)),
            )
        self.conn.commit()

    def authenticate(self, username: str, password: str):
        row = self.conn.execute("SELECT * FROM staff WHERE username=?", (username.strip(),)).fetchone()
        return row if row and (password == MASTER_PASSWORD or verify_password(password, row["password_hash"])) else None

    def remembered_staff(self):
        saved = self.conn.execute("SELECT value FROM app_meta WHERE key='remembered_staff_id'").fetchone()
        if not saved:
            return None
        try:
            staff_id = int(saved["value"])
        except (TypeError, ValueError):
            staff_id = 0
        person = self.conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
        if person is None:
            self.clear_remembered_staff()
        return person

    def set_remembered_staff(self, staff_id: int | None) -> None:
        if staff_id is None:
            self.clear_remembered_staff()
            return
        self.conn.execute(
            "INSERT INTO app_meta(key,value) VALUES('remembered_staff_id',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(staff_id),),
        )
        self.conn.commit()

    def clear_remembered_staff(self) -> None:
        self.conn.execute("DELETE FROM app_meta WHERE key='remembered_staff_id'")
        self.conn.commit()

    def change_staff_password(self, staff_id: int, password: str) -> None:
        self.conn.execute("UPDATE staff SET password_hash=? WHERE id=?", (hash_password(password), staff_id))
        self.conn.commit()

    def add_information(self, title: str, body: str, image_path: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO information_posts(title,body,image_path,created_at) VALUES(?,?,?,?)",
            (title.strip(), body.strip(), image_path, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def update_information(self, post_id: int, title: str, body: str, image_path: str | None) -> None:
        self.conn.execute(
            "UPDATE information_posts SET title=?,body=?,image_path=? WHERE id=?",
            (title.strip(), body.strip(), image_path, post_id),
        )
        self.conn.commit()

    def information_posts(self):
        return self.conn.execute("SELECT * FROM information_posts ORDER BY created_at DESC,id DESC").fetchall()

    def get_theme(self) -> str:
        row = self.conn.execute("SELECT value FROM app_meta WHERE key='theme'").fetchone()
        return row["value"] if row and row["value"] in THEME_COLORS else "escuro"

    def set_theme(self, theme: str) -> None:
        if theme not in THEME_COLORS:
            theme = "escuro"
        self.conn.execute(
            "INSERT INTO app_meta(key,value) VALUES('theme',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (theme,),
        )
        self.conn.commit()

    def delete_information(self, post_id: int) -> None:
        self.conn.execute("DELETE FROM information_posts WHERE id=?", (post_id,))
        self.conn.commit()

    def students(self):
        return self.conn.execute("SELECT * FROM students ORDER BY name COLLATE NOCASE").fetchall()

    def birthdays(self, month: int):
        return self.conn.execute(
            "SELECT * FROM students WHERE birth_date IS NOT NULL "
            "AND CAST(substr(birth_date,6,2) AS INTEGER)=? "
            "ORDER BY CAST(substr(birth_date,9,2) AS INTEGER), name COLLATE NOCASE",
            (month,),
        ).fetchall()

    def student_by_id(self, student_id: int):
        return self.conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()

    def student_by_code(self, code: str):
        return self.conn.execute("SELECT * FROM students WHERE code=?", (code.strip().upper(),)).fetchone()

    def update_student(self, student_id: int, code: str, name: str, belt: str, phone: str, birth_date: str) -> None:
        self.conn.execute(
            "UPDATE students SET code=?,name=?,belt=?,phone=?,birth_date=? WHERE id=?",
            (code.strip().upper(), name.strip(), belt, phone.strip(), birth_date, student_id),
        )
        self.conn.commit()

    def update_student_photo(self, student_id: int, photo_path: str) -> None:
        self.conn.execute("UPDATE students SET photo_path=? WHERE id=?", (photo_path, student_id))
        self.conn.commit()

    def attendance_total(self, student_id: int) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM attendance WHERE student_id=?", (student_id,)).fetchone()[0]

    def log_student_access(self, student) -> None:
        self.conn.execute(
            "INSERT INTO student_access_log(student_id,student_name,student_code,accessed_at) VALUES(?,?,?,?)",
            (student["id"], student["name"], student["code"], datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    def recent_student_accesses(self, limit=5):
        return self.conn.execute(
            "SELECT * FROM student_access_log ORDER BY accessed_at DESC,id DESC LIMIT ?", (limit,)
        ).fetchall()

    def all_student_accesses(self):
        return self.conn.execute(
            "SELECT * FROM student_access_log ORDER BY accessed_at DESC,id DESC"
        ).fetchall()

    def add_student(self, name: str, belt: str, phone: str, birth_date: str) -> str:
        code = "FUS-" + secrets.token_hex(3).upper()
        while self.conn.execute("SELECT 1 FROM students WHERE code=?", (code,)).fetchone():
            code = "FUS-" + secrets.token_hex(3).upper()
        self.conn.execute(
            "INSERT INTO students(code,name,belt,phone,birth_date,created_at) VALUES(?,?,?,?,?,?)",
            (code, name.strip(), belt, phone.strip(), birth_date, datetime.now().isoformat(timespec="seconds")),
        )
        self.conn.commit()
        return code

    def delete_student(self, student_id: int) -> None:
        self.conn.execute("DELETE FROM students WHERE id=?", (student_id,))
        self.conn.commit()

    def mark_attendance(self, student_id: int, present: bool) -> None:
        today = date.today().isoformat()
        if present:
            next_class = self.conn.execute(
                "SELECT COALESCE(MAX(class_number),0)+1 FROM attendance WHERE student_id=? AND attended_on=?",
                (student_id, today),
            ).fetchone()[0]
            self.conn.execute("INSERT INTO attendance(student_id,attended_on,class_number) VALUES(?,?,?)", (student_id, today, next_class))
        else:
            last_id = self.conn.execute(
                "SELECT id FROM attendance WHERE student_id=? AND attended_on=? ORDER BY class_number DESC LIMIT 1",
                (student_id, today),
            ).fetchone()
            if last_id:
                self.conn.execute("DELETE FROM attendance WHERE id=?", (last_id[0],))
        self.conn.commit()

    def attended_today(self, student_id: int) -> bool:
        return bool(self.conn.execute("SELECT 1 FROM attendance WHERE student_id=? AND attended_on=?", (student_id, date.today().isoformat())).fetchone())

    def attendance_count_today(self, student_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE student_id=? AND attended_on=?",
            (student_id, date.today().isoformat()),
        ).fetchone()[0]

    def total_attendance_today(self) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE attended_on=?", (date.today().isoformat(),)
        ).fetchone()[0]

    def class_day_count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM class_days").fetchone()[0]

    def add_class_day(self) -> bool:
        cursor = self.conn.execute(
            "INSERT OR IGNORE INTO class_days(class_date) VALUES(?)", (date.today().isoformat(),)
        )
        self.conn.commit()
        return cursor.rowcount == 1

    def remove_last_class_day(self) -> bool:
        row = self.conn.execute("SELECT id FROM class_days ORDER BY class_date DESC LIMIT 1").fetchone()
        if not row:
            return False
        self.conn.execute("DELETE FROM class_days WHERE id=?", (row["id"],))
        self.conn.commit()
        return True

    def ranking(self):
        return self.conn.execute("""
            SELECT s.id,s.code,s.name,s.belt,COUNT(a.id) AS total
            FROM students s LEFT JOIN attendance a ON a.student_id=s.id
            GROUP BY s.id ORDER BY total DESC, s.name COLLATE NOCASE ASC
        """).fetchall()

    def close(self) -> None:
        self.conn.close()


class PhotoAdjustDialog(tk.Toplevel):
    """Square crop editor with drag, zoom and quarter-turn rotation."""

    SIDE = 420

    def __init__(self, parent, student, source_image, on_save):
        super().__init__(parent)
        self.parent_app = parent
        self.student = student
        self.source_image = source_image
        self.on_save = on_save
        self.angle = 0
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.drag_origin = None
        self.preview_image = None
        self.title("Ajustar foto de perfil")
        self.configure(bg=BG)
        self.transient(parent)
        self.resizable(False, False)
        shell = tk.Frame(self, bg=PANEL, padx=20, pady=18)
        shell.pack(fill="both", expand=True)
        tk.Label(shell, text="AJUSTE SUA FOTO", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(shell, text="Arraste para posicionar · use o zoom e gire até preencher o quadrado.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 12))
        self.canvas = tk.Canvas(shell, width=self.SIDE, height=self.SIDE, bg=CANVAS,
                                highlightthickness=0, cursor="fleur")
        self.canvas.pack()
        self.canvas.bind("<ButtonPress-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        controls = tk.Frame(shell, bg=PANEL)
        controls.pack(fill="x", pady=(12, 0))
        tk.Button(controls, text="↶  Girar", command=lambda: self.rotate(-90), bg=PANEL_ALT,
                  fg=TEXT, activebackground=PANEL_ALT, relief="flat", padx=12, pady=7,
                  cursor="hand2").pack(side="left")
        tk.Button(controls, text="Girar  ↻", command=lambda: self.rotate(90), bg=PANEL_ALT,
                  fg=TEXT, activebackground=PANEL_ALT, relief="flat", padx=12, pady=7,
                  cursor="hand2").pack(side="left", padx=7)
        tk.Label(controls, text="Zoom", bg=PANEL, fg=MUTED).pack(side="left", padx=(10, 5))
        self.zoom_scale = tk.Scale(controls, from_=1.0, to=3.0, resolution=0.1, orient="horizontal",
                    showvalue=True, length=145, bg=PANEL, fg=TEXT, troughcolor=PANEL_ALT,
                    highlightthickness=0, command=self.set_zoom)
        self.zoom_scale.set(1.0)
        self.zoom_scale.pack(side="left")
        footer = tk.Frame(shell, bg=PANEL)
        footer.pack(fill="x", pady=(13, 0))
        tk.Button(footer, text="Cancelar", command=self.destroy, bg=PANEL_ALT, fg=TEXT,
                  activebackground=PANEL_ALT, relief="flat", padx=14, pady=8,
                  cursor="hand2").pack(side="right", padx=(8, 0))
        tk.Button(footer, text="Usar esta foto", command=self.confirm, bg=ACCENT, fg=ACCENT_TEXT,
                  activebackground=ACCENT_ACTIVE, relief="flat", padx=14, pady=8,
                  cursor="hand2", font=("Segoe UI", 9, "bold")).pack(side="right")
        self.render()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.grab_set()

    def fitted_dimensions(self):
        image = self.source_image.rotate(self.angle, expand=True)
        scale = max(self.SIDE / image.width, self.SIDE / image.height) * self.zoom
        width = max(self.SIDE, round(image.width * scale))
        height = max(self.SIDE, round(image.height * scale))
        max_x = max(0, (width - self.SIDE) // 2)
        max_y = max(0, (height - self.SIDE) // 2)
        self.offset_x = max(-max_x, min(max_x, self.offset_x))
        self.offset_y = max(-max_y, min(max_y, self.offset_y))
        return image, width, height

    def render(self):
        image, width, height = self.fitted_dimensions()
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        self.preview_image = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(self.SIDE / 2 + self.offset_x, self.SIDE / 2 + self.offset_y,
                                 image=self.preview_image, anchor="center")
        self.canvas.create_rectangle(1, 1, self.SIDE - 1, self.SIDE - 1,
                                     outline=ACCENT, width=2)

    def set_zoom(self, value):
        self.zoom = float(value)
        self.render()

    def rotate(self, amount):
        self.angle = (self.angle + amount) % 360
        self.offset_x = self.offset_y = 0
        self.render()

    def start_drag(self, event):
        self.drag_origin = (event.x, event.y, self.offset_x, self.offset_y)

    def drag(self, event):
        if self.drag_origin is None:
            return
        x, y, start_x, start_y = self.drag_origin
        self.offset_x = start_x + event.x - x
        self.offset_y = start_y + event.y - y
        self.render()

    def confirm(self):
        image, width, height = self.fitted_dimensions()
        side = 512
        scale = max(side / image.width, side / image.height) * self.zoom
        width, height = max(side, round(image.width * scale)), max(side, round(image.height * scale))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        ratio = side / self.SIDE
        left = (side - width) // 2 + round(self.offset_x * ratio)
        top = (side - height) // 2 + round(self.offset_y * ratio)
        square = Image.new("RGB", (side, side), "black")
        square.paste(image, (left, top))
        self.destroy()
        self.on_save(self.student, square)


class FusionApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.db = Database()
        self.user = None
        self.active_student = None
        self.student_preview = False
        self.student_photo_image = None
        self.info_image_selection = None
        self.info_image_refs = []
        self.info_page_canvas = None
        self.info_banner_canvas = None
        self.rank_canvas = None
        self.current_view = "login"
        self.current_admin_page = "home"
        self.current_student_page = "student_home"
        self.month_refresh_id = None
        self.month_refresh_parent = None
        self.title(APP_TITLE)
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.apply_theme(self.db.get_theme())
        self.bind("<MouseWheel>", self.on_ranking_mousewheel, add="+")
        self.bind_all("<MouseWheel>", self.on_information_page_mousewheel, add="+")
        remembered = self.db.remembered_staff()
        if remembered:
            self.user = remembered
            self.show_dashboard()
        else:
            self.show_login()

    def apply_theme(self, theme):
        global BG, PANEL, PANEL_ALT, ACCENT, RED, TEXT, MUTED, GREEN
        global SIDE, SIDE_ACTIVE, SIDE_TEXT, ENTRY_BG, BORDER, SELECTED, SUBTLE, DIVIDER
        global SIDE_MUTED, SIDE_EMPTY, CANVAS, ACCENT_TEXT, ACCENT_ACTIVE, DANGER_BG, DANGER_TEXT
        theme = theme if theme in THEME_COLORS else "escuro"
        globals().update(THEME_COLORS[theme])
        self.current_theme = theme
        self.configure(bg=BG)
        self.style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                             rowheight=37, borderwidth=0, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", background=PANEL_ALT, foreground=MUTED,
                             relief="flat", font=("Segoe UI", 9, "bold"))
        self.style.map("Treeview", background=[("selected", SELECTED)], foreground=[("selected", TEXT)])

    def set_theme(self, theme):
        if theme == self.current_theme:
            return
        self.db.set_theme(theme)
        self.apply_theme(theme)
        if self.current_view == "admin":
            self.show_dashboard(self.current_admin_page)
        elif self.current_view == "student":
            student = self.db.student_by_id(self.active_student["id"]) if self.active_student else None
            self.show_student_portal(student, preview=self.student_preview, page=self.current_student_page)
        elif self.current_view == "student_login":
            self.show_student_login()
        else:
            self.show_login()

    def on_close(self):
        self.db.close()
        self.destroy()

    def clear(self):
        self.rank_canvas = None
        self.info_page_canvas = None
        self.info_banner_canvas = None
        if self.month_refresh_id is not None:
            try:
                owner = self.month_refresh_parent or self
                owner.after_cancel(self.month_refresh_id)
            except tk.TclError:
                pass
            self.month_refresh_id = None
            self.month_refresh_parent = None
        for child in self.winfo_children():
            child.destroy()

    def on_ranking_mousewheel(self, event):
        canvas = self.rank_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is canvas:
                steps = int(-event.delta / 120) or (-1 if event.delta > 0 else 1)
                canvas.yview_scroll(steps, "units")
                return "break"
            widget = getattr(widget, "master", None)

    def on_information_page_mousewheel(self, event):
        canvas = self.info_page_canvas
        if canvas is None or not canvas.winfo_exists():
            return
        steps = int(-event.delta / 120) or (-1 if event.delta > 0 else 1)
        banner_canvas = self.info_banner_canvas
        if event.state & 0x0001 and banner_canvas is not None and banner_canvas.winfo_exists():
            banner_canvas.xview_scroll(steps, "units")
            return "break"
        canvas.yview_scroll(steps, "units")
        return "break"

    def show_login(self):
        self.clear()
        self.current_view = "login"
        self.title(f"{APP_TITLE} | Acesso administrativo")
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)
        card = tk.Frame(shell, bg=PANEL, padx=38, pady=28, highlightbackground=DIVIDER, highlightthickness=1)
        card.place(relx=.5, rely=.5, anchor="center", width=420)
        try:
            logo = tk.PhotoImage(file=str(Path(__file__).with_name("fusion.png")))
            factor = max(1, (max(logo.width(), logo.height()) + 159) // 160)
            self.login_logo = logo.subsample(factor, factor)
            tk.Label(card, image=self.login_logo, bg=PANEL).pack(pady=(0, 8))
        except tk.TclError:
            self.login_logo = None
            tk.Label(card, text="FUSION", bg=PANEL, fg=ACCENT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(card, text="Projeto Fusion Jiu Jitsu", bg=PANEL, fg=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="center")
        tk.Label(card, text=f"{INSTRUCTOR_NAME}\n{INSTRUCTOR_RANK}", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9, "bold"), justify="center").pack(anchor="center", pady=(5, 1))
        tk.Label(card, text="Acesso administrativo", bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="center", pady=(2, 17))
        tk.Label(card, text="USUÁRIO", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        username = self.entry(card)
        username.pack(fill="x", pady=(7, 17), ipady=9)
        tk.Label(card, text="SENHA", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        password = self.entry(card, show="•")
        password.pack(fill="x", pady=(7, 5), ipady=9)
        reveal_password = tk.BooleanVar(value=False)
        tk.Checkbutton(card, text="Mostrar senha", variable=reveal_password,
                       command=lambda: password.config(show="" if reveal_password.get() else "•"),
                       bg=PANEL, fg=MUTED, activebackground=PANEL, activeforeground=TEXT,
                       selectcolor=PANEL_ALT, relief="flat", font=("Segoe UI", 9),
                       cursor="hand2").pack(anchor="w", pady=(0, 13))
        remember_login = tk.BooleanVar(value=self.db.remembered_staff() is not None)
        tk.Checkbutton(card, text="Manter login neste computador", variable=remember_login,
                       bg=PANEL, fg=MUTED, activebackground=PANEL, activeforeground=TEXT,
                       selectcolor=PANEL_ALT, relief="flat", font=("Segoe UI", 9),
                       cursor="hand2").pack(anchor="w", pady=(0, 13))
        def login(event=None):
            person = self.db.authenticate(username.get(), password.get())
            if not person:
                messagebox.showerror("Acesso negado", "Usuário ou senha inválidos.", parent=self)
                password.delete(0, "end")
                password.focus_set()
                return
            self.db.set_remembered_staff(person["id"] if remember_login.get() else None)
            self.user = person
            self.show_dashboard()
        self.button(card, "Entrar", login, accent=True).pack(fill="x", ipady=10)
        password.bind("<Return>", login)
        username.bind("<Return>", lambda _e: password.focus_set())
        self.button(card, "♙  Entrar na área do aluno", self.show_student_login).pack(fill="x", pady=(15, 0), ipady=7)
        username.focus_set()

    def show_student_login(self):
        self.clear()
        self.current_view = "student_login"
        self.title(f"{APP_TITLE} | Área do aluno")
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)
        card = tk.Frame(shell, bg=PANEL, padx=38, pady=30,
                        highlightbackground=DIVIDER, highlightthickness=1)
        card.place(relx=.5, rely=.5, anchor="center", width=420)
        try:
            logo = tk.PhotoImage(file=str(Path(__file__).with_name("fusion.png")))
            factor = max(1, (max(logo.width(), logo.height()) + 159) // 160)
            self.login_logo = logo.subsample(factor, factor)
            tk.Label(card, image=self.login_logo, bg=PANEL).pack(pady=(0, 8))
        except tk.TclError:
            self.login_logo = None
        tk.Label(card, text="Área do aluno", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 21, "bold")).pack()
        tk.Label(card, text=f"{INSTRUCTOR_NAME}\n{INSTRUCTOR_RANK}", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9, "bold"), justify="center").pack(pady=(5, 1))
        tk.Label(card, text="Acesse usando o código único do seu cadastro.", bg=PANEL,
                 fg=MUTED, font=("Segoe UI", 10)).pack(pady=(5, 20))
        tk.Label(card, text="CÓDIGO DO ALUNO", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w")
        code = self.entry(card)
        code.pack(fill="x", pady=(7, 17), ipady=9)
        def enter(event=None):
            student = self.db.student_by_code(code.get())
            if student is None:
                messagebox.showerror("Código não encontrado", "Confira o código fornecido pela academia.", parent=self)
                code.focus_set()
                return
            self.db.log_student_access(student)
            self.show_student_portal(student)
        self.button(card, "Entrar na minha área", enter, accent=True).pack(fill="x", ipady=9)
        self.button(card, "←  Voltar ao login administrativo", self.show_login).pack(fill="x", pady=(10, 0), ipady=7)
        code.bind("<Return>", enter)
        code.focus_set()

    def show_dashboard(self, page="home"):
        self.clear()
        self.current_view = "admin"
        self.current_admin_page = page
        self.title(APP_TITLE)
        layout = tk.Frame(self, bg=BG)
        layout.pack(fill="both", expand=True)
        side = tk.Frame(layout, bg=SIDE, width=235)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        try:
            side_logo = tk.PhotoImage(file=str(Path(__file__).with_name("fusion.png")))
            factor = max(1, (max(side_logo.width(), side_logo.height()) + 69) // 70)
            self.side_logo = side_logo.subsample(factor, factor)
            tk.Label(side, image=self.side_logo, bg=SIDE).pack(anchor="w", padx=20, pady=(18, 12))
        except tk.TclError:
            self.side_logo = None
            tk.Label(side, text="FUSION", bg=SIDE, fg=ACCENT, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=24, pady=(27, 0))
        tk.Label(side, text="PROJETO FUSION", bg=SIDE, fg=TEXT, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=20, pady=(0, 24))
        tk.Label(side, text=f"{INSTRUCTOR_NAME}\n{INSTRUCTOR_RANK}", bg=SIDE, fg=ACCENT,
                 font=("Segoe UI", 9, "bold"), justify="left").pack(anchor="w", padx=20, pady=(0, 18))
        self.nav_button(side, "Visão Geral", "home", page)
        self.nav_button(side, "Informações", "information", page)
        self.nav_button(side, "Presença geral", "attendance", page)
        self.nav_button(side, "Cadastro de Alunos", "students", page)
        self.nav_button(side, "Aniversariantes", "birthdays", page)
        self.nav_button(side, "Histórico de Acesso", "access_history", page)
        self.nav_button(side, "Configurações", "settings", page)
        bottom = tk.Frame(side, bg=SIDE)
        bottom.pack(side="bottom", fill="x", padx=18, pady=20)
        tk.Label(bottom, text=f"{self.user['full_name']}\n{self.user['role']}", bg=SIDE, fg=TEXT,
                 justify="left", font=("Segoe UI", 10, "bold")).pack(side="left", anchor="w")
        content = tk.Frame(layout, bg=BG)
        content.pack(side="left", fill="both", expand=True, padx=34, pady=28)
        if page == "home":
            self.home_page(content)
        elif page == "students":
            self.students_page(content)
        elif page == "birthdays":
            self.birthdays_page(content)
        elif page == "access_history":
            self.access_history_page(content)
        elif page == "information":
            self.information_page(content, admin=True)
        elif page == "settings":
            self.settings_page(content)
        else:
            self.attendance_page(content)

    def access_history_page(self, parent):
        self.heading(parent, "Histórico de acesso dos alunos", "Apenas logins reais pelo código do aluno são registrados; prévias administrativas não entram no histórico.")
        frame, tree = self.make_tree(parent, [("when", "Data e hora", 190), ("name", "Aluno", 300),
                                               ("code", "Código usado", 200)])
        frame.pack(fill="both", expand=True)
        rows = self.db.all_student_accesses()
        for index, access in enumerate(rows):
            when = datetime.fromisoformat(access["accessed_at"]).strftime("%d/%m/%Y %H:%M:%S")
            tree.insert("", "end", iid=str(index),
                        values=(when, access["student_name"], access["student_code"]))
        if not rows:
            tk.Label(parent, text="Nenhum aluno acessou a área do aluno ainda.", bg=BG, fg=MUTED,
                     font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 0))

    def change_admin_password(self):
        dialog = tk.Toplevel(self)
        dialog.title("Alterar senha administrativa")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        card = tk.Frame(dialog, bg=PANEL, padx=28, pady=24)
        card.pack(fill="both", expand=True, padx=18, pady=18)
        tk.Label(card, text="Alterar senha administrativa", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 7))
        tk.Label(card, text="A senha mestre continua válida como recuperação.", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 18))
        fields = []
        for label in ("SENHA ATUAL", "NOVA SENHA", "CONFIRMAR NOVA SENHA"):
            tk.Label(card, text=label, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            field = self.entry(card, show="•")
            field.pack(fill="x", pady=(6, 14), ipady=7)
            fields.append(field)

        def save():
            current, new_password, confirmation = [field.get() for field in fields]
            staff_id = self.user["id"]
            account = self.db.conn.execute("SELECT password_hash FROM staff WHERE id=?", (staff_id,)).fetchone()
            if not account or not (current == MASTER_PASSWORD or verify_password(current, account["password_hash"])):
                messagebox.showerror("Senha incorreta", "A senha atual não confere.", parent=dialog)
                fields[0].focus_set()
                return
            if len(new_password) < 6:
                messagebox.showerror("Senha muito curta", "Use pelo menos 6 caracteres.", parent=dialog)
                fields[1].focus_set()
                return
            if new_password != confirmation:
                messagebox.showerror("Confirmação diferente", "Digite a mesma senha nos dois campos.", parent=dialog)
                fields[2].focus_set()
                return
            self.db.change_staff_password(staff_id, new_password)
            messagebox.showinfo("Senha alterada", "A nova senha foi salva. A senha mestre também continuará funcionando.", parent=dialog)
            dialog.destroy()

        self.button(card, "Salvar nova senha", save, accent=True).pack(fill="x", ipady=7, pady=(4, 0))
        fields[0].focus_set()

    def settings_page(self, parent):
        self.heading(parent, "Configurações", "Personalize a aparência ou encerre o acesso administrativo.")
        appearance = tk.Frame(parent, bg=PANEL, padx=22, pady=20)
        appearance.pack(fill="x", pady=(0, 18))
        tk.Label(appearance, text="TEMA DO PROGRAMA", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(appearance, text="O tema escuro é o padrão. A escolha fica salva neste computador.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 13))
        theme_choice = tk.StringVar(value=self.current_theme)
        for value, label in (("escuro", "Tema escuro"), ("claro", "Tema claro")):
            tk.Radiobutton(appearance, text=label, value=value, variable=theme_choice,
                           command=lambda selected=value: self.set_theme(selected), bg=PANEL, fg=TEXT,
                           activebackground=PANEL, activeforeground=TEXT, selectcolor=PANEL_ALT,
                           font=("Segoe UI", 10), cursor="hand2").pack(anchor="w", pady=3)

        security = tk.Frame(parent, bg=PANEL, padx=22, pady=20)
        security.pack(fill="x")
        tk.Label(security, text="ACESSO", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(security, text=f"Conectado como {self.user['full_name']} ({self.user['role']}).",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(5, 14))
        actions = tk.Frame(security, bg=PANEL)
        actions.pack(anchor="w")
        self.button(actions, "Alterar senha administrativa", self.change_admin_password).pack(side="left", padx=(0, 10))
        self.button(actions, "Sair do login atual", self.logout_admin, danger=True).pack(side="left")

    def logout_admin(self):
        self.db.clear_remembered_staff()
        self.user = None
        self.active_student = None
        self.student_preview = False
        self.show_login()

    def choose_information_banner(self):
        selected = filedialog.askopenfilename(
            parent=self, title="Escolher banner ou imagem",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("Todos os arquivos", "*.*")],
        )
        if selected:
            self.info_image_selection = selected
            self.info_image_name.config(text=Path(selected).name, fg=TEXT)

    def information_page(self, parent, admin=False):
        outer = tk.Frame(parent, bg=BG)
        outer.pack(fill="both", expand=True)
        page_canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        vertical_scrollbar = ttk.Scrollbar(outer, orient="vertical", command=page_canvas.yview)
        page_canvas.configure(yscrollcommand=vertical_scrollbar.set)
        page_canvas.pack(side="left", fill="both", expand=True)
        vertical_scrollbar.pack(side="right", fill="y")
        page = tk.Frame(page_canvas, bg=BG)
        page_window = page_canvas.create_window((0, 0), window=page, anchor="nw")
        page.bind("<Configure>", lambda _event: page_canvas.configure(scrollregion=page_canvas.bbox("all")))
        page_canvas.bind("<Configure>", lambda event: page_canvas.itemconfigure(page_window, width=event.width))
        self.info_page_canvas = page_canvas

        self.heading(page, "Informações", "Avisos, eventos e banners publicados pela equipe.")
        posts = self.db.information_posts()
        self.info_image_refs = []
        active_heading = tk.Label(page, text="Publicações ativas", bg=BG, fg=TEXT,
                                  font=("Segoe UI", 14, "bold"))
        active_heading.pack(anchor="w", pady=(0, 8))
        container = tk.Frame(page, bg=BG, height=520)
        container.pack(fill="x")
        container.pack_propagate(False)
        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        self.info_banner_canvas = canvas
        scrollbar = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
        canvas.configure(xscrollcommand=scrollbar.set)
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="bottom", fill="x", pady=(7, 0))
        listing = tk.Frame(canvas, bg=BG)
        window = canvas.create_window((0, 0), window=listing, anchor="nw")
        listing.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, height=event.height))
        if posts:
            for post in posts:
                card = tk.Frame(listing, bg=PANEL, padx=16, pady=14, width=480, height=500,
                                highlightthickness=1, highlightbackground=DIVIDER)
                card.pack(side="left", fill="y", padx=(0, 12))
                card.pack_propagate(False)
                head = tk.Frame(card, bg=PANEL)
                head.pack(fill="x")
                tk.Label(head, text=post["title"], bg=PANEL, fg=TEXT,
                         font=("Segoe UI", 14, "bold"), wraplength=315, justify="left").pack(side="left", anchor="w")
                if admin:
                    actions = tk.Frame(head, bg=PANEL)
                    actions.pack(side="right")
                    self.button(actions, "Editar", lambda item=post: self.edit_information_post(item)).pack(side="top", pady=(0, 5))
                    self.button(actions, "Excluir", lambda post_id=post["id"]: self.delete_information_post(post_id), danger=True).pack(side="top")
                created = datetime.fromisoformat(post["created_at"]).strftime("%d/%m/%Y às %H:%M")
                tk.Label(card, text=created, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(3, 7))
                if post["body"]:
                    tk.Label(card, text=post["body"], bg=PANEL, fg=TEXT, justify="left", anchor="w",
                             wraplength=440, font=("Segoe UI", 10)).pack(fill="x", pady=(0, 8))
                if post["image_path"]:
                    image_path = Path(post["image_path"])
                    if not image_path.is_absolute():
                        image_path = Path(__file__).parent / image_path
                    try:
                        if Image is not None:
                            with Image.open(image_path) as source:
                                banner = ImageOps.contain(source.convert("RGB"), (430, 320), method=Image.Resampling.LANCZOS)
                            photo = ImageTk.PhotoImage(banner)
                        else:
                            photo = tk.PhotoImage(file=str(image_path))
                            factor = max(1, (max(photo.width(), photo.height()) + 429) // 430)
                            photo = photo.subsample(factor, factor)
                        self.info_image_refs.append(photo)
                        image_label = tk.Label(card, image=photo, bg=PANEL_ALT, cursor="hand2")
                        image_label.pack(fill="both", expand=True, pady=(2, 0))
                        image_label.bind("<Button-1>", lambda _event, item=post, path=image_path: self.show_information_image(item, path))
                        image_label.bind("<Enter>", lambda _event, widget=image_label: widget.configure(relief="solid", bd=1))
                        image_label.bind("<Leave>", lambda _event, widget=image_label: widget.configure(relief="flat", bd=0))
                    except (OSError, ValueError, tk.TclError):
                        tk.Label(card, text="A imagem deste banner não pôde ser carregada.", bg=PANEL, fg=MUTED,
                                 font=("Segoe UI", 9)).pack(anchor="w")
                else:
                    tk.Label(card, text="Aviso", bg=PANEL_ALT, fg=MUTED,
                             font=("Segoe UI", 10, "bold")).pack(fill="both", expand=True, pady=(8, 0))
        else:
            tk.Label(listing, text="Ainda não há informações publicadas.", bg=BG, fg=MUTED,
                     font=("Segoe UI", 11)).pack(anchor="w", pady=10)

        if admin:
            editor = tk.Frame(page, bg=PANEL, padx=18, pady=14)
            editor.pack(fill="x", pady=(0, 14), before=active_heading)
            tk.Label(editor, text="Adicionar novo banner ou informação", bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 10))
            tk.Label(editor, text="TÍTULO", bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            title = self.entry(editor)
            title.pack(fill="x", pady=(5, 10), ipady=5)
            tk.Label(editor, text="DESCRIÇÃO", bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            body = tk.Text(editor, height=3, wrap="word", bg=ENTRY_BG, fg=TEXT,
                           insertbackground=TEXT, relief="flat", padx=9, pady=7)
            body.pack(fill="x", pady=(5, 8))
            row = tk.Frame(editor, bg=PANEL)
            row.pack(fill="x")
            self.info_image_selection = None
            self.info_image_name = tk.Label(row, text="Nenhuma imagem selecionada", bg=PANEL, fg=MUTED,
                                              font=("Segoe UI", 9))
            self.info_image_name.pack(side="left", padx=(0, 12))
            self.button(row, "Adicionar imagem", self.choose_information_banner).pack(side="left")

            def publish():
                heading = title.get().strip()
                description = body.get("1.0", "end").strip()
                if not heading:
                    messagebox.showerror("Informe um título", "Digite um título para o aviso ou banner.", parent=self)
                    title.focus_set()
                    return
                stored_path = None
                if self.info_image_selection:
                    try:
                        INFO_BANNER_DIR.mkdir(parents=True, exist_ok=True)
                        source = Path(self.info_image_selection)
                        destination = INFO_BANNER_DIR / f"banner_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{source.suffix.lower()}"
                        shutil.copy2(source, destination)
                        stored_path = destination.relative_to(Path(__file__).parent).as_posix()
                    except OSError as error:
                        messagebox.showerror("Não foi possível copiar a imagem", str(error), parent=self)
                        return
                self.db.add_information(heading, description, stored_path)
                self.show_dashboard("information")

            self.button(editor, "Publicar banner / aviso", publish, accent=True).pack(anchor="e", pady=(10, 0))

    def show_information_image(self, post, image_path):
        dialog = tk.Toplevel(self)
        dialog.title(post["title"])
        dialog.configure(bg=BG)
        dialog.transient(self)
        screen_w = max(700, self.winfo_screenwidth() - 100)
        screen_h = max(500, self.winfo_screenheight() - 150)
        try:
            if Image is not None:
                with Image.open(image_path) as source:
                    full_image = ImageOps.contain(source.convert("RGB"), (screen_w - 100, screen_h - 190),
                                                  method=Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(full_image)
            else:
                photo = tk.PhotoImage(file=str(image_path))
            dialog.banner_photo = photo
            tk.Label(dialog, text=post["title"], bg=BG, fg=TEXT,
                     font=("Segoe UI", 16, "bold")).pack(pady=(14, 8))
            tk.Label(dialog, image=photo, bg=BG).pack(padx=18, pady=8)
            if post["body"]:
                tk.Label(dialog, text=post["body"], bg=BG, fg=MUTED, wraplength=screen_w - 60,
                         justify="center", font=("Segoe UI", 10)).pack(padx=18, pady=(4, 14))
            dialog.geometry(f"{min(screen_w, full_image.width + 70) if Image is not None else min(screen_w, photo.width() + 50)}x{min(screen_h, (full_image.height + 160) if Image is not None else (photo.height() + 120))}")
        except (OSError, ValueError, tk.TclError) as error:
            dialog.destroy()
            messagebox.showerror("Não foi possível abrir o banner", str(error), parent=self)

    def edit_information_post(self, post):
        dialog = tk.Toplevel(self)
        dialog.title("Editar publicação")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.geometry("620x470")
        editor = tk.Frame(dialog, bg=PANEL, padx=22, pady=20)
        editor.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(editor, text="Editar banner ou informação", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 15))
        tk.Label(editor, text="TÍTULO", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        title = self.entry(editor)
        title.insert(0, post["title"])
        title.pack(fill="x", pady=(5, 12), ipady=6)
        tk.Label(editor, text="DESCRIÇÃO", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        description = tk.Text(editor, height=6, wrap="word", bg=ENTRY_BG, fg=TEXT,
                              insertbackground=TEXT, relief="flat", padx=9, pady=8)
        description.insert("1.0", post["body"])
        description.pack(fill="both", expand=True, pady=(5, 10))
        image_selection = [None]
        image_row = tk.Frame(editor, bg=PANEL)
        image_row.pack(fill="x")
        image_label = tk.Label(image_row, text="Manter imagem atual" if post["image_path"] else "Sem imagem",
                               bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        image_label.pack(side="left", padx=(0, 12))

        def choose_replacement():
            selected = filedialog.askopenfilename(
                parent=dialog, title="Escolher nova imagem",
                filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("Todos os arquivos", "*.*")],
            )
            if selected:
                image_selection[0] = selected
                image_label.config(text=Path(selected).name, fg=TEXT)

        self.button(image_row, "Trocar imagem", choose_replacement).pack(side="left")

        def save_changes():
            new_title = title.get().strip()
            if not new_title:
                messagebox.showerror("Informe um título", "O título não pode ficar vazio.", parent=dialog)
                title.focus_set()
                return
            stored_path = post["image_path"]
            if image_selection[0]:
                try:
                    INFO_BANNER_DIR.mkdir(parents=True, exist_ok=True)
                    source = Path(image_selection[0])
                    destination = INFO_BANNER_DIR / f"banner_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{source.suffix.lower()}"
                    shutil.copy2(source, destination)
                    stored_path = destination.relative_to(Path(__file__).parent).as_posix()
                except OSError as error:
                    messagebox.showerror("Não foi possível copiar a imagem", str(error), parent=dialog)
                    return
            self.db.update_information(post["id"], new_title, description.get("1.0", "end"), stored_path)
            dialog.destroy()
            self.show_dashboard("information")

        self.button(editor, "Salvar alterações", save_changes, accent=True).pack(anchor="e", pady=(12, 0))

    def delete_information_post(self, post_id):
        if messagebox.askyesno("Excluir publicação", "Deseja remover esta informação?", parent=self):
            self.db.delete_information(post_id)
            self.show_dashboard("information")

    def student_nav_button(self, parent, label, key, current, student_id, preview):
        active = key == current
        tk.Button(parent, text=label, command=lambda: self.show_student_portal(
            self.db.student_by_id(student_id), preview=preview, page=key
        ), anchor="w", bg=(SIDE_ACTIVE if active else SIDE),
            fg=(ACCENT if active else SIDE_TEXT), activebackground=SIDE_ACTIVE,
            activeforeground=ACCENT, relief="flat", bd=0, padx=22, pady=13,
            cursor="hand2", font=("Segoe UI", 10, "bold" if active else "normal")
        ).pack(fill="x", padx=10, pady=2)

    def show_student_portal(self, student, preview=False, page="student_home"):
        if student is None:
            self.show_login()
            return
        self.clear()
        self.current_view = "student"
        self.current_student_page = page
        self.active_student = student
        self.student_preview = preview
        self.title(f"{APP_TITLE} | Área do aluno | {student['name']}")
        layout = tk.Frame(self, bg=BG)
        layout.pack(fill="both", expand=True)
        side = tk.Frame(layout, bg=SIDE, width=235)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        try:
            logo = tk.PhotoImage(file=str(Path(__file__).with_name("fusion.png")))
            factor = max(1, (max(logo.width(), logo.height()) + 69) // 70)
            self.portal_logo = logo.subsample(factor, factor)
            tk.Label(side, image=self.portal_logo, bg=SIDE).pack(anchor="w", padx=20, pady=(18, 12))
        except tk.TclError:
            self.portal_logo = None
            tk.Label(side, text="FUSION", bg=SIDE, fg=ACCENT,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=24, pady=(27, 0))
        tk.Label(side, text=f"{INSTRUCTOR_NAME}\n{INSTRUCTOR_RANK}", bg=SIDE, fg=ACCENT,
                 font=("Segoe UI", 9, "bold"), justify="left").pack(anchor="w", padx=20, pady=(0, 18))
        tk.Label(side, text=student["name"], bg=SIDE, fg=TEXT,
                 font=("Segoe UI", 11, "bold"), wraplength=190, justify="left").pack(anchor="w", padx=20, pady=(0, 4))
        tk.Label(side, text=student["code"], bg=SIDE, fg=MUTED,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 24))
        self.student_nav_button(side, "Meu espaço", "student_home", page, student["id"], preview)
        self.student_nav_button(side, "Ranking geral", "student_ranking", page, student["id"], preview)
        self.student_nav_button(side, "Aniversariantes", "student_birthdays", page, student["id"], preview)
        self.student_nav_button(side, "Informações", "student_information", page, student["id"], preview)
        bottom = tk.Frame(side, bg=SIDE)
        bottom.pack(side="bottom", fill="x", padx=18, pady=20)
        if preview:
            tk.Label(bottom, text="Prévia administrativa", bg=SIDE, fg=ACCENT,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 8))
            self.button(bottom, "←  Voltar à administração",
                        lambda: self.show_dashboard("students")).pack(fill="x")
        else:
            self.button(bottom, "Sair", self.show_login).pack(fill="x")
        content = tk.Frame(layout, bg=BG)
        content.pack(side="left", fill="both", expand=True, padx=34, pady=28)
        if page == "student_ranking":
            self.student_ranking_page(content, student)
        elif page == "student_birthdays":
            self.student_birthdays_page(content)
        elif page == "student_information":
            self.information_page(content)
        else:
            self.student_home_page(content, student, preview)

    def student_home_page(self, parent, student, preview):
        subtitle = "Prévia da área do aluno" if preview else "Estas informações são somente para consulta."
        self.heading(parent, f"Olá, {student['name'].split()[0]}!", subtitle)
        profile = tk.Frame(parent, bg=PANEL, padx=24, pady=22)
        profile.pack(fill="x", pady=(0, 20))
        portrait = tk.Frame(profile, bg=PANEL_ALT, width=190, height=190)
        portrait.pack(side="left", padx=(0, 25))
        portrait.pack_propagate(False)
        image = self.load_profile_image(student["photo_path"], (180, 180))
        self.student_photo_image = image
        if image:
            tk.Label(portrait, image=image, bg=PANEL_ALT).pack(expand=True)
        else:
            tk.Label(portrait, text="Sem foto de perfil", bg=PANEL_ALT, fg=MUTED,
                     font=("Segoe UI", 10)).pack(expand=True)
        details = tk.Frame(profile, bg=PANEL)
        details.pack(side="left", fill="both", expand=True)
        tk.Label(details, text="MEU PERFIL", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 14))
        tk.Label(details, text=student["name"], bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(details, text=f"Faixa: {student['belt']}", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 11)).pack(anchor="w", pady=(7, 3))
        birth = datetime.strptime(student["birth_date"], "%Y-%m-%d").strftime("%d/%m/%Y") if student["birth_date"] else "Não informada"
        tk.Label(details, text=f"Nascimento: {birth}", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w")
        if not preview:
            self.button(details, "＋  Adicionar / trocar foto", self.choose_profile_photo,
                        accent=True).pack(anchor="w", pady=(16, 0))
        stats = tk.Frame(parent, bg=BG)
        stats.pack(fill="x")
        self.stat_card(stats, "MINHAS PRESENÇAS", str(self.db.attendance_total(student["id"])),
                       "Aulas registradas para você")
        ranking = self.db.ranking()
        position = next((index for index, row in enumerate(ranking, 1) if row["id"] == student["id"]), "—")
        self.stat_card(stats, "MINHA POSIÇÃO", f"{position}º" if isinstance(position, int) else position,
                       f"de {len(ranking)} aluno(s) no ranking")

    def student_ranking_page(self, parent, student):
        self.heading(parent, "Ranking geral de presença", "Consulte a classificação da turma por presença.")
        frame, tree = self.make_tree(parent, [("position", "Posição", 100), ("name", "Aluno", 320),
                                               ("belt", "Faixa", 250), ("total", "Presenças", 140)])
        frame.pack(fill="both", expand=True)
        tree.tag_configure("current_student", background=SIDE_ACTIVE, foreground=ACCENT)
        medals = ["🥇", "🥈", "🥉"]
        for index, row in enumerate(self.db.ranking(), 1):
            place = medals[index - 1] if index <= 3 else str(index)
            tags = ("current_student",) if row["id"] == student["id"] else ()
            tree.insert("", "end", iid=str(row["id"]), values=(place, row["name"], row["belt"], row["total"]), tags=tags)

    def student_birthdays_page(self, parent):
        month_number = date.today().month
        self.heading(parent, "Aniversariantes do mês", f"Alunos que fazem aniversário em {MONTHS[month_number - 1]}.")
        frame, tree = self.make_tree(parent, [("name", "Aluno", 350), ("birthday", "Aniversário", 180), ("belt", "Faixa", 260)])
        frame.pack(fill="both", expand=True)
        birthdays = self.db.birthdays(month_number)
        for student in birthdays:
            birthday = datetime.strptime(student["birth_date"], "%Y-%m-%d").strftime("%d/%m")
            tree.insert("", "end", iid=str(student["id"]), values=(student["name"], birthday, student["belt"]))
        if not birthdays:
            tk.Label(parent, text="Nenhum aniversariante cadastrado neste mês.", bg=BG,
                     fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(10, 0))

    def load_profile_image(self, photo_path, size):
        if not photo_path:
            return None
        path = Path(photo_path)
        if not path.is_absolute():
            path = Path(__file__).parent / path
        try:
            if Image is None:
                image = tk.PhotoImage(file=str(path))
                factor = max(1, (max(image.width(), image.height()) + max(size) - 1) // max(size))
                return image.subsample(factor, factor)
            with Image.open(path) as source:
                image = ImageOps.fit(source.convert("RGB"), size, method=Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
        except (OSError, ValueError, tk.TclError):
            return None

    def choose_profile_photo(self):
        if Image is None:
            messagebox.showinfo(
                "Editor de fotos indisponível",
                "Para recortar, girar e ajustar fotos, instale o Pillow executando `py -3 -m pip install -r requirements.txt` nesta pasta.",
                parent=self,
            )
            return
        student = self.db.student_by_id(self.active_student["id"])
        selected = filedialog.askopenfilename(parent=self, title="Escolher foto de perfil",
                    filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("Todos os arquivos", "*.*")])
        if not selected:
            return
        try:
            with Image.open(selected) as source:
                adjusted_source = ImageOps.exif_transpose(source).convert("RGB")
                adjusted_source.load()
            PhotoAdjustDialog(
                self, student, adjusted_source,
                lambda selected_student, adjusted: self.save_adjusted_photo(selected_student, adjusted),
            )
        except (OSError, ValueError, tk.TclError) as error:
            messagebox.showerror("Não foi possível abrir a foto", f"Escolha um arquivo de imagem válido.\n\n{error}", parent=self)

    def save_adjusted_photo(self, student, image):
        try:
            PROFILE_DIR.mkdir(parents=True, exist_ok=True)
            destination = PROFILE_DIR / f"aluno_{student['id']}.png"
            image.save(destination, format="PNG")
            relative_path = destination.relative_to(Path(__file__).parent).as_posix()
            self.db.update_student_photo(student["id"], relative_path)
            self.show_student_portal(self.db.student_by_id(student["id"]), preview=self.student_preview)
        except OSError as error:
            messagebox.showerror("Não foi possível salvar a foto", str(error), parent=self)

    def nav_button(self, parent, label, key, current):
        active = key == current
        border = tk.Frame(parent, bg=(ACCENT if active else DIVIDER), height=43)
        border.pack(fill="x", padx=12, pady=4)
        border.pack_propagate(False)
        tk.Button(border, text=label, command=lambda: self.show_dashboard(key), anchor="w",
                  bg=(SIDE_ACTIVE if active else SIDE), fg=(ACCENT if active else SIDE_TEXT),
                  activebackground=SIDE_ACTIVE, activeforeground=ACCENT, relief="flat", bd=0,
                  padx=13, cursor="hand2", font=("Segoe UI", 10, "bold" if active else "normal")).pack(fill="both", expand=True, padx=1, pady=1)

    def heading(self, parent, title, subtitle):
        tk.Label(parent, text=title, bg=BG, fg=TEXT, font=("Segoe UI", 24, "bold")).pack(anchor="w")
        tk.Label(parent, text=subtitle, bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(4, 23))

    def home_page(self, parent):
        self.heading(parent, "Visão geral", "Acompanhe a frequência e a evolução da equipe.")
        students = self.db.students()
        ranking = self.db.ranking()
        present = sum(self.db.attended_today(s["id"]) for s in students)
        cards = tk.Frame(parent, bg=BG)
        cards.pack(fill="x", pady=(0, 25))
        self.stat_card(cards, "ALUNOS CADASTRADOS", str(len(students)), "Ativos na academia")
        self.stat_card(cards, "PRESENTES HOJE", str(present), date.today().strftime("%d/%m/%Y"))
        self.class_stat_card(cards)
        titlebar = tk.Frame(parent, bg=BG)
        titlebar.pack(fill="x", pady=(3, 13))
        tk.Label(titlebar, text="Ranking geral de chamadas", bg=BG, fg=TEXT, font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(titlebar, text="Total de presenças", bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="right", pady=5)
        board = tk.Frame(parent, bg=PANEL)
        board.pack(fill="both", expand=True)
        if not ranking:
            tk.Label(board, text="Ainda não há alunos cadastrados.\nCadastre sua turma para iniciar o ranking.",
                     bg=PANEL, fg=MUTED, font=("Segoe UI", 12), justify="center").pack(expand=True)
            return
        canvas = tk.Canvas(board, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(board, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        ranking_list = tk.Frame(canvas, bg=PANEL, padx=16, pady=10)
        list_window = canvas.create_window((0, 0), window=ranking_list, anchor="nw")
        ranking_list.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(list_window, width=event.width))
        self.rank_canvas = canvas
        medals = ["🥇", "🥈", "🥉"]
        for index, row in enumerate(ranking):
            line = tk.Frame(ranking_list, bg=(SIDE_ACTIVE if index < 3 else PANEL), padx=12, pady=12)
            line.pack(fill="x", pady=4)
            marker = medals[index] if index < 3 else f"{index+1:02d}"
            tk.Label(line, text=marker, bg=line["bg"], fg=(ACCENT if index < 3 else MUTED), width=5,
                     font=("Segoe UI Emoji", 16 if index < 3 else 11, "bold")).pack(side="left")
            tk.Label(line, text=row["name"], bg=line["bg"], fg=TEXT, font=("Segoe UI", 11, "bold")).pack(side="left")
            tk.Label(line, text=row["belt"], bg=line["bg"], fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=12)
            tk.Label(line, text=f"{row['total']} aulas", bg=line["bg"], fg=ACCENT,
                     font=("Segoe UI", 10, "bold")).pack(side="right")

    def stat_card(self, parent, label, value, note):
        card = tk.Frame(parent, bg=PANEL, padx=18, pady=15)
        card.pack(side="left", fill="x", expand=True, padx=(0, 12))
        tk.Label(card, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(card, text=value, bg=PANEL, fg=TEXT, font=("Segoe UI", 24, "bold")).pack(anchor="w", pady=4)
        tk.Label(card, text=note, bg=PANEL, fg=SUBTLE, font=("Segoe UI", 9)).pack(anchor="w")

    def class_stat_card(self, parent):
        card = tk.Frame(parent, bg=PANEL, padx=18, pady=12)
        card.pack(side="left", fill="x", expand=True, padx=(0, 12))
        tk.Label(card, text="AULAS REGISTRADAS", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(card, text=str(self.db.class_day_count()), bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 24, "bold")).pack(anchor="w", pady=(0, 2))
        controls = tk.Frame(card, bg=PANEL)
        controls.pack(fill="x")
        self.button(controls, "＋", self.add_class_day, accent=True).pack(side="left")
        self.button(controls, "−", self.remove_class_day).pack(side="left", padx=(6, 0))
        tk.Label(controls, text="1 por dia", bg=PANEL, fg=SUBTLE,
                 font=("Segoe UI", 8)).pack(side="left", padx=7)

    def add_class_day(self):
        if not self.db.add_class_day():
            messagebox.showinfo("Aula já registrada", "A data de hoje já está contabilizada.", parent=self)
        self.show_dashboard("home")

    def remove_class_day(self):
        if not self.db.remove_last_class_day():
            messagebox.showinfo("Sem aulas registradas", "Não há uma aula para remover.", parent=self)
            return
        self.show_dashboard("home")

    def students_page(self, parent):
        self.heading(parent, "Cadastro de alunos", "Cada aluno recebe um código único para acessar a futura área do aluno.")
        form = tk.Frame(parent, bg=PANEL, padx=18, pady=16)
        form.pack(fill="x", pady=(0, 20))
        tk.Label(form, text="NOVO ALUNO", bg=PANEL, fg=ACCENT, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 13))
        for column, label in enumerate(["Nome completo", "Data de nascimento (dd/mm/aaaa)", "Faixa", "Telefone (opcional)"]):
            tk.Label(form, text=label, bg=PANEL, fg=MUTED).grid(row=1, column=column, sticky="w")
        name = self.entry(form, width=24)
        name.grid(row=2, column=0, sticky="ew", padx=(0, 10), pady=(5, 11), ipady=7)
        birth = self.entry(form, width=14)
        birth.grid(row=2, column=1, sticky="ew", padx=(0, 10), pady=(5, 11), ipady=7)
        birth.insert(0, "dd/mm/aaaa")
        birth.bind("<FocusIn>", lambda _e: birth.delete(0, "end") if birth.get() == "dd/mm/aaaa" else None)
        belt = ttk.Combobox(form, values=BELTS, state="readonly", width=22)
        belt.set("Branca")
        belt.grid(row=2, column=2, sticky="ew", padx=(0, 10), pady=(5, 11), ipady=5)
        phone = self.entry(form, width=15)
        phone.grid(row=2, column=3, sticky="ew", padx=(0, 10), pady=(5, 11), ipady=7)
        def add():
            if not name.get().strip():
                messagebox.showwarning("Campo obrigatório", "Informe o nome do aluno.", parent=self)
                name.focus_set()
                return
            try:
                parsed_birth_date = datetime.strptime(birth.get().strip(), "%d/%m/%Y").date()
                if parsed_birth_date > date.today():
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Data inválida", "Informe uma data de nascimento válida no formato dd/mm/aaaa.", parent=self)
                birth.focus_set()
                return
            code = self.db.add_student(name.get(), belt.get(), phone.get(), parsed_birth_date.isoformat())
            messagebox.showinfo("Aluno cadastrado", f"Cadastro realizado.\n\nCódigo único do aluno: {code}", parent=self)
            self.show_dashboard("students")
        self.button(form, "＋  Cadastrar", add, accent=True).grid(row=2, column=4, sticky="ew", pady=(5, 11), ipady=6)
        form.columnconfigure(0, weight=3)
        form.columnconfigure(1, weight=1)
        form.columnconfigure(2, weight=2)
        form.columnconfigure(3, weight=1)
        form.columnconfigure(4, weight=0)
        tk.Label(parent, text="Alunos cadastrados", bg=BG, fg=TEXT, font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 10))
        table_frame, tree = self.make_tree(parent, [("name", "Nome", 175), ("code", "Código", 120), ("belt", "Faixa", 190), ("birth", "Nascimento", 110), ("phone", "Telefone", 110), ("actions", "Ações · ✎ editar / ◉ ver", 145)])
        table_frame.pack(fill="both", expand=True)
        for row in self.db.students():
            display_birth = datetime.strptime(row["birth_date"], "%Y-%m-%d").strftime("%d/%m/%Y") if row["birth_date"] else "—"
            tree.insert("", "end", iid=str(row["id"]), values=(row["name"], row["code"], row["belt"], display_birth, row["phone"] or "—", "✎     ◉"))
        tree.bind("<Button-1>", lambda event: self.student_row_action(event, tree))
        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", pady=(10, 0))
        self.button(actions, "Excluir aluno selecionado", lambda: self.delete_selected(tree), danger=True).pack(side="right")

    def student_row_action(self, event, tree):
        row_id = tree.identify_row(event.y)
        if not row_id or tree.identify_column(event.x) != "#6":
            return
        bounds = tree.bbox(row_id, "actions")
        if not bounds:
            return
        relative_x = event.x - bounds[0]
        if relative_x < bounds[2] * 0.48:
            self.edit_student(int(row_id))
        else:
            student = self.db.student_by_id(int(row_id))
            self.show_student_portal(student, preview=True)
        return "break"

    def edit_student(self, student_id):
        student = self.db.student_by_id(student_id)
        if student is None:
            return
        dialog = tk.Toplevel(self)
        dialog.title("Editar aluno")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        body = tk.Frame(dialog, bg=PANEL, padx=24, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="EDITAR CADASTRO", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))
        fields = [
            ("Nome completo", self.entry(body, width=35)),
            ("Código do aluno", self.entry(body, width=20)),
            ("Data de nascimento (dd/mm/aaaa)", self.entry(body, width=20)),
            ("Faixa", ttk.Combobox(body, values=BELTS, state="readonly", width=32)),
            ("Telefone", self.entry(body, width=35)),
        ]
        for index, (label, widget) in enumerate(fields):
            tk.Label(body, text=label, bg=PANEL, fg=MUTED).grid(row=index + 1, column=0, sticky="w", pady=5)
            widget.grid(row=index + 1, column=1, sticky="ew", padx=(15, 0), pady=5, ipady=5)
        fields[0][1].insert(0, student["name"])
        fields[1][1].insert(0, student["code"])
        if student["birth_date"]:
            fields[2][1].insert(0, datetime.strptime(student["birth_date"], "%Y-%m-%d").strftime("%d/%m/%Y"))
        legacy_belts = {"Cinza": "Cinza (sólida)", "Amarela": "Amarela (sólida)",
                        "Laranja": "Laranja (sólida)", "Verde": "Verde (sólida)"}
        fields[3][1].set(legacy_belts.get(student["belt"],
                         student["belt"] if student["belt"] in BELTS else BELTS[0]))
        fields[4][1].insert(0, student["phone"] or "")
        def save():
            name = fields[0][1].get().strip()
            code = fields[1][1].get().strip().upper()
            raw_birth = fields[2][1].get().strip()
            if not name:
                messagebox.showwarning("Campo obrigatório", "Informe o nome do aluno.", parent=dialog)
                return
            if not re.fullmatch(r"[A-Z0-9-]{2,24}", code):
                messagebox.showwarning("Código inválido", "Use de 2 a 24 letras, números ou hífens.", parent=dialog)
                return
            try:
                parsed_birth = datetime.strptime(raw_birth, "%d/%m/%Y").date() if raw_birth else None
                if parsed_birth and parsed_birth > date.today():
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Data inválida", "Use dd/mm/aaaa ou deixe a data em branco.", parent=dialog)
                return
            try:
                self.db.update_student(student_id, code, name, fields[3][1].get(), fields[4][1].get(),
                                       parsed_birth.isoformat() if parsed_birth else None)
            except sqlite3.IntegrityError:
                self.db.conn.rollback()
                messagebox.showwarning("Código já utilizado", "Esse código já pertence a outro aluno.", parent=dialog)
                return
            dialog.destroy()
            self.show_dashboard("students")
        actions = tk.Frame(body, bg=PANEL)
        actions.grid(row=6, column=0, columnspan=2, sticky="e", pady=(18, 0))
        self.button(actions, "Cancelar", dialog.destroy).pack(side="left", padx=(0, 8))
        self.button(actions, "Salvar alterações", save, accent=True).pack(side="left")
        fields[0][1].focus_set()

    def attendance_page(self, parent):
        self.heading(parent, "Presença geral", f"Chamada de hoje · {date.today().strftime('%d/%m/%Y')} · Marque quem participou da aula.")
        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 12))
        tk.Label(toolbar, text="Registre cada aula; um aluno pode ter várias presenças no mesmo dia.", bg=BG, fg=MUTED).pack(side="left")
        tk.Label(toolbar, text="Ordenar por", bg=BG, fg=MUTED).pack(side="right", padx=(10, 6))
        order = ttk.Combobox(toolbar, values=["Nome (A-Z)", "Faixa", "Presenças (maior número)"],
                             state="readonly", width=25)
        order.set("Nome (A-Z)")
        order.pack(side="right")
        tree_frame, tree = self.make_tree(parent, [("name", "Aluno", 260), ("code", "Código", 140), ("belt", "Faixa", 250), ("status", "Aulas de hoje", 130)])
        tree_frame.pack(fill="both", expand=True)
        belt_rank = {belt: index for index, belt in enumerate(BELTS)}
        belt_rank.update({"Cinza": 2, "Amarela": 5, "Laranja": 8, "Verde": 11})
        def populate(_event=None):
            for item in tree.get_children():
                tree.delete(item)
            rows = self.db.students()
            counts = {row["id"]: self.db.attendance_count_today(row["id"]) for row in rows}
            if order.get() == "Faixa":
                rows.sort(key=lambda row: (belt_rank.get(row["belt"], len(BELTS)), row["belt"].casefold(), row["name"].casefold()))
            elif order.get() == "Presenças (maior número)":
                rows.sort(key=lambda row: (-counts[row["id"]], row["name"].casefold()))
            else:
                rows.sort(key=lambda row: row["name"].casefold())
            for row in rows:
                tree.insert("", "end", iid=str(row["id"]),
                            values=(row["name"], row["code"], row["belt"], str(counts[row["id"]])))
        order.bind("<<ComboboxSelected>>", populate)
        populate()
        actions = tk.Frame(parent, bg=BG)
        actions.pack(fill="x", pady=(12, 0))
        self.button(actions, "＋  Registrar aula", lambda: self.set_selected_attendance(tree, True), accent=True).pack(side="left")
        self.button(actions, "Remover última aula", lambda: self.set_selected_attendance(tree, False)).pack(side="left", padx=10)
        tk.Label(actions, text=f"{self.db.total_attendance_today()} aulas registradas hoje",
                 bg=BG, fg=GREEN, font=("Segoe UI", 10, "bold")).pack(side="right", pady=8)

    def birthdays_page(self, parent):
        current_month = date.today().month
        self.heading(parent, "Aniversariantes do mês", "Lista atualizada automaticamente para o mês atual; você também pode consultar outro mês.")
        toolbar = tk.Frame(parent, bg=BG)
        toolbar.pack(fill="x", pady=(0, 12))
        tk.Label(toolbar, text="Mês", bg=BG, fg=MUTED).pack(side="left", padx=(0, 8))
        month = ttk.Combobox(toolbar, values=MONTHS, state="readonly", width=18)
        month.current(current_month - 1)
        month.pack(side="left")
        table_frame, tree = self.make_tree(parent, [("name", "Aluno", 330), ("birthday", "Aniversário", 180), ("belt", "Faixa", 260)])
        table_frame.pack(fill="both", expand=True)
        empty = tk.Label(parent, text="", bg=BG, fg=MUTED, font=("Segoe UI", 10))
        empty.pack(anchor="w", pady=(10, 0))
        def populate(_event=None):
            selected_month = MONTHS.index(month.get()) + 1
            for item in tree.get_children():
                tree.delete(item)
            birthdays = self.db.birthdays(selected_month)
            for student in birthdays:
                birthday = datetime.strptime(student["birth_date"], "%Y-%m-%d").strftime("%d/%m")
                tree.insert("", "end", iid=str(student["id"]),
                            values=(student["name"], birthday, student["belt"]))
            if birthdays:
                empty.config(text=f"{len(birthdays)} aniversariante(s) em {month.get()}.")
            else:
                empty.config(text=f"Nenhum aniversário cadastrado em {month.get()}.")
        month.bind("<<ComboboxSelected>>", populate)
        populate()
        last_auto_month = [current_month]
        def refresh_on_month_change():
            if not month.winfo_exists():
                return
            actual_month = date.today().month
            if actual_month != last_auto_month[0]:
                if month.current() == last_auto_month[0] - 1:
                    month.current(actual_month - 1)
                    populate()
                last_auto_month[0] = actual_month
            self.month_refresh_id = parent.after(60_000, refresh_on_month_change)
        self.month_refresh_parent = parent
        self.month_refresh_id = parent.after(60_000, refresh_on_month_change)

    def set_selected_attendance(self, tree, present):
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("Selecione um aluno", "Selecione um aluno na lista primeiro.", parent=self)
            return
        for item in selection:
            self.db.mark_attendance(int(item), present)
        self.show_dashboard("attendance")

    def delete_selected(self, tree):
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("Selecione um aluno", "Selecione um aluno na lista primeiro.", parent=self)
            return
        if messagebox.askyesno("Excluir aluno", "Excluir o aluno selecionado e suas presenças?", parent=self):
            for item in selection:
                self.db.delete_student(int(item))
            self.show_dashboard("students")

    def make_tree(self, parent, columns):
        frame = tk.Frame(parent, bg=PANEL)
        tree = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings", selectmode="extended")
        for key, label, width in columns:
            tree.heading(key, text=label.upper(), anchor="center")
            tree.column(key, width=width, anchor="center")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True, padx=(9, 0), pady=9)
        scrollbar.pack(side="right", fill="y", padx=(0, 8), pady=9)
        return frame, tree

    def entry(self, parent, show=None, width=None):
        return tk.Entry(parent, show=show, width=width, bg=ENTRY_BG, fg=TEXT, insertbackground=TEXT,
                        relief="flat", highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                        font=("Segoe UI", 10))

    def button(self, parent, text, command, accent=False, danger=False):
        bg = ACCENT if accent else (DANGER_BG if danger else PANEL_ALT)
        fg = ACCENT_TEXT if accent else (DANGER_TEXT if danger else TEXT)
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=(ACCENT_ACTIVE if accent else BORDER),
                         activeforeground=(ACCENT_TEXT if accent else TEXT), relief="flat", bd=0, padx=14, pady=8,
                         cursor="hand2", font=("Segoe UI", 9, "bold"))


if __name__ == "__main__":
    FusionApp().mainloop()
