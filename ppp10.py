import sys
import os
import ctypes
import traceback
import tempfile
import keyboard
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QWidget, QFileDialog,
    QSlider, QHBoxLayout, QVBoxLayout, QFrame, QDesktopWidget, QSystemTrayIcon, QMenu, QAction, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QPoint, QRect, QObject, pyqtSignal, pyqtSlot, QSize, QTimer, QSettings, QEvent
from PyQt5.QtGui import QPixmap, QTransform, QCursor, QClipboard, QImage, QPainter, QPen, QColor, QFont, QFontDatabase, QFontMetrics, QIcon
import win32gui
import win32con
import time
import ctypes
import pywintypes
import winreg


# Константы Windows API
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080

# Константы для изменения размера
EDGE_NONE = 0
EDGE_LEFT = 1
EDGE_TOP = 2
EDGE_RIGHT = 3
EDGE_BOTTOM = 4
EDGE_TOPLEFT = 5
EDGE_TOPRIGHT = 6
EDGE_BOTTOMLEFT = 7
EDGE_BOTTOMRIGHT = 8
EDGE_MARGIN = 10  # Зона для захвата края в пикселях

# Константы для работы с профилями
REGISTRY_BASE_KEY = "Software\\PeekPickPic"
DEFAULT_PROFILE_NAME = "Основной профиль"

# Глобальные переменные для профилей
current_profile = None
profiles_list = []

# Глобальная переменная app, чтобы управлять выходом изнутри хоткея
app = None

overlay_bar = None  # будет хранить объект EditModeOverlay

is_switching_mode = False

windows_selection = []  # Список выделенных окон

#Класс для отображения Edit mode оверлея
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtWidgets import QWidget
from PyQt5.QtGui import QPainter, QFont, QColor, QFontDatabase

def load_profiles_list():
    """Загружает список профилей из реестра"""
    global profiles_list
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_BASE_KEY)
        profiles_key_path = f"{REGISTRY_BASE_KEY}\\Profiles"
        
        try:
            profiles_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, profiles_key_path)
            profiles_list = []
            i = 0
            
            # Перебираем все подключи (профили)
            while True:
                try:
                    profile_name = winreg.EnumKey(profiles_key, i)
                    profiles_list.append(profile_name)
                    i += 1
                except WindowsError:
                    break
            
            winreg.CloseKey(profiles_key)
        except FileNotFoundError:
            # Если ключа с профилями нет, создаем его с одним профилем по умолчанию
            profiles_list = [DEFAULT_PROFILE_NAME]
            create_profile(DEFAULT_PROFILE_NAME)
        
        # Если список пуст, добавляем профиль по умолчанию
        if not profiles_list:
            profiles_list = [DEFAULT_PROFILE_NAME]
            create_profile(DEFAULT_PROFILE_NAME)
            
        winreg.CloseKey(key)
    except FileNotFoundError:
        # Если базового ключа нет, создаем его и профиль по умолчанию
        profiles_list = [DEFAULT_PROFILE_NAME]
        create_profile(DEFAULT_PROFILE_NAME)
    
    print(f"Загружен список профилей: {profiles_list}")
    return profiles_list

def get_current_profile():
    """Получает имя текущего профиля из реестра"""
    global current_profile
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_BASE_KEY)
        current_profile, _ = winreg.QueryValueEx(key, "CurrentProfile")
        winreg.CloseKey(key)
    except (FileNotFoundError, WindowsError):
        # Если ключа или значения нет, используем профиль по умолчанию
        current_profile = DEFAULT_PROFILE_NAME
        # Сохраняем выбор в реестр
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_BASE_KEY)
        winreg.SetValueEx(key, "CurrentProfile", 0, winreg.REG_SZ, current_profile)
        winreg.CloseKey(key)
    
    # Если текущего профиля нет в списке, создаем его
    if current_profile not in profiles_list:
        create_profile(current_profile)
    
    print(f"Текущий профиль: {current_profile}")
    return current_profile

def set_current_profile(profile_name):
    """Устанавливает текущий профиль"""
    global current_profile
    
    # Если профиля нет в списке, создаем его
    if profile_name not in profiles_list:
        create_profile(profile_name)
    
    # Сохраняем выбор в реестр
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_BASE_KEY)
    winreg.SetValueEx(key, "CurrentProfile", 0, winreg.REG_SZ, profile_name)
    winreg.CloseKey(key)
    
    current_profile = profile_name
    print(f"Установлен текущий профиль: {profile_name}")

# Диалоговые функции для создания, переименования и удаления профилей
def create_profile_dialog():
    """Открывает диалог для создания нового профиля"""
    try:
        name, ok = QInputDialog.getText(None, 'Новый профиль', 
                                       'Введите имя нового профиля:')
        if ok and name:
            # Проверяем, существует ли профиль с таким именем
            if name in profiles_list:
                QMessageBox.warning(None, 'Ошибка', 
                                   f'Профиль с именем "{name}" уже существует!')
                return
            
            # Сохраняем текущее состояние
            save_windows_state()
            
            # Создаем новый профиль
            create_profile(name)
            
            # Добавляем профиль в список
            profiles_list.append(name)
            
            # Переключаемся на новый профиль
            set_current_profile(name)
            
            # Загружаем (пустое) состояние из нового профиля
            load_windows_state()
            
            # Переходим в режим рабочего стола
            toggle_all_windows_mode(True)
            
            # Обновляем меню
            update_profiles_menu()
            
            print(f"Создан новый профиль: {name}")
    except Exception as e:
        print(f"Ошибка при создании нового профиля: {e}")
        traceback.print_exc()


def create_profile(profile_name):
    """Создает новый профиль"""
    global profiles_list
    
    if profile_name in profiles_list:
        print(f"Профиль {profile_name} уже существует")
        return
    
    # Создаем ключ профиля
    profile_key_path = f"{REGISTRY_BASE_KEY}\\Profiles\\{profile_name}"
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, profile_key_path)
    winreg.CloseKey(key)
    
    # Добавляем профиль в список
    profiles_list.append(profile_name)
    print(f"Создан новый профиль: {profile_name}")

def rename_profile(old_name, new_name):
    """Переименовывает профиль"""
    global profiles_list, current_profile
    
    if old_name not in profiles_list:
        print(f"Профиль {old_name} не существует")
        return False
    
    if new_name in profiles_list:
        print(f"Профиль {new_name} уже существует")
        return False
    
    try:
        # Создаем новый ключ с тем же содержимым
        old_key_path = f"{REGISTRY_BASE_KEY}\\Profiles\\{old_name}"
        new_key_path = f"{REGISTRY_BASE_KEY}\\Profiles\\{new_name}"
        
        if copy_registry_key(old_key_path, new_key_path):
            # Удаляем старый ключ
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, old_key_path)
            
            # Обновляем список профилей
            index = profiles_list.index(old_name)
            profiles_list[index] = new_name
            
            # Если это был текущий профиль, обновляем ссылку
            if current_profile == old_name:
                current_profile = new_name
                # Обновляем значение в реестре
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REGISTRY_BASE_KEY)
                winreg.SetValueEx(key, "CurrentProfile", 0, winreg.REG_SZ, new_name)
                winreg.CloseKey(key)
            
            print(f"Профиль {old_name} переименован в {new_name}")
            return True
        else:
            print(f"Не удалось скопировать ключ профиля {old_name}")
            return False
    except Exception as e:
        print(f"Ошибка при переименовании профиля: {e}")
        traceback.print_exc()
        return False

def delete_profile_dialog(profile_name):
    """Открывает диалог для удаления профиля"""
    try:
        reply = QMessageBox.question(None, 'Удаление профиля', 
                                    f'Вы уверены, что хотите удалить профиль "{profile_name}"?',
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Удаляем профиль
            if delete_profile(profile_name):
                # Обновляем меню
                update_profiles_menu()
    except Exception as e:
        print(f"Ошибка при удалении профиля: {e}")
        traceback.print_exc()


def delete_profile(profile_name):
    """Удаляет профиль"""
    global profiles_list, current_profile
    
    if profile_name not in profiles_list:
        print(f"Профиль {profile_name} не существует")
        return False
    
    # Нельзя удалить единственный профиль
    if len(profiles_list) <= 1:
        print("Нельзя удалить единственный профиль")
        return False
    
    # Нельзя удалить текущий профиль
    if profile_name == current_profile:
        # Переключаемся на другой профиль
        next_profile = next((p for p in profiles_list if p != profile_name), None)
        if next_profile:
            set_current_profile(next_profile)
        else:
            print("Не удалось найти другой профиль для переключения")
            return False
    
    try:
        # Удаляем ключ профиля
        profile_key_path = f"{REGISTRY_BASE_KEY}\\Profiles\\{profile_name}"
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, profile_key_path)
        
        # Удаляем профиль из списка
        profiles_list.remove(profile_name)
        print(f"Профиль {profile_name} удален")
        return True
    except Exception as e:
        print(f"Ошибка при удалении профиля: {e}")
        return False
    
def copy_registry_key(src_key_path, dst_key_path):
    """Копирует ключ реестра со всеми значениями и подключами"""
    try:
        src_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, src_key_path)
        dst_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, dst_key_path)
        
        # Копируем значения
        i = 0
        while True:
            try:
                name, value, type_id = winreg.EnumValue(src_key, i)
                winreg.SetValueEx(dst_key, name, 0, type_id, value)
                i += 1
            except WindowsError:
                break
        
        # Копируем подключи
        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(src_key, i)
                copy_registry_key(f"{src_key_path}\\{subkey_name}", f"{dst_key_path}\\{subkey_name}")
                i += 1
            except WindowsError:
                break
        
        winreg.CloseKey(src_key)
        winreg.CloseKey(dst_key)
        return True
    except Exception as e:
        print(f"Ошибка при копировании ключа реестра: {e}")
        return False
    
def delete_registry_key(key_path):
    """Рекурсивно удаляет ключ реестра с подключами"""
    try:
        # Открываем ключ
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, 
                            winreg.KEY_READ | winreg.KEY_ENUMERATE_SUB_KEYS)
        
        # Перебираем и удаляем все подключи
        while True:
            try:
                subkey = winreg.EnumKey(key, 0)  # Всегда берем первый ключ
                delete_registry_key(f"{key_path}\\{subkey}")
            except WindowsError:
                break
        
        winreg.CloseKey(key)
        
        # Удаляем сам ключ
        parent_path = "\\".join(key_path.split("\\")[:-1])
        subkey_name = key_path.split("\\")[-1]
        
        parent_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, parent_path, 0, 
                                   winreg.KEY_WRITE)
        winreg.DeleteKey(parent_key, subkey_name)
        winreg.CloseKey(parent_key)
    except Exception as e:
        print(f"Ошибка при удалении ключа реестра: {e}")


def alt_tab_workaround(hwnd):
    try:
        # Временно меняем состояние окна на topmost и обратно, чтобы убедить Windows в необходимости активировать окно
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)

        # И снова явно делаем окно foreground
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"Альтернативный способ активации окна тоже не сработал: {e}")


def activate_our_app_window():
    ASFW_ANY = -1

    if windows:
        hwnd = int(windows[-1].winId())

        ctypes.windll.user32.AllowSetForegroundWindow(ASFW_ANY)

        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        try:
            win32gui.SetForegroundWindow(hwnd)
        except pywintypes.error as e:
            print(f"Ошибка SetForegroundWindow: {e}")
            # Используем дополнительный надежный способ активации окна
            force_activate_window(hwnd)

def force_activate_window(hwnd):
    try:
        # Делаем окно временно самым верхним, чтобы система позволила ему выйти вперёд
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        time.sleep(0.05)  # небольшая задержка
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        time.sleep(0.05)  # небольшая задержка
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"Дополнительный метод активации тоже не сработал: {e}")

class EditModeOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)  # Окно не в панели задач
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)  # Скрывает окно для пользователя
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)  # Показывать без активации
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)  # Прозрачность для фона

        self.bg_color = QColor("#1C1A99")
        self.text_color = QColor("#F29BBE")

        # Зададим текст, который будем гонять
        self.marquee_text = " edit mode  / " * 30  # повторим много раз
        self.offset = 0  # смещение текста слева-направо
        self.speed = 2    # пикселей за "тик" таймера

        # Настраиваем высоту полоски (примерно как «высота панели задач»)
        self.bar_height = 40

        # Таймер для анимации
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_marquee)
        self.timer.start(24)  # обновление ~20 кадров/сек

        # Загрузим шрифт Source Sans Variable Black
        font_db = QFontDatabase()
        self.font = font_db.addApplicationFont("C:/Users/Коди/Desktop/SourceSans3-VariableFont_wght.ttf")  # Путь к шрифту
        if self.font == -1:
            print("Не удалось загрузить шрифт Source Sans Variable Black")

    def show_overlay(self):
        # Устанавливаем геометрию (во всю ширину экрана)
        desktop = self.screen().geometry()
        self.setGeometry(0, 0, desktop.width(), self.bar_height)

        self.show()

    def update_marquee(self):
        # Смещаем текст влево
        self.offset -= self.speed
        # Если уехали слишком далеко влево, возвращаемся
        if abs(self.offset) > self.width():
            self.offset = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Заливаем фон
        painter.fillRect(self.rect(), self.bg_color)
        painter.setPen(self.text_color)

        # Устанавливаем шрифт для текста
        font = QFont("SourceSans3-VariableFont_wght", 16)  # Выбираем шрифт и размер
        painter.setFont(font)

        # Создаём объект QFontMetrics для расчёта длины строки
        font_metrics = QFontMetrics(font)
        text_width = font_metrics.horizontalAdvance(self.marquee_text)

        # Рисуем текст со смещением
        text_x = self.offset
        text_y = int(self.bar_height * 0.7)  # Центрируем по высоте полоски

        painter.drawText(text_x, text_y, self.marquee_text)

        # Рисуем второй повторяющийся текст для создания бесшовного эффекта
        painter.drawText(text_x + text_width, text_y, self.marquee_text)

        painter.end()

    def mousePressEvent(self, event):
        """Позволяет кликать по всему, что находится под плашкой"""
        event.ignore()  # Игнорируем события мыши для самого окна, чтобы они "проходили" вниз

# Класс для обработки сигналов
class HotkeySignals(QObject):
    create_window_signal = pyqtSignal()
    toggle_all_windows_mode_signal = pyqtSignal(bool)
    paste_image_signal = pyqtSignal()  # Новый сигнал для вставки из буфера обмена
    delete_active_window_signal = pyqtSignal()  # Новый сигнал для удаления активного окна

hotkey_signals = HotkeySignals()
global_desktop_mode = False
windows = []
wallpaper_windows = []
active_window = None  # Переменная для отслеживания активного окна

def find_desktop_window():
    """Находит окно рабочего стола для правильного отображения обоев"""
    try:
        progman = win32gui.FindWindow("Progman", None)
        if not progman:
            return None
        
        # Отправляем сообщение и ждём
        win32gui.SendMessageTimeout(
            progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000
        )
        time.sleep(0.05)  # Можно увеличить задержку
        
        workerw_list = []
        
        def enum_windows_proc(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                class_name = win32gui.GetClassName(hwnd)
                if class_name == "WorkerW":
                    results.append(hwnd)
            return True
        
        win32gui.EnumWindows(enum_windows_proc, workerw_list)
        
        # ищем WorkerW, внутри которого SHELLDLL_DefView
        for workerw in workerw_list:
            defview = win32gui.FindWindowEx(workerw, 0, "SHELLDLL_DefView", None)
            if defview:
                # 1) Попробуем вернуть любой другой WorkerW (кроме этого)
                for w2 in workerw_list:
                    if w2 != workerw:
                        return w2
                
                # 2) Если не нашли другого – вернём сам workerw (с DefView)
                return workerw
        
        # Если нигде не обнаружили 'SHELLDLL_DefView' – возвращаем Progman
        return progman
    except Exception as e:
        print(f"Ошибка при поиске окна рабочего стола: {e}")
        traceback.print_exc()
        return None

def check_active_window():
    global global_desktop_mode, is_switching_mode

    if is_switching_mode:
        return

    try:
        active_hwnd = win32gui.GetForegroundWindow()
        our_hwnds = [int(window.winId()) for window in windows]
        if overlay_bar:
            our_hwnds.append(int(overlay_bar.winId()))

        try:
            class_name = win32gui.GetClassName(active_hwnd)
        except pywintypes.error:
            class_name = ""

        if active_hwnd not in our_hwnds and class_name not in ("WorkerW", "Progman"):
            if not global_desktop_mode:
                print(f"Активное окно не наше ({class_name}), переключаемся в desktop mode")
                hotkey_signals.toggle_all_windows_mode_signal.emit(True)

    except Exception as e:
        print(f"Ошибка в check_active_window: {e}")
        traceback.print_exc()

def save_windows_state():
    """Сохраняет состояние всех окон в реестр для текущего профиля"""
    global windows, current_profile
    
    if not current_profile:
        print("Нет активного профиля для сохранения")
        return
    
    try:
        # Открываем/создаем ключ текущего профиля
        profile_key_path = f"{REGISTRY_BASE_KEY}\\Profiles\\{current_profile}"
        profile_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, profile_key_path)
        
        # Устанавливаем количество окон
        winreg.SetValueEx(profile_key, "WindowsCount", 0, winreg.REG_DWORD, len(windows))
        
        # Сохраняем состояние каждого окна
        for i, window in enumerate(windows):
            window_key_path = f"{profile_key_path}\\Window{i}"
            window_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, window_key_path)
            
            # Сохраняем путь к изображению
            winreg.SetValueEx(window_key, "ImagePath", 0, winreg.REG_SZ, window.image_path)
            
            # Сохраняем позицию и размер
            winreg.SetValueEx(window_key, "X", 0, winreg.REG_DWORD, window.x())
            winreg.SetValueEx(window_key, "Y", 0, winreg.REG_DWORD, window.y())
            winreg.SetValueEx(window_key, "Width", 0, winreg.REG_DWORD, window.width())
            winreg.SetValueEx(window_key, "Height", 0, winreg.REG_DWORD, window.height())
            
            # Сохраняем информацию о z-index (порядке окон)
            winreg.SetValueEx(window_key, "ZIndex", 0, winreg.REG_DWORD, i)
            
            winreg.CloseKey(window_key)
        
        winreg.CloseKey(profile_key)
        print(f"Сохранено {len(windows)} окон в профиле '{current_profile}'")
    except Exception as e:
        print(f"Ошибка при сохранении состояния окон: {e}")


def load_windows_state():
    """Загружает состояние окон из реестра для текущего профиля"""
    global windows, current_profile
    
    # Закрываем все существующие окна
    for window in windows[:]:
        window.close()
    windows.clear()
    
    if not current_profile:
        print("Нет активного профиля для загрузки")
        return
    
    try:
        # Открываем ключ текущего профиля
        profile_key_path = f"{REGISTRY_BASE_KEY}\\Profiles\\{current_profile}"
        profile_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, profile_key_path)
        
        try:
            # Получаем количество сохраненных окон
            windows_count, _ = winreg.QueryValueEx(profile_key, "WindowsCount")
            
            # Загружаем каждое окно
            for i in range(windows_count):
                try:
                    window_key_path = f"{profile_key_path}\\Window{i}"
                    window_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, window_key_path)
                    
                    # Получаем путь к изображению
                    image_path, _ = winreg.QueryValueEx(window_key, "ImagePath")
                    
                    # Получаем позицию и размер
                    x, _ = winreg.QueryValueEx(window_key, "X")
                    y, _ = winreg.QueryValueEx(window_key, "Y")
                    width, _ = winreg.QueryValueEx(window_key, "Width")
                    height, _ = winreg.QueryValueEx(window_key, "Height")
                    
                    # Создаем окно с изображением
                    image_window = ImageWindow(image_path)
                    image_window.setGeometry(x, y, width, height)
                    windows.append(image_window)
                    
                    winreg.CloseKey(window_key)
                except Exception as e:
                    print(f"Ошибка при загрузке окна {i}: {e}")
            
            print(f"Загружено {len(windows)} окон из профиля '{current_profile}'")
        except FileNotFoundError:
            print(f"Нет сохраненных окон в профиле '{current_profile}'")
        
        winreg.CloseKey(profile_key)
    except FileNotFoundError:
        print(f"Ключ профиля '{current_profile}' не найден")

def switch_to_next_profile():
    """Переключается на следующий профиль в списке"""
    global current_profile, profiles_list
    
    if not profiles_list or len(profiles_list) <= 1:
        return
    
    # Находим индекс текущего профиля
    try:
        current_index = profiles_list.index(current_profile)
    except ValueError:
        current_index = -1
    
    # Вычисляем индекс следующего профиля
    next_index = (current_index + 1) % len(profiles_list)
    next_profile = profiles_list[next_index]
    
    # Переключаемся на следующий профиль
    if next_profile != current_profile:
        # Сохраняем текущее состояние
        save_windows_state()
        
        # Переключаемся на новый профиль
        set_current_profile(next_profile)
        
        # Загружаем состояние из нового профиля
        load_windows_state()
        
        # Переходим в режим рабочего стола
        toggle_all_windows_mode(True)
        
        print(f"Переключились на профиль: {next_profile}")

def switch_to_prev_profile():
    """Переключается на предыдущий профиль в списке"""
    global current_profile, profiles_list
    
    if not profiles_list or len(profiles_list) <= 1:
        return
    
    # Находим индекс текущего профиля
    try:
        current_index = profiles_list.index(current_profile)
    except ValueError:
        current_index = 0
    
    # Вычисляем индекс предыдущего профиля
    prev_index = (current_index - 1) % len(profiles_list)
    prev_profile = profiles_list[prev_index]  # Правильно получаем prev_profile
    
    # Переключаемся на предыдущий профиль
    if prev_profile != current_profile:
        # Сохраняем текущее состояние
        save_windows_state()
        
        # Переключаемся на новый профиль
        set_current_profile(prev_profile)
        
        # Загружаем состояние из нового профиля
        load_windows_state()
        
        # Переходим в режим рабочего стола
        toggle_all_windows_mode(True)
        
        print(f"Переключились на профиль: {prev_profile}")

class WallpaperWindow(QMainWindow):
    """Отдельный класс для режима рабочего стола"""
    def __init__(self, image_path, rotation=0, opacity=1.0, scale_factor=1.0, position=None):
        super().__init__()
        
        print(f"Создание WallpaperWindow для изображения: {image_path}")
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Файл изображения не существует: {image_path}")
        
        self.image_path = image_path
        self.rotation = rotation
        self.opacity_value = opacity
        self.scale_factor = scale_factor
        
        # Устанавливаем флаги окна для режима рабочего стола
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Создаем метку для изображения
        self.label = QLabel(self)
        
        # Загружаем изображение
        self.original_pixmap = QPixmap(self.image_path)
        self.loadImage()
        
        # Присоединяем к окну рабочего стола
        desktop_hwnd = find_desktop_window()
        if (desktop_hwnd):
            hwnd = int(self.winId())
            win32gui.SetParent(hwnd, desktop_hwnd)
            
            style = WS_EX_LAYERED | WS_EX_NOACTIVATE
            win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, style)
            
            win32gui.SetWindowPos(
                hwnd, None,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE
                | win32con.SWP_NOSIZE
                | win32con.SWP_NOACTIVATE
                | win32con.SWP_SHOWWINDOW
            )
        
        self.show()
        
        if position:
            self.move(position)
            
    def loadImage(self):
        if not self.original_pixmap.isNull():
            # Применяем поворот
            transform = QTransform()
            transform.rotate(self.rotation)
            pixmap = self.original_pixmap.transformed(transform)
            
            # Применяем масштабирование
            if self.scale_factor != 1.0:
                new_width = int(pixmap.width() * self.scale_factor)
                new_height = int(pixmap.height() * self.scale_factor)
                pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Устанавливаем изображение
            self.label.setPixmap(pixmap)
            self.resize(pixmap.width(), pixmap.height())
            self.label.setGeometry(0, 0, pixmap.width(), pixmap.height())
            
            # Устанавливаем прозрачность
            self.setWindowOpacity(self.opacity_value)

class SelectionFrame(QWidget):
    """Отдельный виджет для отображения рамки выделения"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # Устанавливаем флаги окна
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        # Цвет рамки такой же, как у фона "edit mode"
        self.frame_color = QColor("#1C1A99")
        
    def paintEvent(self, event):
        painter = QPainter(self)
        # Делаем ОЧЕНЬ жирную рамку
        pen = QPen(self.frame_color, 10, Qt.DashLine)
        # Возвращаем видимую пунктирность, но с короткими сегментами
        pen.setDashPattern([0.5, 2])  # 1 пикселей штрих, 2 пикселей пробел
        painter.setPen(pen)
        margin = 5
        painter.drawRect(margin, margin, self.width() - 2*margin, self.height() - 2*margin)
        painter.end()

# Полностью переписанная функция для очистки выделений
def clear_all_selections():
    """Очищает все выделения - удаляет все рамки и очищает список"""
    global windows_selection
    
    print("Очистка всех выделений...")
    
    # Делаем копию списка, поскольку он может измениться во время итерации
    for window in list(windows_selection):
        if hasattr(window, 'selection_frame') and window.selection_frame:
            print(f"Удаляю рамку выделения для окна {window.image_path}")
            window.selection_frame.setParent(None)  # Убираем родителя
            window.selection_frame.hide()           # Скрываем
            window.selection_frame.deleteLater()    # Планируем удаление
            window.selection_frame = None           # Обнуляем ссылку
            window.is_selected = False              # Сбрасываем флаг
    
    # Очищаем список выделенных окон
    windows_selection.clear()
    print("Все выделения очищены.")

# Глобальное переключение режима с четкой обработкой выделений
def toggle_all_windows_mode(is_desktop_mode):
    """
    Переключает режим между рабочим столом и режимом редактирования.
    is_desktop_mode=True значит переключаемся В режим рабочего стола.
    is_desktop_mode=False значит переключаемся В режим редактирования.
    """
    global global_desktop_mode, wallpaper_windows, windows, overlay_bar, is_switching_mode
    try:
        # Если уже идет переключение или режим уже активен, игнорируем запрос
        if is_switching_mode or global_desktop_mode == is_desktop_mode:
            print(f"Игнорируем запрос на переключение: уже переключаемся или режим уже {is_desktop_mode}")
            return
            
        is_switching_mode = True
        print(f"Переключение режима в {'desktop mode' if is_desktop_mode else 'edit mode'}...")
        
        clear_all_selections()
        
        # Смена режима - сначала меняем глобальную переменную
        global_desktop_mode = is_desktop_mode

        if not is_desktop_mode:  # Переход в edit mode (режим редактирования)
            # Закрываем все окна-обои
            for wp in wallpaper_windows[:]:
                wp.close()
            wallpaper_windows.clear()  # Очищаем список

            # Показываем основные окна
            for window in windows:
                window.show()
                window.raise_()
                # Важно: сбрасываем режим для каждого окна
                window.set_desktop_mode(False)

            # Показываем панель инструментов
            if overlay_bar:
                overlay_bar.show_overlay()
                overlay_bar.raise_()

        else:  # Переход в desktop mode (режим рабочего стола)
            # Скрываем все основные окна
            for window in windows:
                window.hide()
                window.set_desktop_mode(True)

            # Скрываем панель инструментов
            if overlay_bar:
                overlay_bar.hide()

            # Создаем окна-обои только если они еще не созданы
            if not wallpaper_windows:
                for i, img_win in enumerate(reversed(windows)):
                    try:
                        # Проверяем, существует ли файл изображения
                        if not os.path.exists(img_win.image_path):
                            print(f"Файл не существует: {img_win.image_path}, пропускаем")
                            continue
                            
                        # Создаем окно-обои
                        wp = WallpaperWindow(
                            img_win.image_path,
                            img_win.rotation,
                            img_win.opacity_value,
                            img_win.scale_factor,
                            img_win.pos()
                        )
                        wallpaper_windows.append(wp)
                        
                        # Настраиваем Z-order окон
                        hwnd_wp = int(wp.winId())
                        if i == 0:
                            win32gui.SetWindowPos(
                                hwnd_wp, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                            )
                        else:
                            hwnd_prev = int(wallpaper_windows[i - 1].winId())
                            win32gui.SetWindowPos(
                                hwnd_wp, hwnd_prev, 0, 0, 0, 0,
                                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                            )
                    except Exception as e:
                        print(f"Ошибка при создании окна-обоев для {img_win.image_path}: {e}")

        # Сбрасываем флаг переключения через 1 секунду
        QTimer.singleShot(1000, lambda: unblock_switch_mode())

    except Exception as e:
        print(f"Ошибка в toggle_all_windows_mode: {e}")
        traceback.print_exc()
        is_switching_mode = False  # Сбрасываем флаг в случае ошибки


# Обработчик горячей клавиши более явно инвертирует текущий режим
def hotkey_pressed_toggle_mode():
    """Обработчик горячей клавиши для переключения режима."""
    global global_desktop_mode
    
    # Определяем новый режим как противоположный текущему
    new_mode = not global_desktop_mode
    
    print(f"Нажата клавиша Ctrl+Alt+D для переключения в режим: {'рабочего стола' if new_mode else 'редактирования'}")
    print(f"Текущий режим: {'рабочий стол' if global_desktop_mode else 'редактирование'}")
    
    # Эмитируем сигнал для переключения режима
    hotkey_signals.toggle_all_windows_mode_signal.emit(new_mode)


# Сбрасываем флаг переключения режима
def unblock_switch_mode():
    """Сбрасывает флаг блокировки переключения режима"""
    global is_switching_mode
    is_switching_mode = False
    print("Разблокировано переключение режима")

def mouseMoveEvent(self, event):
    """Обработка движения мыши"""
    # Если не нажата левая кнопка мыши, просто обновляем курсор
    if not event.buttons() & Qt.LeftButton:
        if not self.drag_locked:
            edge = self.detect_edge(event.pos())
            self.update_cursor(edge)
        return
    
    # Если идёт изменение размера
    if self.resizing and not self.drag_locked:
        # ... существующий код для изменения размера ...
        return
    
    # Если у нас есть позиция для перетаскивания и нет блокировки
    if self.drag_position is not None and not self.drag_locked:
        # Вычисляем новую позицию
        new_pos = event.globalPos() - self.drag_position
        
        # УПРОЩАЕМ: Если это окно в списке выделенных и там больше одного окна
        if self in windows_selection and len(windows_selection) > 1:
            # Вычисляем смещение
            delta_x = new_pos.x() - self.x()
            delta_y = new_pos.y() - self.y()
            
            print(f"Перемещаю группу выделенных объектов на dx={delta_x}, dy={delta_y}")
            
            # Сначала перемещаем другие окна
            for window in windows_selection:
                if window != self:
                    window.move(window.x() + delta_x, window.y() + delta_y)
                    # Обновляем положение рамки сразу
                    if hasattr(window, 'update_selection_frame'):
                        window.update_selection_frame()
            
            # Теперь перемещаем текущее окно
            self.move(new_pos)
            # И обновляем его рамку
            self.update_selection_frame()
        else:
            # Просто перемещаем текущее окно
            self.move(new_pos)
            # Обновляем рамку, если она есть
            if self in windows_selection:
                self.update_selection_frame()
        
        event.accept()

# Для отслеживания состояния мыши - добавим mouseReleaseEvent
def mouseReleaseEvent(self, event):
    """Обработка отпускания кнопки мыши"""
    if event.button() == Qt.LeftButton:
        # Сбрасываем состояния
        self.drag_position = None
        self.resizing = False
        self.resize_edge = EDGE_NONE
        
        # Обновляем курсор
        edge = self.detect_edge(event.pos())
        self.update_cursor(edge)
    
    # Вызываем родительский метод
    super().mouseReleaseEvent(event)

# Для глобального фильтра - принудительное очищение при выходе из edit mode
class GlobalEventFilter(QObject):
    def eventFilter(self, obj, event):
        # Обрабатываем клики мыши
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            # Проверяем, что не кликнули на наших окнах
            clicked_on_our_window = False
            for window in windows:
                if window.underMouse():
                    clicked_on_our_window = True
                    break
            
            # Если клик не на наших окнах - очищаем выделение
            if not clicked_on_our_window and (not overlay_bar or not overlay_bar.underMouse()):
                clear_all_selections()
        
        # Обрабатываем изменение активного окна (для очистки выделений)
        elif event.type() == QEvent.ActivationChange:
            # Если активировалось не наше окно - проверяем global_desktop_mode
            if global_desktop_mode and windows_selection:
                # В режиме рабочего стола - гарантированно чистим выделения
                clear_all_selections()
        
        return super().eventFilter(obj, event)

class ImageWindow(QMainWindow):
    """Главное окно приложения"""
    
    def __init__(self, image_path):
        super().__init__()
        
        # Проверяем, существует ли файл
        if not os.path.exists(image_path):
            print(f"ОШИБКА: Изображение не найдено: {image_path}")
            return
        
        self.image_path = image_path
        self.original_pixmap = QPixmap(image_path)
        
        # Свойства окна
        self.rotation = 0
        self.opacity_value = 1.0
        self.scale_factor = 1.0
        self.drag_position = None
        self.drag_locked = False
        self.control_panel_visible = False
        self.resizing = False
        self.resize_edge = EDGE_NONE
        self.is_active = False  # Флаг для отслеживания активности окна
        self.selection_frame = None  # Будет хранить объект SelectionFrame
        self.is_selected = False  # Флаг выделения окна
        
        # Расчет начального размера (не больше 800 пикселей по высоте)
        self.calculate_initial_size()
        
        # Настройка окна
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Добавляем для контроля z-order
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        
        self.setMouseTracking(True)  # Включаем отслеживание мыши без нажатия
        
        # Создаем метку для изображения
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        
        # Создаем панель управления
        self.create_controls()
        
        # Загружаем изображение
        self.loadImage()
        
        print(f"Создано окно с изображением: {image_path}")
        
        # Подключаем сигнал глобального переключения режима
        hotkey_signals.toggle_all_windows_mode_signal.connect(self.on_global_mode_change)
        
        # Установка начального размера окна
        if not self.original_pixmap or self.original_pixmap.isNull():
            self.resize(400, 300)
        
        # Устанавливаем обработчик событий мыши
        self.installEventFilter(self)
    
    def calculate_initial_size(self):
        """Рассчитывает начальный размер изображения (не больше 800 пикселей по высоте)"""
        if self.original_pixmap.height() > 800:
            # Рассчитываем масштаб, чтобы высота была 800 пикселей
            self.scale_factor = 800 / self.original_pixmap.height()
        else:
            # Если изображение уже достаточно маленькое, оставляем как есть
            self.scale_factor = 1.0

    def create_controls(self):
        """Создает панель управления с кнопками"""
        # Создаем панель
        self.control_panel = QFrame(self)
        self.control_panel.setStyleSheet("""
            QFrame {
                background-color: rgba(40, 40, 40, 150);
                border-radius: 5px;
                padding: 2px;
            }
            QPushButton {
                background-color: rgba(60, 60, 60, 200);
                color: white;
                border: none;
                border-radius: 3px;
                padding: 4px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: rgba(80, 80, 80, 230);
            }
            QSlider {
                background: transparent;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: rgba(100, 100, 100, 200);
                margin: 0px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: white;
                width: 10px;
                margin: -3px 0;
                border-radius: 5px;
            }
        """)
        
        # Компактная панель с инструментами
        layout = QHBoxLayout(self.control_panel)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        
        # Добавление нового изображения
        self.btn_add = QPushButton("+", self.control_panel)
        self.btn_add.setToolTip("Добавить изображение")
        self.btn_add.clicked.connect(self.add_image)
        layout.addWidget(self.btn_add)
        
        # Ползунок прозрачности (с иконкой)
        self.opacity_slider = QSlider(Qt.Horizontal, self.control_panel)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(int(self.opacity_value * 100))
        self.opacity_slider.setToolTip("Прозрачность")
        self.opacity_slider.valueChanged.connect(self.change_opacity)
        layout.addWidget(self.opacity_slider)
        
        # Кнопка поворота
        self.btn_rotate = QPushButton("⟳", self.control_panel)
        self.btn_rotate.setToolTip("Повернуть изображение")
        self.btn_rotate.clicked.connect(self.rotate_image)
        layout.addWidget(self.btn_rotate)
        
        # Кнопка блокировки перемещения
        self.btn_lock = QPushButton("🔓", self.control_panel)
        self.btn_lock.setToolTip("Заблокировать перемещение")
        self.btn_lock.clicked.connect(self.toggle_lock)
        layout.addWidget(self.btn_lock)
        
        # Кнопка закрытия
        self.btn_close = QPushButton("✕", self.control_panel)
        self.btn_close.setToolTip("Закрыть окно")
        self.btn_close.clicked.connect(self.remove_image)
        layout.addWidget(self.btn_close)
        
        # Устанавливаем размеры панели после добавления всех элементов
        self.control_panel.adjustSize()
        self.control_panel.hide()  # Скрываем панель при старте
    
    def eventFilter(self, obj, event):
        """Обработчик событий для показа/скрытия панели управления"""
        if obj == self:
            if event.type() == event.Enter:
                self.control_panel.show()
            elif event.type() == event.Leave:
                # Проверяем, не находится ли курсор над панелью управления
                cursor_pos = QCursor.pos()
                panel_global_rect = QRect(
                    self.control_panel.mapToGlobal(QPoint(0, 0)), 
                    self.control_panel.size()
                )
                if not panel_global_rect.contains(cursor_pos):
                    self.control_panel.hide()
            
        return super().eventFilter(obj, event)
    
    def loadImage(self):
        """Загружает и отображает изображение с учетом поворота и масштаба"""
        if self.original_pixmap.isNull():
            return
        
        # Применяем поворот
        transform = QTransform()
        transform.rotate(self.rotation)
        pixmap = self.original_pixmap.transformed(transform)
        
        # Применяем масштабирование
        if self.scale_factor != 1.0:
            new_width = int(pixmap.width() * self.scale_factor)
            new_height = int(pixmap.height() * self.scale_factor)
            pixmap = pixmap.scaled(new_width, new_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # Устанавливаем изображение
        self.label.setPixmap(pixmap)
        
        # Устанавливаем прозрачность
        self.setWindowOpacity(self.opacity_value)
        
        # Изменяем размер окна по размеру изображения
        self.resize(pixmap.width(), pixmap.height())
        
        # Размещаем label по размеру окна
        self.label.setGeometry(0, 0, pixmap.width(), pixmap.height())
        
        # Устанавливаем позицию панели управления снизу по центру
        panel_width = self.control_panel.width()
        panel_height = self.control_panel.height()
        panel_x = (pixmap.width() - panel_width) // 2
        panel_y = pixmap.height() - panel_height - 10
        self.control_panel.setGeometry(panel_x, panel_y, panel_width, panel_height)
    
    def on_global_mode_change(self, is_desktop_mode):
        """Обработчик изменения глобального режима для этого окна"""
        try:
            global wallpaper_windows
            
            print(f"on_global_mode_change для окна {self.image_path}: {is_desktop_mode}")
            
            if is_desktop_mode:
                # Сохраняем текущее положение (если нужно)
                self.saved_position = self.pos()
                self.saved_visibility = self.isVisible()
                
                # В режиме рабочего стола просто скрываем окно
                self.hide()
            else:
                # Возвращаемся в обычный режим
                # (окна-обои при этом закрываются в toggle_windows_mode)
                self.show()
                self.raise_()
        except Exception as e:
            print(f"Ошибка при изменении режима в окне: {e}")
            traceback.print_exc()

    def mousePressEvent(self, event):
        """Обработка нажатия кнопки мыши"""
        if event.button() == Qt.LeftButton:
            # Отладочный вывод для проверки модификатора Ctrl
            print(f"Mouse press with modifiers: {QApplication.keyboardModifiers()}")
            
            # Устанавливаем это окно как активное
            self.set_as_active()
            
            if QApplication.keyboardModifiers() & Qt.ControlModifier:
                # С Ctrl - добавляем/удаляем в/из выделения
                if self in windows_selection:
                    windows_selection.remove(self)
                    print(f"Removed from selection. Count: {len(windows_selection)}")
                else:
                    windows_selection.append(self)
                    print(f"Added to selection. Count: {len(windows_selection)}")
            else:
                # Без Ctrl - делаем единственным выделенным
                windows_selection.clear()
                windows_selection.append(self)
                print(f"Made single selection")
            
            # Обновляем отображение выделения для всех окон
            for window in windows:
                window.update_selection_frame()
            
            # Определяем, находится ли курсор над краем окна
            self.resize_edge = self.detect_edge(event.pos())
            
            if self.resize_edge != EDGE_NONE and not self.drag_locked:
                # Если курсор над краем, начинаем изменение размера
                self.resizing = True
                event.accept()
            elif not self.drag_locked:
                # Если не над краем, начинаем перетаскивание
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши"""
        if not event.buttons() & Qt.LeftButton:
            # Если левая кнопка не нажата, просто обновляем курсор
            if not self.drag_locked:
                edge = self.detect_edge(event.pos())
                self.update_cursor(edge)
            return
        
        # Если идёт изменение размера
        if self.resizing and not self.drag_locked:
            # Изменение размера
            if self.resize_edge == EDGE_RIGHT:
                width = max(100, event.pos().x())
                height = self.height()
                self.scale_factor = width / self.original_pixmap.width()
                # Убедимся что высота сохраняет пропорции
                height = int(self.original_pixmap.height() * self.scale_factor)
                self.resize(int(width), height)
            elif self.resize_edge == EDGE_BOTTOM:
                width = self.width()
                height = max(100, event.pos().y())
                self.scale_factor = height / self.original_pixmap.height()
                # Убедимся что ширина сохраняет пропорции
                width = int(self.original_pixmap.width() * self.scale_factor)
                self.resize(width, int(height))
            elif self.resize_edge == EDGE_BOTTOMRIGHT:
                width = max(100, event.pos().x())
                height = max(100, event.pos().y())
                
                # Сохраняем пропорции изображения
                aspect_ratio = self.original_pixmap.width() / self.original_pixmap.height()
                if width / height > aspect_ratio:
                    width = int(height * aspect_ratio)
                else:
                    height = int(width / aspect_ratio)
                
                self.scale_factor = width / self.original_pixmap.width()
                self.resize(int(width), int(height))
            
            # Обновляем изображение с новым масштабом
            self.loadImage()
            return
        
        # Перемещение окна или группы выделенных окон
        if self.drag_position is not None and not self.drag_locked:
            # Вычисляем новую позицию
            new_pos = event.globalPos() - self.drag_position
            
            # Проверяем, выделено ли это окно и есть ли другие выделенные окна
            if self in windows_selection and len(windows_selection) > 1:
                # Вычисляем смещение от текущей позиции
                delta_x = new_pos.x() - self.x()
                delta_y = new_pos.y() - self.y()
                
                # Сначала перемещаем текущее окно
                self.move(new_pos)
                
                # Затем все остальные выделенные окна на то же смещение
                for window in windows_selection:
                    if window != self:  # Не перемещаем текущее окно дважды
                        current_pos = window.pos()
                        window.move(current_pos.x() + delta_x, current_pos.y() + delta_y)
                
                # Обновляем положение рамок выделения
                for window in windows_selection:
                    window.update_selection_frame()
            else:
                # Просто перемещаем текущее окно
                self.move(new_pos)
                if self in windows_selection:
                    self.update_selection_frame()
            
            event.accept()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = None
            self.resizing = False
            self.resize_edge = EDGE_NONE
            self.setCursor(Qt.ArrowCursor)
    
    def detect_edge(self, pos):
        width = self.width()
        height = self.height()
        
        # Определяем, находится ли курсор над краем окна
        left_edge = pos.x() <= EDGE_MARGIN
        right_edge = pos.x() >= width - EDGE_MARGIN
        top_edge = pos.y() <= EDGE_MARGIN
        bottom_edge = pos.y() >= height - EDGE_MARGIN
        
        # Углы
        if top_edge and left_edge:
            return EDGE_TOPLEFT
        elif top_edge and right_edge:
            return EDGE_TOPRIGHT
        elif bottom_edge and left_edge:
            return EDGE_BOTTOMLEFT
        elif bottom_edge and right_edge:
            return EDGE_BOTTOMRIGHT
        
        # Края
        if left_edge:
            return EDGE_LEFT
        elif right_edge:
            return EDGE_RIGHT
        elif top_edge:
            return EDGE_TOP
        elif bottom_edge:
            return EDGE_BOTTOM
        
        return EDGE_NONE
    
    def add_image(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение", "", "Images (*.png *.xpm *.jpg *.bmp)"
        )
        if fname:
            self.image_path = fname
            self.original_pixmap = QPixmap(self.image_path)
            self.loadImage()
    
    def change_opacity(self, value):
        self.opacity_value = value / 100.0
        self.setWindowOpacity(self.opacity_value)
    
    def rotate_image(self):
        self.rotation = (self.rotation + 90) % 360
        self.loadImage()
    
    def remove_image(self):
        """Удаляет текущее окно из списка без закрытия приложения"""
        global windows, active_window
        
        print(f"Удаление окна: {self.image_path}")
        
        # Удаляем окно из списка 
        if self in windows:
            windows.remove(self)
        
        # Сбрасываем активное окно, если это было оно
        if active_window == self:
            active_window = None
        
        # Закрываем только окно, но не программу
        self.hide()
        self.deleteLater()
        
        print(f"Окно удалено. Осталось окон: {len(windows)}")
    
    def toggle_lock(self):
        self.drag_locked = not self.drag_locked
        self.btn_lock.setText("🔓" if not self.drag_locked else "🔒")

    def set_as_active(self):
        """Устанавливает это окно как активное"""
        global active_window
        
        # Сбрасываем активное состояние предыдущего окна
        if active_window and active_window != self:
            active_window.is_active = False
            active_window.update()
        
        # Устанавливаем текущее окно как активное
        active_window = self
        self.is_active = True
        self.update()  # Перерисовываем окно, чтобы показать рамку
        # -- Вот добавим логику, чтобы последнее активное окно было в конце списка:
        if self in windows:
            windows.remove(self)
        windows.append(self)

    def update_selection_frame(self):
        """Обновляет рамку выделения"""
        print(f"Updating selection frame for window. In selection: {self in windows_selection}")
        
        # Проверяем, находится ли окно в списке выделенных
        if self in windows_selection:
            # Если рамки нет, создаем новую
            if not self.selection_frame:
                self.selection_frame = SelectionFrame()
            
            # Обновляем размер и положение рамки
            geom = self.geometry()
            self.selection_frame.setGeometry(
                geom.x() - 4, 
                geom.y() - 4, 
                geom.width() + 8, 
                geom.height() + 8
            )
            self.selection_frame.show()
            self.is_selected = True
            print("Selection frame shown")
        else:
            # Если окно не выделено, скрываем и удаляем рамку
            if self.selection_frame:
                self.selection_frame.hide()
                self.selection_frame.deleteLater()
                self.selection_frame = None
            self.is_selected = False
            print("Selection frame hidden/removed")

    def paintEvent(self, event):
        """Переопределяем метод рисования для добавления рамки активному окну"""
        # Сначала рисуем само изображение через родительский метод
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        
        # Если окно активно, рисуем синюю рамку
        if self.is_active:
            pen = QPen(Qt.blue, 2)  # Синяя рамка толщиной 2 пикселя
            painter.setPen(pen)
            painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        
        painter.end()  # Завершаем работу с painter

        # ВНИМАНИЕ: Убрана попытка рисовать self.selection_frame,
        # так как теперь это отдельный виджет, а не объект QRect

    def moveEvent(self, event):
        """Обработчик события перемещения окна - обновляем положение рамки"""
        super().moveEvent(event)
        if self.is_selected:
            self.update_selection_frame()
    
    def resizeEvent(self, event):
        """Обработчик события изменения размера - обновляем размер рамки"""
        super().resizeEvent(event)
        if self.is_selected:
            self.update_selection_frame()
    
    def closeEvent(self, event):
        """Обработчик закрытия окна - удаляем рамку выделения"""
        if self.selection_frame:
            self.selection_frame.deleteLater()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        # Обработка нажатия клавиш
        super().keyPressEvent(event)
        
        # Если нажата клавиша Ctrl, не делаем ничего особенного (просто она работает как модификатор)
        if event.key() == Qt.Key_Control:
            pass  # Не выполняем никаких действий

    def set_desktop_mode(self, enabled):
        if enabled:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnBottomHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        else:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.show()

    def update_flags(self, edit_mode):
        flags = Qt.FramelessWindowHint | Qt.Tool
        if edit_mode:
            flags |= Qt.WindowStaysOnTopHint
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        else:
            flags |= Qt.WindowStaysOnBottomHint
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(flags)
        self.show()

def hotkey_pressed_create():
    hotkey_signals.create_window_signal.emit()

def hotkey_pressed_toggle_mode():
    """Обработчик горячей клавиши для переключения режима."""
    global global_desktop_mode
    
    # Определяем новый режим как противоположный текущему
    new_mode = not global_desktop_mode
    
    print(f"Нажата клавиша Ctrl+Alt+D для переключения в режим: {'рабочего стола' if new_mode else 'редактирования'}")
    print(f"Текущий режим: {'рабочий стол' if global_desktop_mode else 'редактирование'}")
    
    # Эмитируем сигнал для переключения режима
    hotkey_signals.toggle_all_windows_mode_signal.emit(new_mode)

def hotkey_pressed_paste_image():
    """Обработчик горячей клавиши для вставки изображения из буфера обмена"""
    print("Нажата клавиша для вставки изображения из буфера обмена")
    hotkey_signals.paste_image_signal.emit()

def hotkey_pressed_delete_active():
    """Обработчик горячей клавиши для удаления активного окна"""
    print("Нажата клавиша для удаления активного окна")
    hotkey_signals.delete_active_window_signal.emit()

def hotkey_pressed_exit_app():
    """Обработчик горячей клавиши для выхода из приложения."""
    print("Нажата клавиша для выхода из приложения (Ctrl+Alt+N). Сохраняем состояние и завершаем...")
    save_windows_state()  # сохраняем параметры окон
    QApplication.quit()   # корректно завершаем приложение

def hotkey_pressed_next_profile():
    """Обработчик горячей клавиши Ctrl+Alt+Right для переключения на следующий профиль"""
    if is_switching_mode:
        return
    switch_to_next_profile()

def hotkey_pressed_prev_profile():
    """Обработчик горячей клавиши Ctrl+Alt+Left для переключения на предыдущий профиль"""
    if is_switching_mode:
        return
    switch_to_prev_profile()


@pyqtSlot()
def delete_active_window():
    """Удаляет активное в данный момент окно"""
    global active_window
    
    if active_window:
        print(f"Удаление активного окна: {active_window.image_path}")
        active_window.remove_image()
    else:
        print("Нет активного окна для удаления")

@pyqtSlot()
def paste_image_from_clipboard():
    """Создает новое окно с изображением из буфера обмена"""
    try:
        # Получаем доступ к буферу обмена
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        # Проверяем, есть ли изображение в буфере обмена
        if mime_data.hasImage():
            print("Найдено изображение в буфере обмена")
            image = clipboard.image()
            
            if not image.isNull():
                # Создаем временный файл для сохранения изображения
                temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                temp_filename = temp_file.name
                temp_file.close()
                
                # Сохраняем изображение
                image.save(temp_filename, "PNG")
                print(f"Изображение сохранено во временный файл: {temp_filename}")
                
                # Сначала переводим в режим редактирования
                hotkey_signals.toggle_all_windows_mode_signal.emit(False)
                
                # Создаем новое окно
                new_win = ImageWindow(temp_filename)
                windows.append(new_win)
                new_win.show()
                new_win.raise_()
                new_win.activateWindow()
                print("Создано новое окно с изображением из буфера обмена")
            else:
                print("Изображение в буфере обмена повреждено или недоступно")
        else:
            print("В буфере обмена нет изображения")
    except Exception as e:
        print(f"Ошибка при вставке изображения из буфера обмена: {e}")
        traceback.print_exc()

@pyqtSlot()
def create_new_window():
    """Создает новое окно с изображением"""
    try:
        # Если мы в режиме рабочего стола, сначала переключаемся в режим редактирования
        if global_desktop_mode:
            print("Переключаемся из режима рабочего стола перед созданием нового окна")
            # Переключаемся в режим редактирования
            hotkey_signals.toggle_all_windows_mode_signal.emit(False)
            
            # Добавляем таймер для создания окна после переключения
            QTimer.singleShot(1200, lambda: open_file_dialog_and_create_window())
        else:
            # Если мы уже в режиме редактирования, просто создаем окно
            open_file_dialog_and_create_window()
            
    except Exception as e:
        print(f"Ошибка при создании нового окна: {e}")
        traceback.print_exc()  # Печатаем ошибку, если что-то пошло не так

def open_file_dialog_and_create_window():
    """Вспомогательная функция для выбора файла и создания окна с изображением"""
    try:
        fname, _ = QFileDialog.getOpenFileName(
            None, "Выберите изображение", "", "Images (*.png *.xpm *.jpg *.bmp)"
        )
        if fname:
            # Если файл выбран, продолжаем создание окна
            # Создаем новое окно
            new_win = ImageWindow(fname)
            
            # Добавляем в список окон
            windows.append(new_win)
            
            # Показываем окно и поднимаем его наверх
            new_win.show()
            new_win.raise_()
            new_win.activateWindow()
        else:
            # Если пользователь отменил выбор изображения
            print("Выбор изображения отменён, окно не создано.")
    except Exception as e:
        print(f"Ошибка при создании нового окна из диалога: {e}")
        traceback.print_exc()  # Печатаем ошибку, если что-то пошло не так

        
def toggle_windows_mode(is_desktop_mode):
    """
    Переключает режим между рабочим столом и режимом редактирования.
    is_desktop_mode=True значит переключаемся В режим рабочего стола.
    is_desktop_mode=False значит переключаемся В режим редактирования.
    """
    global global_desktop_mode, wallpaper_windows, windows, overlay_bar, is_switching_mode
    try:
        # Если уже идет переключение или режим уже активен, игнорируем запрос
        if is_switching_mode or global_desktop_mode == is_desktop_mode:
            print(f"Игнорируем запрос на переключение: уже переключаемся или режим уже {is_desktop_mode}")
            return
            
        global_desktop_mode = is_desktop_mode
        is_switching_mode = True
        print(f"Переключение режима в {'desktop mode' if is_desktop_mode else 'edit mode'}...")
        clear_all_selections()

        if not is_desktop_mode:  # Переход в edit mode
            for wp in wallpaper_windows[:]:
                wp.close()
            wallpaper_windows.clear()

            for window in windows:
                window.show()
                window.raise_()

            if overlay_bar:
                overlay_bar.show_overlay()
                overlay_bar.raise_()

        else:  # Переход в desktop mode
            for window in windows:
                window.hide()

            if overlay_bar:
                overlay_bar.hide()

            # Создаем окна-обои только если их ещё нет
            if not wallpaper_windows:
                for i, img_win in enumerate(reversed(windows)):
                    wp = WallpaperWindow(
                        img_win.image_path,
                        img_win.rotation,
                        img_win.opacity_value,
                        img_win.scale_factor,
                        img_win.pos()
                    )
                    wallpaper_windows.append(wp)
                    hwnd_wp = int(wp.winId())

                    if i == 0:
                        win32gui.SetWindowPos(
                            hwnd_wp, win32con.HWND_BOTTOM, 0, 0, 0, 0,
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                        )
                    else:
                        hwnd_prev = int(wallpaper_windows[i - 1].winId())
                        win32gui.SetWindowPos(
                            hwnd_wp, hwnd_prev, 0, 0, 0, 0,
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE |
                            win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                        )

            # Минимизируем прочие окна для лучшего пользовательского опыта
            def minimize_other_windows(hwnd, _):
                our_hwnds = [int(window.winId()) for window in windows]
                for wp in wallpaper_windows:
                    our_hwnds.append(int(wp.winId()))
                if overlay_bar:
                    our_hwnds.append(int(overlay_bar.winId()))

                class_name = win32gui.GetClassName(hwnd)
                if (win32gui.IsWindowVisible(hwnd) and
                    hwnd not in our_hwnds and
                    class_name not in ("WorkerW", "Progman") and
                    not win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE) & win32con.WS_EX_TOOLWINDOW):
                    win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)

            win32gui.EnumWindows(minimize_other_windows, None)

        # Блокировка проверки таймером на 1 секунду
        QTimer.singleShot(1000, lambda: unblock_switch_mode())
        
        # Активируем наше окно после небольшой задержки
        QTimer.singleShot(400, activate_our_app_window)

    except Exception as e:
        print(f"Ошибка в toggle_all_windows_mode: {e}")
        traceback.print_exc()
        is_switching_mode = False  # Сбрасываем флаг в случае ошибки

def unblock_switch_mode():
    global is_switching_mode
    is_switching_mode = False


# Класс невидимого окна, чтобы приложение не закрывалось
class KeepAliveWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KeepAlive")
        self.setFixedSize(1, 1)  # Минимальный размер
        self.setWindowFlags(Qt.Tool)  # Не показывать в панели задач
        self.hide()  # Скрыть окно

from PyQt5.QtCore import QSettings

def update_profiles_menu():
    """Обновляет меню профилей в трее"""
    try:
        global tray_menu, tray_icon, profiles_list, current_profile, profiles_action, profiles_menu
        
        # Удаляем существующее меню профилей
        if 'profiles_action' in globals():
            tray_menu.removeAction(profiles_action)
        
        # Создаем новое подменю профилей
        profiles_menu = QMenu('Профили')
        
        # Загружаем список профилей
        profiles_list = load_profiles_list()
        
        # Добавляем пункты для каждого профиля
        for profile in profiles_list:
            profile_action = QAction(profile, profiles_menu, checkable=True)
            profile_action.setChecked(profile == current_profile)
            
            # Создаем контекстное меню для этого профиля
            profile_context_menu = QMenu(profiles_menu)
            
            # Действие "Переименовать"
            rename_action = QAction('Переименовать', profile_context_menu)
            rename_action.triggered.connect(lambda checked=False, p=profile: rename_profile_dialog(p))
            profile_context_menu.addAction(rename_action)
            
            # Действие "Удалить" (только если профилей больше одного)
            if len(profiles_list) > 1:
                delete_action = QAction('Удалить', profile_context_menu)
                delete_action.triggered.connect(lambda checked=False, p=profile: delete_profile_dialog(p))
                profile_context_menu.addAction(delete_action)
            
            # Устанавливаем контекстное меню
            profile_action.setMenu(profile_context_menu)
            
            # Основное действие - переключиться на профиль
            profile_action.triggered.connect(lambda checked=False, p=profile: switch_to_profile(p))
            
            profiles_menu.addAction(profile_action)
        
        # Добавляем разделитель
        profiles_menu.addSeparator()
        
        # Добавляем пункт "Создать новый профиль"
        new_profile_action = QAction('Создать новый профиль', profiles_menu)
        new_profile_action.triggered.connect(create_profile_dialog)
        profiles_menu.addAction(new_profile_action)
        
        # Добавляем меню профилей в основное меню
        profiles_action = tray_menu.insertMenu(tray_menu.actions()[0], profiles_menu)
        
    except Exception as e:
        print(f"Ошибка при обновлении меню профилей: {e}")
        traceback.print_exc()

def is_autorun_enabled():
    """Проверяет, включена ли автозагрузка"""
    try:
        # Открываем ключ реестра для автозагрузки
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_READ)
        # Проверяем наличие значения с именем нашей программы
        value, _ = winreg.QueryValueEx(key, 'PeekPickPic')
        # Если значение есть, то автозагрузка включена
        return True
    except FileNotFoundError:
        # Если ключа или значения нет, то автозагрузка отключена
        return False

def toggle_autorun():
    """Включает или отключает автозагрузку"""
    if is_autorun_enabled():
        # Если автозагрузка включена, то отключаем ее
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, 'PeekPickPic')
    else:
        # Если автозагрузка отключена, то включаем ее
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run', 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, 'PeekPickPic', 0, winreg.REG_SZ, f'"{os.path.abspath(sys.executable)}"')

def create_new_profile_dialog():
    global profile_action, profiles_menu, profiles_action
    print("Внутри create_new_profile_dialog()")  # Отладочное сообщение
    profile_name, ok = QInputDialog.getText(None, 'Новый профиль', 
                                            'Введите имя нового профиля:')
    print(f"Введено имя профиля: {profile_name}, OK: {ok}")  # Отладочное сообщение
    if ok and profile_name:
        if profile_name in profiles_list:
            QMessageBox.warning(None, 'Ошибка', 
                                f'Профиль с именем "{profile_name}" уже существует.')
            return
        
        print("Сохранение текущего профиля")  # Отладочное сообщение
        save_windows_state()
        
        print(f"Создание нового профиля: {profile_name}")  # Отладочное сообщение
        create_profile(profile_name)
        
        print(f"Переключение на профиль: {profile_name}")  # Отладочное сообщение
        set_current_profile(profile_name)
        
        print("Очистка окон для нового профиля")  # Отладочное сообщение
        for window in windows[:]:
            window.close()
        windows.clear()
        
        print('Переключение в "режим рабочего стола"')  # Отладочное сообщение
        toggle_all_windows_mode(True)
        
        print("Обновление меню профилей")  # Отладочное сообщение
        update_profiles_menu()
        
        print(f"Текущий список профилей: {profiles_list}")  # Отладочное сообщение
        print(f"Текущий профиль: {current_profile}")  # Отладочное сообщение

def rename_profile_dialog(profile_name):
    global profile_action, profiles_menu, profiles_action
    print(f"Внутри rename_profile_dialog(), профиль: {profile_name}")  # Отладочное сообщение
    try:
        new_name, ok = QInputDialog.getText(None, 'Переименовать профиль', 
                                            'Введите новое имя профиля:',
                                            text=profile_name)
        print(f"Введено новое имя профиля: {new_name}, OK: {ok}")  # Отладочное сообщение
        if ok and new_name and new_name != profile_name:
            if new_name in profiles_list:
                QMessageBox.warning(None, 'Ошибка', 
                                    f'Профиль с именем "{new_name}" уже существует!')
                return
                
            print(f"Переименование профиля: {profile_name} -> {new_name}")  # Отладочное сообщение
            if rename_profile(profile_name, new_name):
                print("Обновление меню профилей")  # Отладочное сообщение
                update_profiles_menu()
    except Exception as e:
        print(f"Ошибка при переименовании профиля: {e}")  # Отладочное сообщение
        traceback.print_exc()

print("Диалоги для работы с профилями созданы")  # Отладочное сообщение    


# Функция для безопасного переключения на профиль
def switch_to_profile(profile_name):
    try:
        if profile_name == current_profile:
            return
        
        # Сохраняем текущее состояние
        save_windows_state()
        
        # Переключаемся на выбранный профиль
        set_current_profile(profile_name)
        
        # Загружаем состояние из нового профиля
        load_windows_state()
        
        # Переходим в режим рабочего стола
        toggle_all_windows_mode(True)
        
        # Обновляем меню
        update_profiles_menu()
        
        print(f"Переключились на профиль: {profile_name}")
    except Exception as e:
        print(f"Ошибка при переключении на профиль: {e}")
        traceback.print_exc()
        

def main():
    global app, overlay_bar, tray_icon, tray_menu  # объявляем глобальные переменные
    
    app = QApplication(sys.argv)
    
    # Загружаем список профилей и текущий профиль
    load_profiles_list()
    get_current_profile()
    
    print("Профили загружены")  # Отладочное сообщение
    
    # Создаем иконку в трее
    tray_icon = QSystemTrayIcon(QIcon(r'D:\PyCharm 2024.2.3\PycharmProjects\ppp\icon.ico'), app)
    tray_icon.setToolTip('PeekPickPic')

    print("Иконка в трее создана")  # Отладочное сообщение
    
    # Создаем контекстное меню
    tray_menu = QMenu()
    
    # Опция автозагрузки
    autorun_action = QAction('Автозагрузка', tray_menu, checkable=True)
    autorun_action.setChecked(is_autorun_enabled())  # проверяем текущее состояние
    autorun_action.triggered.connect(toggle_autorun)
    tray_menu.addAction(autorun_action)
    
    tray_menu.addSeparator()
    
    # Опция выхода
    quit_action = QAction('Выход', tray_menu)
    quit_action.triggered.connect(app.quit)
    tray_menu.addAction(quit_action)

    print("Меню трея настроено")  # Отладочное сообщение
    
    # Обновляем меню профилей
    update_profiles_menu()
    
    print("Меню профилей обновлено")  # Отладочное сообщение
    
    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()
    
    print("Иконка в трее показана")  # Отладочное сообщение
    
    print("Создание диалогов для работы с профилями")  # Отладочное сообщение

    # Первоначальное заполнение меню профилей
    update_profiles_menu()
    
    # Опция автозагрузки
    autorun_action = QAction('Автозагрузка', tray_menu, checkable=True)
    autorun_action.setChecked(is_autorun_enabled())  # проверяем текущее состояние
    autorun_action.triggered.connect(toggle_autorun)
    tray_menu.addAction(autorun_action)
    
    tray_menu.addSeparator()
    
    # Опция выхода
    quit_action = QAction('Выход', tray_menu)
    quit_action.triggered.connect(app.quit)
    tray_menu.addAction(quit_action)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # Создаём оверлей один раз
    overlay_bar = EditModeOverlay()


    # Подключаем сигналы к слотам
    print("Подключение сигналов к слотам")  # Отладочное сообщение
    hotkey_signals.create_window_signal.connect(create_new_window)
    hotkey_signals.toggle_all_windows_mode_signal.connect(toggle_all_windows_mode)
    hotkey_signals.paste_image_signal.connect(paste_image_from_clipboard)
    hotkey_signals.delete_active_window_signal.connect(delete_active_window)
    print("Сигналы подключены к слотам")  # Отладочное сообщение

    print("Добавление горячих клавиш")  # Отладочное сообщение
    # Добавляем горячие клавиши
    keyboard.add_hotkey('ctrl+alt+w', hotkey_pressed_create)
    keyboard.add_hotkey('ctrl+alt+d', hotkey_pressed_toggle_mode)
    keyboard.add_hotkey('ctrl+shift+alt+w', hotkey_pressed_paste_image)
    keyboard.add_hotkey('delete', hotkey_pressed_delete_active)
    keyboard.add_hotkey('ctrl+alt+n', hotkey_pressed_exit_app)
    
    # Добавляем горячие клавиши для переключения профилей
    keyboard.add_hotkey('ctrl+alt+right', hotkey_pressed_next_profile)
    keyboard.add_hotkey('ctrl+alt+left', hotkey_pressed_prev_profile)
    print("Горячие клавиши добавлены")  # Отладочное сообщение

    print("Создание скрытого окна")  # Отладочное сообщение
    # Создаем скрытое окно, чтобы приложение не закрывалось
    keep_alive = KeepAliveWindow()
    print("Скрытое окно создано")  # Отладочное сообщение
    
    print("Загрузка состояния окон из текущего профиля")  # Отладочное сообщение
    # 1) Загружаем состояние окон (ImageWindow) из текущего профиля
    load_windows_state()
    print("Состояние окон загружено")  # Отладочное сообщение

    print("Переключение в 'режим рабочего стола'")  # Отладочное сообщение
    # 2) Автоматически переключаемся в «режим рабочего стола»
    toggle_all_windows_mode(True)
    print('Переключено в "режим рабочего стола"')  # Отладочное сообщение

    print("Создание и запуск таймера для проверки активного окна")  # Отладочное сообщение
    # Таймер, проверяющий активное окно каждые 0.5 секунды
    active_window_timer = QTimer()
    active_window_timer.timeout.connect(check_active_window)
    active_window_timer.start(500)  # 500 миллисекунд (проверка 2 раза в секунду)
    print("Таймер для проверки активного окна создан и запущен")  # Отладочное сообщение

    print("Создание и установка глобального фильтра событий")  # Отладочное сообщение
    # Создаем и устанавливаем глобальный фильтр событий
    global_event_filter = GlobalEventFilter()
    app.installEventFilter(global_event_filter)
    print("Глобальный фильтр событий установлен")  # Отладочное сообщение

    print("Запуск основного цикла событий")  # Отладочное сообщение 
    exit_code = app.exec_()
    print("Основной цикл событий завершен")  # Отладочное сообщение
    
    # При штатном завершении цикла сохраняем состояние текущего профиля
    save_windows_state()
    
    # Очищаем ресурсы
    keyboard.remove_hotkey('ctrl+alt+w')
    keyboard.remove_hotkey('ctrl+alt+d')
    keyboard.remove_hotkey('ctrl+shift+alt+w')
    keyboard.remove_hotkey('delete')
    keyboard.remove_hotkey('ctrl+alt+n')
    keyboard.remove_hotkey('ctrl+alt+right')
    keyboard.remove_hotkey('ctrl+alt+left')
    
    sys.exit(app.exec_())



if __name__ == '__main__':
    main()