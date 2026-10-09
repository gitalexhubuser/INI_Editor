"""INI Settings Editor — компактный графический редактор INI с автосохранением."""

import os
import re
import sys
import tempfile
import customtkinter as ctk
from tkinter import filedialog, messagebox


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PATH_HINTS = ['путь', 'папка', 'path', 'folder', 'dir', 'directory']
BOOL_TOKENS = {
    '0', '1', 'true', 'false', 'yes', 'no', 'on', 'off', 'enabled', 'disabled',
    'да', 'нет'
}
FIELD_FONT = ("Segoe UI", 15)
KEY_FONT = ("Segoe UI", 15, "bold")
COMMENT_FONT = ("Segoe UI", 12)
ENTRY_HEIGHT = 32
AUTOSAVE_DELAY_MS = 450


def read_ini_file(path):
    """Read an INI file while retaining its encoding and exact line endings."""
    with open(path, 'rb') as f:
        raw = f.read()

    if raw.startswith(b'\xef\xbb\xbf'):
        encoding = 'utf-8-sig'
        text = raw.decode(encoding)
    elif raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        encoding = 'utf-16'
        text = raw.decode(encoding)
    else:
        text = None
        encoding = None
        for candidate in ('utf-8', 'mbcs', 'cp1251', 'cp1252'):
            try:
                text = raw.decode(candidate)
                encoding = candidate
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            raise UnicodeError('Не удалось определить кодировку файла')

    return text.splitlines(keepends=True), encoding


def get_line_ending(line):
    if line.endswith('\r\n'):
        return '\r\n'
    if line.endswith('\n'):
        return '\n'
    if line.endswith('\r'):
        return '\r'
    return ''


def detect_type(key, value, comment):
    """Infer a suitable control from an INI value and its comment."""
    v = value.strip()
    c = comment.lower()

    if any(h in c for h in PATH_HINTS):
        return 'path'
    if v.lower() in BOOL_TOKENS:
        return 'bool'
    if re.fullmatch(r'#[0-9A-Fa-f]{6}', v):
        return 'color'
    if ('\\' in v or '/' in v) and not v.startswith('#'):
        return 'path'
    if re.fullmatch(r'-?\d+', v):
        return 'int'
    return 'str'


def parse_range(comment):
    """Read a range such as 0-100 or 0..100 from a field's comment."""
    m = re.search(r'(-?\d+)\s*(?:\.\.|[~]|[-–—]|до\b|to\b)\s*(-?\d+)', comment, re.IGNORECASE)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b > a and b - a <= 10000:
            return a, b
    return None


def bool_value(value):
    return value.strip().lower() in ('1', 'true', 'yes', 'on', 'enabled', 'да')


def format_bool_value(enabled, original):
    """Keep the original boolean vocabulary and capitalization when saving."""
    token = original.strip()
    lower = token.lower()
    pairs = {
        '0': ('0', '1'), '1': ('0', '1'),
        'false': ('false', 'true'), 'true': ('false', 'true'),
        'no': ('no', 'yes'), 'yes': ('no', 'yes'),
        'off': ('off', 'on'), 'on': ('off', 'on'),
        'disabled': ('disabled', 'enabled'), 'enabled': ('disabled', 'enabled'),
        'нет': ('нет', 'да'), 'да': ('нет', 'да'),
    }
    false_token, true_token = pairs.get(lower, ('false', 'true'))
    result = true_token if enabled else false_token
    if token.isupper() and any(ch.isalpha() for ch in token):
        return result.upper()
    if token.istitle():
        return result.title()
    return result


class IniEditor(ctk.CTk):
    def __init__(self, initial_file=None):
        super().__init__()
        self.title("INI Settings Editor")
        self.geometry("1360x850")
        self.minsize(1020, 650)

        self.initial_file = os.path.abspath(initial_file) if initial_file else None
        self.config_dir = (os.path.dirname(self.initial_file)
                           if self.initial_file else
                           os.path.dirname(os.path.abspath(__file__)))
        self.current_file = None
        self.current_lines = []
        self.kv_widgets = {}
        self.file_buttons = {}
        # path -> {'lines': [...], 'dirty': bool, 'encoding': str}
        self.files_cache = {}
        self.invalid_inputs = set()
        self._save_after_id = None
        self._status_after_id = None

        self._build_ui()
        self._load_files(self.config_dir)
        if self.initial_file and os.path.isfile(self.initial_file):
            self._open_file(self.initial_file)

    # -------------------------------------------------------- UI
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(self, width=290, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_rowconfigure(3, weight=1)
        sidebar.grid_propagate(False)

        ctk.CTkLabel(sidebar, text="⚙️  Настройки",
                     font=("Segoe UI", 22, "bold")).grid(
            row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        self.dir_lbl = ctk.CTkLabel(
            sidebar, text=self.config_dir, font=("Segoe UI", 12),
            text_color="gray", wraplength=250, justify="left")
        self.dir_lbl.grid(row=1, column=0, padx=20, pady=(0, 12), sticky="w")

        ctk.CTkButton(sidebar, text="📂  Открыть папку",
                      command=self._choose_dir, height=40,
                      font=("Segoe UI", 14)).grid(
            row=2, column=0, padx=16, pady=(0, 12), sticky="ew")

        self.file_list = ctk.CTkScrollableFrame(sidebar, fg_color="transparent")
        self.file_list.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")

        theme_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        theme_frame.grid(row=4, column=0, padx=18, pady=(0, 16), sticky="ew")
        ctk.CTkLabel(theme_frame, text="Тема:", font=("Segoe UI", 13)).pack(side="left")
        self.theme_switch = ctk.CTkSegmentedButton(
            theme_frame, values=["🌙 Тёмная", "☀️ Светлая"],
            command=self._set_theme, font=("Segoe UI", 12), height=34)
        self.theme_switch.set("🌙 Тёмная")
        self.theme_switch.pack(side="right", fill="x", expand=True, padx=(10, 0))

        main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        self.header = ctk.CTkLabel(
            main, text="Выберите файл слева", font=("Segoe UI", 24, "bold"))
        self.header.grid(row=0, column=0, padx=26, pady=(18, 8), sticky="w")

        self.scroll = ctk.CTkScrollableFrame(main, corner_radius=10)
        self.scroll.grid(row=1, column=0, padx=18, pady=(6, 8), sticky="nsew")
        self.scroll.grid_columnconfigure(0, weight=1)

        bottom = ctk.CTkFrame(main, fg_color="transparent", height=32)
        bottom.grid(row=2, column=0, padx=22, pady=(0, 12), sticky="ew")
        bottom.grid_columnconfigure(0, weight=1)
        # Status is intentionally blank until an edit/save/error occurs.
        self.status = ctk.CTkLabel(
            bottom, text="", font=("Segoe UI", 12, "bold"), anchor="w")
        self.status.grid(row=0, column=0, sticky="w")

    def _set_theme(self, value):
        ctk.set_appearance_mode("light" if "Свет" in value else "dark")

    # -------------------------------------------------------- file loading
    def _load_files(self, folder):
        self.config_dir = os.path.abspath(folder)
        self.dir_lbl.configure(text=self.config_dir)
        self.current_file = None
        self.current_lines = []
        self.files_cache.clear()
        self.invalid_inputs.clear()

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
                path = os.path.abspath(os.path.join(self.config_dir, fname))
                btn = ctk.CTkButton(
                    self.file_list, text=f"  📄  {fname}",
                    anchor="w", fg_color="transparent",
                    hover_color=("gray75", "gray28"),
                    text_color=("gray10", "gray90"),
                    height=38, corner_radius=6,
                    font=("Segoe UI", 13),
                    command=lambda p=path: self._open_file(p))
                btn.pack(fill="x", pady=2)
                self.file_buttons[path] = btn

        if not found:
            ctk.CTkLabel(self.file_list, text="Файлы .ini не найдены",
                         text_color="gray", font=("Segoe UI", 13)).pack(pady=20)

    def _choose_dir(self):
        if not self._validate_current_inputs():
            return
        if not self._save_all(show_error=True):
            return
        folder = filedialog.askdirectory(initialdir=self.config_dir)
        if folder:
            self._cancel_save_timer()
            self._load_files(folder)
            self._set_status("", "gray")

    def _validate_current_inputs(self):
        invalid_here = [item for item in self.invalid_inputs
                        if item[0] == self.current_file]
        if invalid_here:
            self._set_status("Введите целое число в числовом поле.", "#E5A100")
            messagebox.showwarning(
                "Некорректное значение",
                "В одном из числовых полей введено не целое число. "
                "Исправьте значение перед переключением файла или закрытием редактора.")
            return False
        return True

    # -------------------------------------------------------- open file
    def _open_file(self, path):
        path = os.path.abspath(path)
        if self.current_file and self.current_file != path:
            if not self._validate_current_inputs():
                return
            if not self._save_all(show_error=True):
                return

        if path not in self.files_cache:
            try:
                lines, encoding = read_ini_file(path)
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось открыть файл:\n{e}")
                return
            self.files_cache[path] = {
                'lines': lines,
                'dirty': False,
                'encoding': encoding,
            }

        self.current_file = path
        self.current_lines = self.files_cache[path]['lines']
        self.header.configure(text=f"📄  {os.path.basename(path)}")

        for p, button in self.file_buttons.items():
            active = (p == path)
            button.configure(
                fg_color="#1F6AA5" if active else "transparent",
                text_color=("white", "white") if active else ("gray10", "gray90"))

        self._render()
        self._refresh_status()

    # -------------------------------------------------------- render controls
    def _render(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.kv_widgets.clear()

        row = 0
        pending_comments = []
        for idx, raw_line in enumerate(self.current_lines):
            line = raw_line.rstrip('\n').rstrip('\r')
            stripped = line.strip()

            if not stripped:
                pending_comments = []
                continue
            if stripped.startswith(';') or (stripped.startswith('#') and '=' not in stripped):
                pending_comments.append(stripped.lstrip(';#').strip())
                continue
            if stripped.startswith('[') and stripped.endswith(']'):
                self._add_section(row, stripped[1:-1], pending_comments)
                pending_comments = []
                row += 1
                continue
            if '=' in stripped:
                key, _, value = line.partition('=')
                self._add_field(row, idx, key.strip(), value.strip(),
                                '\n'.join(pending_comments))
                pending_comments = []
                row += 1
                continue
            self._add_raw_line(row, idx, line)
            pending_comments = []
            row += 1

    def _add_section(self, row, name, comments):
        frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", padx=0, pady=(12, 5))
        frame.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(top, text="▌", text_color=("#1F6AA5", "#3B8ED0"),
                     font=("Segoe UI", 22, "bold")).pack(side="left", padx=(5, 6))
        ctk.CTkLabel(top, text=name, font=("Segoe UI", 18, "bold"),
                     text_color=("#1F6AA5", "#5AA9E6")).pack(side="left")
        if comments:
            ctk.CTkLabel(
                frame, text='\n'.join(comments), font=COMMENT_FONT,
                text_color="gray", justify="left", anchor="w",
                wraplength=1000).grid(row=1, column=0, padx=(20, 5),
                                      pady=(2, 0), sticky="w")

    def _add_field(self, row, line_idx, key, value, comment):
        ftype = detect_type(key, value, comment)
        card = ctk.CTkFrame(self.scroll, corner_radius=9,
                            fg_color=("gray90", "gray16"))
        card.grid(row=row, column=0, sticky="ew", padx=4, pady=3)
        card.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=12, pady=6)
        inner.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(inner, text=key, font=KEY_FONT,
                     anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 18))

        var, widget, extra = self._make_widget(inner, ftype, value, comment)
        widget.grid(row=0, column=1, sticky="ew")
        if comment:
            ctk.CTkLabel(
                card, text=comment, font=COMMENT_FONT,
                text_color="gray", justify="left", anchor="w",
                wraplength=1000).grid(row=1, column=0, padx=15,
                                      pady=(0, 6), sticky="w")

        self.kv_widgets[line_idx] = {
            'key': key, 'var': var, 'type': ftype, 'original_value': value,
            **extra,
        }
        var.trace_add('write', lambda *_args, i=line_idx: self._on_field_change(i))

    def _add_raw_line(self, row, line_idx, line):
        var = ctk.StringVar(value=line)
        card = ctk.CTkFrame(self.scroll, corner_radius=8,
                            fg_color=("gray88", "gray17"))
        card.grid(row=row, column=0, sticky="ew", padx=4, pady=2)
        card.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(card, textvariable=var, font=("Consolas", 14),
                     height=ENTRY_HEIGHT).grid(
            row=0, column=0, padx=9, pady=5, sticky="ew")
        self.kv_widgets[line_idx] = {
            'key': None, 'var': var, 'type': 'raw', 'original_value': line,
        }
        var.trace_add('write', lambda *_args, i=line_idx: self._on_field_change(i))

    def _make_widget(self, parent, ftype, value, comment):
        extra = {}
        if ftype == 'bool':
            var = ctk.StringVar(value="TRUE" if bool_value(value) else "FALSE")
            widget = ctk.CTkSegmentedButton(
                parent, values=["FALSE", "TRUE"], variable=var,
                font=("Segoe UI", 14, "bold"), height=ENTRY_HEIGHT,
                selected_color="#1F6AA5", selected_hover_color="#185783")
            extra['bool_style'] = value.strip()
            return var, widget, extra

        if ftype == 'int':
            try:
                current = int(value.strip())
            except (TypeError, ValueError):
                current = 0
            bounds = parse_range(comment)
            if bounds is None and 0 <= current <= 100:
                bounds = (0, 100)

            var = ctk.StringVar(value=str(current))
            if bounds:
                low, high = bounds
                start = max(low, min(high, current))
                slider_var = ctk.DoubleVar(value=float(start))
                container = ctk.CTkFrame(parent, fg_color="transparent")
                container.grid_columnconfigure(0, weight=1)
                container.grid_columnconfigure(1, minsize=105)

                def slide_changed(slider_value, target=var):
                    try:
                        target.set(str(int(round(float(slider_value)))))
                    except (TypeError, ValueError):
                        pass

                steps = max(1, min(1000, high - low))
                slider = ctk.CTkSlider(
                    container, from_=low, to=high, number_of_steps=steps,
                    variable=slider_var, command=slide_changed,
                    height=20, button_length=18)
                slider.grid(row=0, column=0, sticky="ew", padx=(0, 14))
                entry = ctk.CTkEntry(
                    container, textvariable=var, font=FIELD_FONT,
                    height=ENTRY_HEIGHT, width=105, justify="center")
                entry.grid(row=0, column=1, sticky="ew")

                def sync_slider(*_args, sv=slider_var, text_var=var,
                                min_value=low, max_value=high):
                    try:
                        number = int(text_var.get().strip())
                    except (TypeError, ValueError):
                        return
                    if min_value <= number <= max_value:
                        sv.set(number)

                var.trace_add('write', sync_slider)
                extra['int_range'] = bounds
                return var, container, extra

            widget = ctk.CTkEntry(parent, textvariable=var,
                                  font=FIELD_FONT, height=ENTRY_HEIGHT)
            return var, widget, extra

        if ftype == 'path':
            var = ctk.StringVar(value=value)
            container = ctk.CTkFrame(parent, fg_color="transparent")
            container.grid_columnconfigure(0, weight=1)
            ctk.CTkEntry(container, textvariable=var, font=FIELD_FONT,
                         height=ENTRY_HEIGHT).grid(
                row=0, column=0, sticky="ew")
            ctk.CTkButton(
                container, text="📂", width=44, height=ENTRY_HEIGHT,
                command=lambda v=var: self._browse_path(v)).grid(
                row=0, column=1, padx=(7, 0))
            return var, container, extra

        if ftype == 'color':
            var = ctk.StringVar(value=value)
            container = ctk.CTkFrame(parent, fg_color="transparent")
            container.grid_columnconfigure(1, weight=1)
            swatch = ctk.CTkFrame(container, width=34, height=34, corner_radius=6,
                                  fg_color=value)
            swatch.grid(row=0, column=0, padx=(0, 9))
            swatch.grid_propagate(False)
            ctk.CTkEntry(container, textvariable=var, font=FIELD_FONT,
                         height=ENTRY_HEIGHT).grid(
                row=0, column=1, sticky="ew")
            var.trace_add('write',
                          lambda *_args, s=swatch, v=var: self._update_swatch(s, v.get()))
            return var, container, extra

        var = ctk.StringVar(value=value)
        widget = ctk.CTkEntry(parent, textvariable=var,
                              font=FIELD_FONT, height=ENTRY_HEIGHT)
        return var, widget, extra

    def _update_swatch(self, swatch, value):
        try:
            swatch.configure(fg_color=value)
        except Exception:
            pass

    # -------------------------------------------------------- live update + autosave
    def _on_field_change(self, idx):
        info = self.kv_widgets.get(idx)
        if not info or not self.current_file:
            return
        data = self.files_cache.get(self.current_file)
        if not data or idx >= len(data['lines']):
            return

        raw = data['lines'][idx]
        eol = get_line_ending(raw)
        content = raw[:-len(eol)] if eol else raw
        field_type = info['type']
        variable = info['var']
        invalid_key = (self.current_file, idx)
        was_invalid = invalid_key in self.invalid_inputs

        try:
            if field_type == 'raw':
                new_line = str(variable.get()) + eol
            else:
                raw_value = str(variable.get())
                if field_type == 'bool':
                    enabled = raw_value.upper() == 'TRUE'
                    value_to_write = format_bool_value(enabled, info['bool_style'])
                elif field_type == 'int':
                    try:
                        value_to_write = str(int(raw_value.strip()))
                    except (TypeError, ValueError):
                        self.invalid_inputs.add(invalid_key)
                        self._set_status("Введите целое число.", "#E5A100")
                        return
                    self.invalid_inputs.discard(invalid_key)
                else:
                    value_to_write = raw_value

                match = re.match(r'^(\s*[^=]*?=\s*)(.*?)(\s*)$', content)
                if match:
                    new_line = match.group(1) + value_to_write + match.group(3) + eol
                else:
                    new_line = f"{info['key']}={value_to_write}{eol}"
        except Exception as exc:
            self._set_status(f"Ошибка обработки значения: {exc}", "#E05D5D")
            return

        if data['lines'][idx] != new_line:
            data['lines'][idx] = new_line
            data['dirty'] = True
            self._update_file_button_label(self.current_file)
            self._set_status("Автосохранение…", "#E5A100")
            self._schedule_autosave()
        elif was_invalid and not self.invalid_inputs:
            if any(item.get('dirty') for item in self.files_cache.values()):
                self._set_status("Автосохранение…", "#E5A100")
                if self._save_after_id is None:
                    self._schedule_autosave()
            else:
                self._set_status("", "gray")

    def _schedule_autosave(self):
        self._cancel_save_timer()
        self._save_after_id = self.after(AUTOSAVE_DELAY_MS, self._autosave_pending)

    def _cancel_save_timer(self):
        if self._save_after_id is not None:
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
            self._save_after_id = None

    def _autosave_pending(self):
        self._save_after_id = None
        success = self._save_all(show_error=False)
        if self.invalid_inputs:
            self._set_status("Исправьте некорректное числовое значение.", "#E5A100")
        elif success:
            # _save_all already displays a short confirmation when it wrote something.
            pass

    # -------------------------------------------------------- path picker
    def _browse_path(self, var):
        value = var.get().strip()
        base = os.path.basename(value.replace('\\', '/'))
        is_file = '.' in base and base.split('.')[-1].lower() in (
            'log', 'ini', 'txt', 'lua', 'exe', 'dll', 'cfg', 'dat')
        initial = self.config_dir
        if value:
            candidate = value if os.path.isabs(value) else os.path.join(self.config_dir, value)
            if os.path.exists(candidate):
                initial = candidate if os.path.isdir(candidate) else os.path.dirname(candidate)
        if is_file:
            picked = filedialog.askopenfilename(initialdir=initial, title="Выберите файл")
        else:
            picked = filedialog.askdirectory(initialdir=initial, title="Выберите папку")
        if not picked:
            return

        relative = self._make_relative(picked)
        if not is_file and (value.endswith('\\') or value.endswith('/')) and \
                not relative.endswith(('\\', '/')):
            relative += '\\'
        var.set(relative)

    def _make_relative(self, path):
        try:
            relative = os.path.relpath(path, self.config_dir)
            if not relative.startswith('..'):
                return relative
        except Exception:
            pass
        return path

    # -------------------------------------------------------- status & labels
    def _set_status(self, text, color="gray", clear_after_ms=None):
        if self._status_after_id is not None:
            try:
                self.after_cancel(self._status_after_id)
            except Exception:
                pass
            self._status_after_id = None
        self.status.configure(text=text, text_color=color)
        if clear_after_ms:
            self._status_after_id = self.after(clear_after_ms, self._clear_status)

    def _clear_status(self):
        self._status_after_id = None
        if not any(data.get('dirty') for data in self.files_cache.values()):
            if not self.invalid_inputs:
                self.status.configure(text="")

    def _refresh_status(self):
        dirty_paths = [path for path, data in self.files_cache.items() if data.get('dirty')]
        if dirty_paths:
            self._set_status("Автосохранение…", "#E5A100")

    def _update_file_button_label(self, path):
        button = self.file_buttons.get(path)
        if not button:
            return
        name = os.path.basename(path)
        dirty = self.files_cache.get(path, {}).get('dirty')
        button.configure(text=f"  {'●' if dirty else '📄'}  {name}")

    # -------------------------------------------------------- save to disk
    def _save_all(self, show_error=False):
        """Write only changed files. Returns False if any write fails."""
        self._cancel_save_timer()
        saved, failed = [], []
        for path, data in self.files_cache.items():
            if not data.get('dirty'):
                continue
            temp_path = None
            try:
                payload = ''.join(data['lines']).encode(data['encoding'])
                folder = os.path.dirname(path) or '.'
                prefix = '.' + os.path.basename(path) + '.'
                fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix='.tmp', dir=folder)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_path, path)
                temp_path = None
                data['dirty'] = False
                saved.append(path)
                self._update_file_button_label(path)
            except Exception as exc:
                failed.append((path, exc))
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

        if failed:
            details = '\n'.join(f"{os.path.basename(path)}: {error}" for path, error in failed)
            self._set_status("Ошибка автосохранения. Файл остался несохранённым.", "#E05D5D")
            if show_error:
                messagebox.showerror("Ошибка сохранения", details)
            return False

        if saved:
            self._set_status("Изменения сохранены", "#7FBA00", clear_after_ms=1700)
        return True

    # -------------------------------------------------------- graceful exit
    def on_close(self):
        if not self._validate_current_inputs():
            return
        if self._save_all(show_error=True):
            if self._status_after_id is not None:
                try:
                    self.after_cancel(self._status_after_id)
                except Exception:
                    pass
            self.destroy()


if __name__ == "__main__":
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    app = IniEditor(initial_file=initial_file)
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
