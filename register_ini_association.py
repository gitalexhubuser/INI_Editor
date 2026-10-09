"""Register/unregister the INI Settings Editor for .ini files on Windows.

Run with the same Python installation that has customtkinter installed:
    python register_ini_association.py install
    python register_ini_association.py uninstall
"""
import argparse
import json
import os
import sys
import winreg

PROG_ID = 'INISettingsEditor.File'
APP_NAME = 'INI Settings Editor'
CLASSES = r'Software\Classes'
CAPABILITIES = r'Software\INISettingsEditor\Capabilities'
REGISTERED_APPS = r'Software\RegisteredApplications'
BACKUP_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 'INISettingsEditor')
BACKUP_FILE = os.path.join(BACKUP_DIR, 'association_backup.json')


def pythonw_path():
    current = os.path.abspath(sys.executable)
    folder, name = os.path.split(current)
    lower = name.lower()
    candidates = []
    if lower.startswith('python') and lower.endswith('.exe') and not lower.endswith('w.exe'):
        candidates.append(os.path.join(folder, 'pythonw.exe'))
        candidates.append(os.path.join(folder, name[:-4] + 'w.exe'))
    candidates.append(current)
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return current


def query_default(key_path):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            return winreg.QueryValueEx(key, '')
    except FileNotFoundError:
        return None


def set_default(key_path, value):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, value)


def delete_tree_if_exists(root, path):
    try:
        winreg.DeleteKey(root, path)
    except OSError:
        pass


def find_built_exe():
    """Find the compiled application if PyInstaller has already built it."""
    base = os.path.abspath(os.path.dirname(__file__))
    candidates = (
        os.path.join(base, 'dist', 'INI Settings Editor', 'INI Settings Editor.exe'),
        os.path.join(base, 'INI Settings Editor.exe'),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def install():
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ini_editor.py'))
    if not os.path.isfile(script):
        raise FileNotFoundError('Рядом с этим установщиком не найден ini_editor.py')

    ext_key = CLASSES + r'\.ini'
    old_default = query_default(ext_key)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(BACKUP_FILE):
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump({'old_default': old_default}, f, ensure_ascii=False, indent=2)

    built_exe = find_built_exe()
    if built_exe:
        runner = built_exe
        command = f'"{runner}" "%1"'
        print('Найден собранный EXE; регистрирую именно его.')
    else:
        runner = pythonw_path()
        command = f'"{runner}" "{script}" "%1"'
        print('Собранный EXE не найден; регистрирую запуск через Python.')

    set_default(ext_key, PROG_ID)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, ext_key + r'\OpenWithProgids') as key:
        # REG_NONE with empty data is the conventional OpenWithProgids marker.
        winreg.SetValueEx(key, PROG_ID, 0, winreg.REG_NONE, b'')

    prog = CLASSES + '\\' + PROG_ID
    set_default(prog, 'INI settings file')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prog + r'\shell\open\command') as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, command)
    set_default(prog + r'\DefaultIcon', f'"{runner}",0')

    # Also advertise the handler through the classic Open With application list.
    app_key = CLASSES + r'\Applications\INI Settings Editor.exe'
    set_default(app_key + r'\DefaultIcon', f'"{runner}",0')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key + r'\shell\open\command') as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, command)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, app_key + r'\SupportedTypes') as key:
        winreg.SetValueEx(key, '.ini', 0, winreg.REG_SZ, '')

    # Make the handler discoverable in Windows' registered-applications list.
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CAPABILITIES) as key:
        winreg.SetValueEx(key, 'ApplicationName', 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, 'ApplicationDescription', 0, winreg.REG_SZ,
                          'Открывает INI-файлы в графическом редакторе настроек.')
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CAPABILITIES + r'\FileAssociations') as key:
        winreg.SetValueEx(key, '.ini', 0, winreg.REG_SZ, PROG_ID)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTERED_APPS) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, CAPABILITIES)

    print('Регистрация выполнена для текущего пользователя Windows.')
    print('Обработчик запускает:')
    print(command)
    print('\nЕсли двойной щелчок всё ещё открывает Блокнот:')
    print('Параметры Windows → Приложения → Приложения по умолчанию →')
    print('выберите приложение по типу файла → .ini → INI Settings Editor.')
    print('Если редактор отсутствует в списке, перезапустите Параметры Windows и повторите выбор.')


def uninstall():
    ext_key = CLASSES + r'\.ini'
    current = query_default(ext_key)
    if current and current[0] == PROG_ID:
        backup = None
        if os.path.exists(BACKUP_FILE):
            try:
                with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                    backup = json.load(f).get('old_default')
            except Exception:
                backup = None
        if backup:
            set_default(ext_key, backup[0])
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ext_key, 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, '')
            except OSError:
                pass

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ext_key + r'\OpenWithProgids', 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, PROG_ID)
    except OSError:
        pass

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTERED_APPS, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass

    delete_tree_if_exists(winreg.HKEY_CURRENT_USER, CAPABILITIES + r'\FileAssociations')
    delete_tree_if_exists(winreg.HKEY_CURRENT_USER, CAPABILITIES)
    # Remove the explicit Open With registration created by this installer.
    app_key = CLASSES + r'\Applications\INI Settings Editor.exe'
    for path in (app_key + r'\shell\open\command',
                 app_key + r'\shell\open',
                 app_key + r'\shell',
                 app_key + r'\SupportedTypes',
                 app_key + r'\DefaultIcon',
                 app_key,
                 CLASSES + '\\' + PROG_ID + r'\shell\open\command',
                 CLASSES + '\\' + PROG_ID + r'\shell\open',
                 CLASSES + '\\' + PROG_ID + r'\shell',
                 CLASSES + '\\' + PROG_ID + r'\DefaultIcon',
                 CLASSES + '\\' + PROG_ID):
        delete_tree_if_exists(winreg.HKEY_CURRENT_USER, path)
    if os.path.exists(BACKUP_FILE):
        try:
            os.remove(BACKUP_FILE)
        except OSError:
            pass
    print('Регистрация редактора удалена. Если Windows сохраняет выбор в «Приложениях по умолчанию», верните там прежнее приложение для .ini.')


def main():
    if os.name != 'nt':
        raise SystemExit('Этот скрипт предназначен для Windows.')
    parser = argparse.ArgumentParser(description='Регистрация INI Settings Editor в Windows')
    parser.add_argument('action', choices=('install', 'uninstall'), nargs='?', default='install')
    args = parser.parse_args()
    if args.action == 'install':
        install()
    else:
        uninstall()


if __name__ == '__main__':
    main()
