import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime

# === БАЗА ДАННЫХ ===
DB_NAME = "lost_found.db"
KEEPER_PASSWORD = "1234"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Находки
    c.execute("""
        CREATE TABLE IF NOT EXISTS finds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            color TEXT NOT NULL,
            scale TEXT,
            address TEXT,
            date_found TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'в хранении',
            finder TEXT,
            issued_to TEXT,
            issued_date TEXT
        )
    """)
    # Заявления о пропаже
    c.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            color TEXT NOT NULL,
            scale TEXT,
            address TEXT,
            date_lost TEXT NOT NULL,
            description TEXT,
            claimant TEXT,
            date_created TEXT
        )
    """)
    conn.commit()
    conn.close()


# === ЛОГИКА СОПОСТАВЛЕНИЯ ===
def find_matches(claim):
    """Возвращает список находок, подходящих под заявление по ключевым признакам."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, category, color, scale, address, date_found, description, status, finder
        FROM finds
        WHERE status != 'выдана'
          AND LOWER(category) = LOWER(?)
          AND LOWER(color) = LOWER(?)
    """, (claim['category'], claim['color']))
    rows = c.fetchall()
    conn.close()

    matches = []
    for r in rows:
        score = 0
        # Категория и цвет уже совпали
        score += 2
        if claim.get('scale') and r[3] and claim['scale'].lower() == r[3].lower():
            score += 1
        if claim.get('address') and r[4] and claim['address'].lower() in r[4].lower():
            score += 1
        if claim.get('date_lost') and r[5]:
            try:
                d1 = datetime.strptime(claim['date_lost'], "%Y-%m-%d")
                d2 = datetime.strptime(r[5], "%Y-%m-%d")
                if abs((d2 - d1).days) <= 3:
                    score += 1
            except ValueError:
                pass
        matches.append((score, r))

    matches.sort(key=lambda x: x[0], reverse=True)
    return matches


# === ГЛАВНОЕ ОКНО ===
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Учёт найденных и потерянных вещей")
        self.geometry("1000x650")

        self.resizable(width=False, height=False)

        # Выбор роли
        top = tk.Frame(self, bg="#000000", pady=10)
        top.pack(fill="y")
        top.pack(anchor="e")
        tk.Label(top, text="Роль:", bg="#000000", fg="white",
                 font=("Arial", 15, "bold")).pack(side="top", padx=5)
        self.role_var = tk.StringVar(value="Потерявший")
        role_cb = ttk.Combobox(top, textvariable=self.role_var,
                               values=["Потерявший", "Нашедший", "Хранитель"],
                               state="readonly", width=20)
        role_cb.pack(side="bottom")
        role_cb.bind("<<ComboboxSelected>>", lambda e: self.build_ui())

        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        self.build_ui()

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def build_ui(self):
        self.clear()
        role = self.role_var.get()
        if role == "Потерявший":
            LostView(self.container)
        elif role == "Нашедший":
            FinderView(self.container)
        else:  # Хранитель
            if not self.ask_keeper_password():
                # откат роли назад
                self.role_var.set("Потерявший")
                LostView(self.container)
                return
            KeeperView(self.container)

    def ask_keeper_password(self):
        """Запрашивает пароль. Возвращает True, если пароль верный."""
        win = tk.Toplevel(self)
        win.title("Вход для хранителя")
        win.geometry("320x160")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()  # модальное окно

        # центрируем относительно главного окна
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 320) // 2
        y = self.winfo_y() + (self.winfo_height() - 160) // 2
        win.geometry(f"+{x}+{y}")

        tk.Label(win, text="Введите пароль хранителя:",
                 font=("Arial", 11)).pack(pady=10)

        pwd_var = tk.StringVar()
        entry = tk.Entry(win, textvariable=pwd_var, show="*", width=25)
        entry.pack(pady=5)
        entry.focus_set()

        result = {"ok": False}

        def confirm(event=None):
            if pwd_var.get() == KEEPER_PASSWORD:
                result["ok"] = True
                win.destroy()
            else:
                messagebox.showerror("Ошибка", "Неверный пароль.")
                pwd_var.set("")
                entry.focus_set()

        def cancel():
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(pady=10)
        tk.Button(btns, text="Войти", bg="#2980b9", fg="white",
                  width=10, command=confirm).pack(side="left", padx=5)
        tk.Button(btns, text="Отмена", width=10,
                  command=cancel).pack(side="left", padx=5)

        entry.bind("<Return>", confirm)
        win.bind("<Escape>", lambda e: cancel())

        self.wait_window(win)  # ждём закрытия окна
        return result["ok"]


# === ВКЛАДКА "ПОТЕРЯВШИЙ" ===
class LostView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        tk.Label(self, text="Подача заявления о пропаже",
                 font=("Arial", 20, "bold")).pack(anchor="nw", pady=20, padx=35)



        form = tk.Frame(self)
        form.pack(pady=5)
        form.pack(padx=50)
        form.pack(anchor="e")
        form.pack(side="left")

        self.vars = {}
        fields = [
            ("Категория", "category"),
            ("Цвет", "color"),
            ("Размер/масштаб", "scale"),
            ("Место пропажи", "address"),
            ("Дата (ГГГГ-ММ-ДД)", "date_lost"),
            ("Краткое описание", "description"),
            ("Ваше имя", "claimant"),
        ]
        for i, (label, key) in enumerate(fields):
            tk.Label(form, text=label + ":").grid(row=i, column=0, sticky="e", padx=5, pady=3)
            e = tk.Entry(form, width=40)
            e.grid(row=i, column=1, padx=5, pady=10)
            self.vars[key] = e

        tk.Button(self, text="Отправить заявление и найти совпадения",
                  bg="#27ae60", fg="white",
                  command=self.submit).pack(padx=10, pady=10, anchor="center")

        tk.Label(self, text="Релевантные совпадения:",
                 font=("Arial", 11, "bold")).pack(anchor="e", padx=50)

        cols = ("id", "category", "color", "scale", "address", "date_found", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=20)
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

    def submit(self):
        claim = {k: v.get().strip() for k, v in self.vars.items()}
        if not claim['category'] or not claim['color'] or not claim['date_lost']:
            messagebox.showwarning("Ошибка", "Заполните категорию, цвет и дату.")
            return

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            INSERT INTO claims (category, color, scale, address, date_lost, description, claimant, date_created)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (claim['category'], claim['color'], claim['scale'], claim['address'],
              claim['date_lost'], claim['description'], claim['claimant'],
              datetime.now().strftime("%Y-%m-%d %H:%M")))
        conn.commit()
        conn.close()

        matches = find_matches(claim)
        for row in self.tree.get_children():
            self.tree.delete(row)

        if not matches:
            messagebox.showinfo("Результат", "Совпадений не найдено.")
            return

        for score, r in matches:
            self.tree.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4], r[5], r[7]))
        messagebox.showinfo("Готово", f"Найдено совпадений: {len(matches)}")


# === ВКЛАДКА "НАШЕДШИЙ" ===
class FinderView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        tk.Label(self, text="Информация для нашедшего",
                 font=("Arial", 14, "bold")).pack(pady=10)

        info = (
            "Если вы нашли вещь:\n\n"
            "1. Принесите её в центр хранения.\n"
            "2. Передайте вещь хранителю.\n"
            "3. Хранитель зарегистрирует находку в системе.\n\n"
            "Спасибо за вашу честность и помощь!"
        )
        tk.Label(self, text=info, justify="left", font=("Arial", 11)).pack(pady=10)

        tk.Label(self, text="Ваши переданные находки:",
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=10, pady=(20, 5))

        cols = ("id", "category", "color", "date_found", "status")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=15)
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=150)
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)

        tk.Label(self, text="Имя нашедшего для фильтра:").pack(anchor="w", padx=10)
        self.name_entry = tk.Entry(self, width=30)
        self.name_entry.pack(anchor="w", padx=10, pady=3)
        tk.Button(self, text="Показать", command=self.load).pack(anchor="w", padx=10, pady=5)

    def load(self):
        name = self.name_entry.get().strip()
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        if name:
            c.execute("SELECT id, category, color, date_found, status FROM finds WHERE LOWER(finder)=LOWER(?)",
                      (name,))
        else:
            c.execute("SELECT id, category, color, date_found, status FROM finds")
        rows = c.fetchall()
        conn.close()

        for row in self.tree.get_children():
            self.tree.delete(row)
        for r in rows:
            self.tree.insert("", "end", values=r)


# === ВКЛАДКА "ХРАНИТЕЛЬ" ===
class KeeperView(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.pack(fill="both", expand=True)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=5, pady=5)

        self.tab_reg = tk.Frame(nb)
        self.tab_all = tk.Frame(nb)
        nb.add(self.tab_reg, text="Регистрация находки")
        nb.add(self.tab_all, text="Все находки")

        self.build_register()
        self.build_all()

    # --- Регистрация находки ---
    def build_register(self):
        tk.Label(self.tab_reg, text="Пошаговая регистрация находки",
                 font=("Arial", 13, "bold")).pack(pady=8)

        form = tk.Frame(self.tab_reg)
        form.pack(pady=5)

        self.fields = {}
        items = [
            ("Категория", "category"),
            ("Цвет", "color"),
            ("Размер/масштаб", "scale"),
            ("Место находки", "address"),
            ("Дата находки (ГГГГ-ММ-ДД)", "date_found"),
            ("Краткое описание", "description"),
            ("Кто принёс (нашедший)", "finder"),
        ]
        for i, (label, key) in enumerate(items):
            tk.Label(form, text=label + ":").grid(row=i, column=0, sticky="e", padx=5, pady=3)
            e = tk.Entry(form, width=40)
            e.grid(row=i, column=1, padx=5, pady=3)
            self.fields[key] = e

        self.status_var = tk.StringVar(value="в хранении")
        tk.Label(form, text="Статус:").grid(row=len(items), column=0, sticky="e", padx=5, pady=3)
        ttk.Combobox(form, textvariable=self.status_var,
                     values=["в хранении", "есть совпадение", "выдана"],
                     state="readonly", width=37).grid(row=len(items), column=1, padx=5, pady=3)

        tk.Button(self.tab_reg, text="Принять на хранение",
                  bg="#2980b9", fg="white",
                  command=self.register_find).pack(pady=10)

    def register_find(self):
        data = {k: v.get().strip() for k, v in self.fields.items()}
        if not data['category'] or not data['color'] or not data['date_found']:
            messagebox.showwarning("Ошибка", "Заполните категорию, цвет и дату находки.")
            return
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            INSERT INTO finds (category, color, scale, address, date_found, description, status, finder)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (data['category'], data['color'], data['scale'], data['address'],
              data['date_found'], data['description'], self.status_var.get(), data['finder']))
        conn.commit()
        conn.close()
        messagebox.showinfo("Готово", "Находка зарегистрирована.")
        for e in self.fields.values():
            e.delete(0, tk.END)
        self.refresh_all()

    # --- Все находки ---
    def build_all(self):
        cols = ("id", "category", "color", "scale", "address", "date_found", "status", "finder")
        self.all_tree = ttk.Treeview(self.tab_all, columns=cols, show="headings", height=18)
        for c in cols:
            self.all_tree.heading(c, text=c)
            self.all_tree.column(c, width=110)
        self.all_tree.pack(fill="both", expand=True, padx=5, pady=5)

        btns = tk.Frame(self.tab_all)
        btns.pack(pady=5)
        tk.Button(btns, text="Обновить", command=self.refresh_all).pack(side="left", padx=5)
        tk.Button(btns, text="Выдать вещь", bg="#27ae60", fg="white",
                  command=self.issue_item).pack(side="left", padx=5)
        tk.Button(btns, text="Напомнить о незабранных", bg="#e67e22", fg="white",
                  command=self.remind).pack(side="left", padx=5)

        self.refresh_all()

    def refresh_all(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""SELECT id, category, color, scale, address, date_found, status, finder
                     FROM finds ORDER BY id DESC""")
        rows = c.fetchall()
        conn.close()
        for row in self.all_tree.get_children():
            self.all_tree.delete(row)
        for r in rows:
            self.all_tree.insert("", "end", values=r)

    def issue_item(self):
        sel = self.all_tree.selection()
        if not sel:
            messagebox.showwarning("Ошибка", "Выберите находку.")
            return
        item = self.all_tree.item(sel[0])['values']
        find_id = item[0]

        win = tk.Toplevel(self)
        win.title("Выдача вещи")
        win.geometry("300x200")

        tk.Label(win, text="Кто получил (ФИО):").pack(pady=5)
        name_e = tk.Entry(win, width=30)
        name_e.pack(pady=5)

        def confirm():
            name = name_e.get().strip()
            if not name:
                messagebox.showwarning("Ошибка", "Введите имя получателя.")
                return
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("""UPDATE finds SET status='выдана', issued_to=?, issued_date=?
                         WHERE id=?""",
                      (name, datetime.now().strftime("%Y-%m-%d %H:%M"), find_id))
            conn.commit()
            conn.close()
            messagebox.showinfo("Готово", "Вещь выдана, запись закрыта.")
            win.destroy()
            self.refresh_all()

        tk.Button(win, text="Подтвердить выдачу", bg="#27ae60", fg="white",
                  command=confirm).pack(pady=10)

    def remind(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""SELECT id, category, color, date_found FROM finds
                     WHERE status='в хранении'""")
        rows = c.fetchall()
        conn.close()
        if not rows:
            messagebox.showinfo("Напоминания", "Незабранных находок нет.")
            return
        text = "Незабранные находки (в хранении):\n\n"
        for r in rows:
            text += f"№{r[0]} — {r[1]}, {r[2]}, найдено {r[3]}\n"
        messagebox.showinfo("Напоминания", text)


if __name__ == "__main__":
    init_db()
    app = App()
    app.mainloop()

