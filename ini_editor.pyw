"""
INI Settings Editor — красивое приложение для редактирования .ini файлов.
Save-All версия: изменения всех файлов держатся в памяти.
"""

import customtkinter as ctk
import os
import re
from tkinter import filedialog, messagebox


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PATH_HINTS = ['путь', 'папка', 'path', 'folder', 'dir', 'directory']


# ------------------------------------------------------------------ helpers
def detect_type(key, value, comment):
    v = value.strip()
    c = comment.lower()
    if any(h in c for h in PATH_HINTS):
        return 'path'
    if ('\\' in v or '/' in v) and not v.startswith('#'):
        return 'path'
    if v in ('0', '1'):
        return 'bool'
    if re.fullmatch(r'-?\d+', v):
        return 'int'
    if re.fullmatch(r'#[0-9A-Fa-f]{6}', v):
        return 'color'
    return 'str'


def parse_range(comment):
    m = re.search(r'(\d+)\s*[\.\-~]{1,2}\s*(\d+)', comment)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b > a and b - a <= 10000:
            return a, b
    return None


# ------------------------------------------------------------------ app
class IniEditor(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("INI Редактор Настроек")
        self.geometry("1220x780")
        self.minsize(950, 620)

        self.config_dir = os.path.dirname(os.path.abspath(__file__))
        self.current_file = None
        self.current_lines = []
        self.kv_widgets = {}
        self.file_buttons = {}

        # path -> {'lines': [...], 'dirty': bool}
        self.files_cache = {}

        self._build_ui()
        self._load_files(self.config_dir)

    # -------------------------------------------------------- UI
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(3, weight=1)
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="⚙️  Настройки",
                     font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, padx=20, pady=(20, 8), sticky="w")

        self.dir_lbl = ctk.CTkLabel(sidebar, text=self.config_dir,
                                    font=("Segoe UI", 10), text_color="gray",
                                    wraplength=240, justify="left")
        self.dir_lbl.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")

        ctk.CTkButton(sidebar, text="📂  Открыть папку",
                      command=self._choose_dir, height=36).grid(
            row=2, column=0, padx=20, pady=(0, 12), sticky="ew")

        self.file_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.file_list.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        theme_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        theme_frame.grid(row=4, column=0, padx=20, pady=(0, 15), sticky="ew")
        ctk.CTkLabel(theme_frame, text="Тема:",
                     font=("Segoe UI", 11)).pack(side="left")
        self.theme_switch = ctk.CTkSegmentedButton(
            theme_frame, values=["🌙 Тёмная", "☀️ Светлая"],
            command=self._set_theme)
        self.theme_switch.set("🌙 Тёмная")
        self.theme_switch.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Main
        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkLabel(main, text="Выберите файл слева",
                                    font=("Segoe UI", 22, "bold"))
        self.header.grid(row=0, column=0, padx=30, pady=(20, 10), sticky="w")

        self.scroll = ctk.CTkScrollableFrame(main, corner_radius=10)
        self.scroll.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(main, fg_color="transparent")
        bottom.grid(row=2, column=0, padx=20, pady=(0, 20), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)

        self.status = ctk.CTkLabel(bottom, text="", text_color="#7FBA00",
                                    font=("Segoe UI", 12, "bold"))
        self.status.grid(row=0, column=0, padx=10, sticky="w")

        ctk.CTkButton(bottom, text="💾  Сохранить всё",
                      command=self._save_all,
                      font=("Segoe UI", 14, "bold"),
                      height=42, width=200).grid(row=0, column=1)

    def _set_theme(self, value):
        ctk.set_appearance_mode("light" if "Свет" in value else "dark")

    # -------------------------------------------------------- load files
    def _load_files(self, folder):
        self.config_dir = os.path.abspath(folder)
        self.dir_lbl.configure(text=self.config_dir)
        self.current_file = None
        self.files_cache.clear()

        for w in self.file_list.winfo_children():
            w.destroy()
        self.file_buttons.clear()
        self.header.configure(text="Выберите файл слева")
        for w in self.scroll.winfo_children():
            w.destroy()

        try:
            entries = sorted(os.listdir(self.config_dir))
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось прочитать папку:\n{e}")
            return

        found = False
        for fname in entries:
            if fname.lower().endswith('.ini'):
                found = True
                path = os.path.join(self.config_dir, fname)
                btn = ctk.CTkButton(
                    self.file_list, text=f"  📄  {fname}",
                    anchor="w", fg_color="transparent",
                    hover_color=("gray75", "gray28"),
                    text_color=("gray10", "gray90"),
                    height=34, corner_radius=6,
                    command=lambda p=path: self._open_file(p))
                btn.pack(fill="x", pady=2)
                self.file_buttons[path] = btn

        if not found:
            ctk.CTkLabel(self.file_list, text="Файлы .ini не найдены",
                         text_color="gray").pack(pady=20)

    def _choose_dir(self):
        # перед сменой папки - спросим, если есть несохранённое
        if not self._confirm_unsaved():
            return
        d = filedialog.askdirectory(initialdir=self.config_dir)
        if d:
            self._load_files(d)

    def _confirm_unsaved(self):
        dirty = [p for p, d in self.files_cache.items() if d.get('dirty')]
        if not dirty:
            return True
        res = messagebox.askyesnocancel(
            "Несохранённые изменения",
            f"Есть изменения в {len(dirty)} файл(ах).\n\n"
            "Да — сохранить и продолжить\n"
            "Нет — не сохранять\n"
            "Отмена — вернуться")
        if res is None:
            return False
        if res:
            self._save_all(silent=True)
        return True

    # -------------------------------------------------------- open file
    def _open_file(self, path):
        # значение кеша уже актуально, т.к. поля пишут в lines через trace
        if path not in self.files_cache:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
                return
            self.files_cache[path] = {'lines': lines, 'dirty': False}

        self.current_file = path
        self.current_lines = self.files_cache[path]['lines']
        self.header.configure(text=f"📄  {os.path.basename(path)}")

        # подсветка активной кнопки
        for p, b in self.file_buttons.items():
            active = (p == path)
            b.configure(fg_color="#1F6AA5" if active else "transparent",
                        text_color=("white", "white") if active else ("gray10", "gray90"))

        self._render()
        self._refresh_status()

    # -------------------------------------------------------- render
    def _render(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.kv_widgets.clear()

        row = 0
        pending_comments = []

        for idx, raw_line in enumerate(self.current_lines):
            line = raw_line.rstrip('\n').rstrip('\r')
            s = line.strip()

            if not s:
                pending_comments = []
                continue

            if s.startswith(';') or (s.startswith('#') and '=' not in s):
                pending_comments.append(s.lstrip(';#').strip())
                continue

            if s.startswith('[') and s.endswith(']'):
                self._add_section(row, s[1:-1], pending_comments)
                pending_comments = []
                row += 1
                continue

            if '=' in s:
                key, _, val = line.partition('=')
                self._add_field(row, idx, key.strip(), val.strip(),
                                '\n'.join(pending_comments))
                pending_comments = []
                row += 1
                continue

            self._add_raw_line(row, idx, line)
            pending_comments = []
            row += 1

    def _add_section(self, row, name, comments):
        frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(16, 8))
        frame.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")

        ctk.CTkLabel(top, text="▌", text_color=("#1F6AA5", "#3B8ED0"),
                     font=("Segoe UI", 20, "bold")).pack(side="left", padx=(5, 6))
        ctk.CTkLabel(top, text=name, font=("Segoe UI", 16, "bold"),
                     text_color=("#1F6AA5", "#5AA9E6")).pack(side="left")

        if comments:
            ctk.CTkLabel(frame, text='\n'.join(comments), font=("Segoe UI", 10),
                         text_color="gray", justify="left", anchor="w",
                         wraplength=850).grid(row=1, column=0, padx=(20, 5),
                                              pady=(4, 0), sticky="w")

    def _add_field(self, row, line_idx, key, value, comment):
        ftype = detect_type(key, value, comment)

        card = ctk.CTkFrame(self.scroll, corner_radius=10,
                            fg_color=("gray90", "gray16"))
        card.grid(row=row, column=0, sticky="ew", padx=5, pady=4)
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=15, pady=12)
        inner.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(inner, text=key, font=("Segoe UI", 13, "bold"),
                     anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 20))

        var, widget = self._make_widget(inner, ftype, value, comment)
        widget.grid(row=0, column=1, sticky="ew")

        if comment:
            ctk.CTkLabel(card, text=comment, font=("Segoe UI", 10),
                         text_color="gray", justify="left", anchor="w",
                         wraplength=780).grid(row=1, column=0, padx=18,
                                              pady=(0, 10), sticky="w")

        self.kv_widgets[line_idx] = {'key': key, 'var': var, 'type': ftype}

        # Ключевой момент: любое изменение виджета — сразу пишем в lines
        var.trace_add('write',
                      lambda *_a, i=line_idx: self._on_field_change(i))

    def _add_raw_line(self, row, line_idx, line):
        var = ctk.StringVar(value=line)
        card = ctk.CTkFrame(self.scroll, corner_radius=8,
                            fg_color=("gray88", "gray17"))
        card.grid(row=row, column=0, sticky="ew", padx=5, pady=2)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(card, textvariable=var,
                     font=("Consolas", 12)).grid(
            row=0, column=0, padx=10, pady=6, sticky="ew")
        self.kv_widgets[line_idx] = {'key': None, 'var': var, 'type': 'raw'}
        var.trace_add('write',
                      lambda *_a, i=line_idx: self._on_field_change(i))

    # -------------------------------------------------------- widget factory
    def _make_widget(self, parent, ftype, value, comment):
        if ftype == 'bool':
            var = ctk.IntVar(value=1 if value.strip() == '1' else 0)
            w = ctk.CTkSwitch(parent, text="", variable=var, onvalue=1,
                              offvalue=0, switch_width=48, switch_height=22)
            return var, w

        if ftype == 'int':
            try:
                cur = int(value)
            except Exception:
                cur = 0
            rng = parse_range(comment)
            if rng:
                minv, maxv = rng
                cur = max(minv, min(maxv, cur))
                var = ctk.IntVar(value=cur)
                container = ctk.CTkFrame(parent, fg_color="transparent")
                container.grid_columnconfigure(0, weight=1)
                ctk.CTkSlider(container, from_=minv, to=maxv, variable=var,
                              number_of_steps=maxv - minv).grid(
                    row=0, column=0, sticky="ew", padx=(0, 12))
                ctk.CTkLabel(container, textvariable=var, width=60,
                             font=("Segoe UI", 12, "bold")).grid(row=0, column=1)
                return var, container
            var = ctk.IntVar(value=cur)
            return var, ctk.CTkEntry(parent, textvariable=var)

        if ftype == 'path':
            var = ctk.StringVar(value=value)
            container = ctk.CTkFrame(parent, fg_color="transparent")
            container.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(container, textvariable=var).grid(
                row=0, column=0, sticky="ew")
            ctk.CTkButton(container, text="📂", width=42,
                          command=lambda v=var: self._browse_path(v)).grid(
                row=0, column=1, padx=(6, 0))
            return var, container

        if ftype == 'color':
            var = ctk.StringVar(value=value)
            container = ctk.CTkFrame(parent, fg_color="transparent")
            container.grid_columnconfigure(1, weight=1)
            swatch = ctk.CTkFrame(container, width=30, height=30,
                                  corner_radius=6, fg_color=value)
            swatch.grid(row=0, column=0, padx=(0, 8))
            swatch.grid_propagate(False)
            ctk.CTkEntry(container, textvariable=var).grid(
                row=0, column=1, sticky="ew")
            var.trace_add('write',
                          lambda *a, s=swatch, v=var: self._update_swatch(s, v.get()))
            return var, container

        var = ctk.StringVar(value=value)
        return var, ctk.CTkEntry(parent, textvariable=var)

    def _update_swatch(self, swatch, val):
        try:
            swatch.configure(fg_color=val)
        except Exception:
            pass

    # -------------------------------------------------------- live write to cache
    def _on_field_change(self, idx):
        info = self.kv_widgets.get(idx)
        if not info or not self.current_file:
            return
        lines = self.files_cache[self.current_file]['lines']
        if idx >= len(lines):
            return

        raw = lines[idx]
        eol = '\n' if raw.endswith('\n') else ''
        t = info['type']
        var = info['var']

        try:
            if t == 'raw':
                new_line = str(var.get()) + eol
            else:
                val = '1' if (t == 'bool' and var.get() == 1) else \
                      '0' if (t == 'bool') else str(var.get())
                content = raw.rstrip('\n').rstrip('\r')
                m = re.match(r'^(\s*[^=]*?=\s*)(.*?)(\s*)$', content)
                if m:
                    new_line = m.group(1) + val + m.group(3) + eol
                else:
                    new_line = f"{info['key']}={val}{eol}"
        except Exception:
            return

        if lines[idx] != new_line:
            lines[idx] = new_line
            self.files_cache[self.current_file]['dirty'] = True
            self._refresh_status()
            self._update_file_button_label(self.current_file)

    # -------------------------------------------------------- path picker
    def _browse_path(self, var):
        val = var.get().strip()
        base = os.path.basename(val.replace('\\', '/'))
        is_file = '.' in base and base.split('.')[-1].lower() in (
            'log', 'ini', 'txt', 'lua', 'exe', 'dll', 'cfg', 'dat')

        initial = self.config_dir
        if val:
            cand = val if os.path.isabs(val) else os.path.join(self.config_dir, val)
            if os.path.exists(cand):
                initial = cand if os.path.isdir(cand) else os.path.dirname(cand)

        if is_file:
            picked = filedialog.askopenfilename(initialdir=initial,
                                                title="Выберите файл")
        else:
            picked = filedialog.askdirectory(initialdir=initial,
                                             title="Выберите папку")
        if not picked:
            return

        rel = self._make_relative(picked)
        if not is_file and (val.endswith('\\') or val.endswith('/')) and \
                not rel.endswith(('\\', '/')):
            rel += '\\'
        var.set(rel)

    def _make_relative(self, path):
        try:
            rel = os.path.relpath(path, self.config_dir)
            if not rel.startswith('..'):
                return rel
        except Exception:
            pass
        return path

    # -------------------------------------------------------- status & labels
    def _refresh_status(self):
        dirty_files = [p for p, d in self.files_cache.items() if d.get('dirty')]
        if dirty_files:
            self.status.configure(
                text=f"⚠  Несохранённых файлов: {len(dirty_files)}",
                text_color="#E5A100")
        else:
            self.status.configure(text="Все изменения сохранены",
                                  text_color="#7FBA00")

    def _update_file_button_label(self, path):
        btn = self.file_buttons.get(path)
        if not btn:
            return
        name = os.path.basename(path)
        dirty = self.files_cache.get(path, {}).get('dirty')
        btn.configure(text=f"  {'●' if dirty else '📄'}  {name}")

    # -------------------------------------------------------- save
    def _save_all(self, silent=False):
        if not self.files_cache:
            if not silent:
                messagebox.showinfo("Инфо", "Нет открытых файлов")
            return

        saved, failed = [], []
        for path, data in self.files_cache.items():
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    f.writelines(data['lines'])
                data['dirty'] = False
                saved.append(path)
                self._update_file_button_label(path)
            except Exception as e:
                failed.append((path, e))

        self._refresh_status()

        if failed:
            msg = "\n".join(f"{os.path.basename(p)}: {e}" for p, e in failed)
            messagebox.showerror("Ошибка сохранения", msg)
            return

        if not silent:
            self.status.configure(
                text=f"✅  Сохранено файлов: {len(saved)}",
                text_color="#7FBA00")
            self.after(3000, self._refresh_status)

    # -------------------------------------------------------- graceful exit
    def on_close(self):
        if self._confirm_unsaved():
            self.destroy()


if __name__ == "__main__":
    app = IniEditor()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()