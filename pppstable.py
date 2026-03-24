import sys
import os
import ctypes
import traceback
import tempfile
import keyboard
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QWidget, QFileDialog,
    QSlider, QHBoxLayout, QVBoxLayout, QFrame, QDesktopWidget
)
from PyQt5.QtCore import Qt, QPoint, QRect, QObject, pyqtSignal, pyqtSlot, QSize, QTimer
from PyQt5.QtGui import QPixmap, QTransform, QCursor, QClipboard, QImage
import win32gui
import win32con
import time

# Константы Windows API
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00080000

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

# Класс для обработки сигналов
class HotkeySignals(QObject):
    create_window_signal = pyqtSignal()
    toggle_all_windows_mode_signal = pyqtSignal(bool)
    paste_image_signal = pyqtSignal()  # Новый сигнал для вставки из буфера обмена

hotkey_signals = HotkeySignals()
global_desktop_mode = False
windows = []
wallpaper_windows = []
window_parameters = {}

def find_desktop_window():
    """Находит окно для размещения изображения под иконками рабочего стола"""
    try:
        # Сначала находим Progman
        progman = win32gui.FindWindow("Progman", None)
        if not progman:
            print("Не удалось найти окно Progman!")
            return None
        
        print(f"Найдено окно Progman: {progman}")
        
        # Отправляем сообщение для создания WorkerW
        win32gui.SendMessageTimeout(
            progman, 0x052C, 0, 0, win32con.SMTO_NORMAL, 1000)
        
        # Ждем создания окон
        time.sleep(0.1)
        
        # Собираем все окна WorkerW
        workerw_list = []
        
        def enum_windows_proc(hwnd, results):
            if win32gui.IsWindowVisible(hwnd):
                class_name = win32gui.GetClassName(hwnd)
                if class_name == "WorkerW":
                    results.append(hwnd)
            return True
        
        win32gui.EnumWindows(enum_windows_proc, workerw_list)
        
        print(f"Найдено окон WorkerW: {len(workerw_list)}")
        
        # Проверяем окна WorkerW
        for workerw in workerw_list:
            # Ищем SHELLDLL_DefView внутри WorkerW
            defview = win32gui.FindWindowEx(workerw, 0, "SHELLDLL_DefView", None)
            if defview:
                print(f"Найден SHELLDLL_DefView в WorkerW {workerw}")
                # Если нашли SHELLDLL_DefView, нам нужно следующее окно WorkerW
                next_workerw = None
                for w in workerw_list:
                    if w > workerw:
                        next_workerw = w
                        break
                
                if next_workerw:
                    print(f"Используем следующее окно WorkerW: {next_workerw}")
                    return next_workerw
        
        # Если не нашли нужное окно WorkerW, используем Progman
        print("Не найдено подходящее окно WorkerW, используем Progman")
        return progman
    except Exception as e:
        print(f"Ошибка при поиске окна рабочего стола: {e}")
        traceback.print_exc()
        return None

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
        if desktop_hwnd:
            hwnd = int(self.winId())
            win32gui.SetParent(hwnd, desktop_hwnd)
            
            # Устанавливаем стиль окна
            style = WS_EX_LAYERED | WS_EX_NOACTIVATE
            win32gui.SetWindowLong(hwnd, GWL_EXSTYLE, style)
            
            # Показываем окно
            self.show()
            
            # Если указана позиция, устанавливаем её
            if position:
                self.move(position)
        else:
            print("ОШИБКА: Не удалось найти окно рабочего стола")
    
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
        
        # Расчет начального размера (не больше 800 пикселей по высоте)
        self.calculate_initial_size()
        
        # Настройка окна
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
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
                # Сохраняем текущее положение перед скрытием
                self.saved_position = self.pos()
                self.saved_visibility = self.isVisible()
                
                try:
                    # Создаем окно-обои с теми же параметрами
                    wallpaper = WallpaperWindow(
                        self.image_path, 
                        self.rotation,
                        self.opacity_value,  # Передаем текущую прозрачность
                        self.scale_factor,
                        self.pos()
                    )
                    wallpaper_windows.append(wallpaper)
                    self.hide()
                except Exception as e:
                    print(f"Ошибка при создании окна-обои: {e}")
                    traceback.print_exc()
            else:
                # Переключение в обычный режим
                # Окна-обои закрываются в глобальном обработчике toggle_windows_mode
                # Показываем текущее окно
                self.show()
                self.raise_()
        except Exception as e:
            print(f"Ошибка при изменении режима в окне: {e}")
            traceback.print_exc()
    
    def mousePressEvent(self, event):
        """Обработка нажатия кнопки мыши"""
        if event.button() == Qt.LeftButton:
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
    
    def mouseMoveEvent(self, event):
        # Проверяем, находимся ли у края окна для изменения размера
        if not self.drag_locked and not self.resizing:
            edge = self.detect_edge(event.pos())
            
            # Меняем курсор в зависимости от положения
            if edge == EDGE_LEFT or edge == EDGE_RIGHT:
                self.setCursor(Qt.SizeHorCursor)
            elif edge == EDGE_TOP or edge == EDGE_BOTTOM:
                self.setCursor(Qt.SizeVerCursor)
            elif edge == EDGE_TOPLEFT or edge == EDGE_BOTTOMRIGHT:
                self.setCursor(Qt.SizeFDiagCursor)
            elif edge == EDGE_TOPRIGHT or edge == EDGE_BOTTOMLEFT:
                self.setCursor(Qt.SizeBDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        
        # Изменение размера
        if not self.drag_locked and self.resizing and self.resize_edge != EDGE_NONE:
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
        
        # Перемещение окна
        if event.buttons() & Qt.LeftButton and self.drag_position is not None and not self.drag_locked:
            self.move(event.globalPos() - self.drag_position)
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
        global windows
        self.close()
        if self in windows:
            windows.remove(self)
    
    def toggle_lock(self):
        self.drag_locked = not self.drag_locked
        self.btn_lock.setText("🔓" if not self.drag_locked else "🔒")

def hotkey_pressed_create():
    hotkey_signals.create_window_signal.emit()

def hotkey_pressed_toggle_mode():
    global global_desktop_mode
    new_mode = not global_desktop_mode
    print(f"Нажата клавиша для переключения в режим: {'рабочего стола' if new_mode else 'обычный'}")
    hotkey_signals.toggle_all_windows_mode_signal.emit(new_mode)

def hotkey_pressed_paste_image():
    """Обработчик горячей клавиши для вставки изображения из буфера обмена"""
    print("Нажата клавиша для вставки изображения из буфера обмена")
    hotkey_signals.paste_image_signal.emit()

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
                
                # Создаем новое окно с изображением
                new_win = ImageWindow(temp_filename)
                new_win.show()
                windows.append(new_win)
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
    fname, _ = QFileDialog.getOpenFileName(
        None, "Выберите изображение", "", "Images (*.png *.xpm *.jpg *.bmp)"
    )
    if fname:
        new_win = ImageWindow(fname)
        new_win.show()
        windows.append(new_win)

def toggle_windows_mode(is_desktop_mode):
    """Обработчик глобального переключения режима"""
    global global_desktop_mode
    try:
        global_desktop_mode = is_desktop_mode
        
        if not is_desktop_mode:
            # Закрываем все окна-обои при выходе из режима рабочего стола
            for wp in wallpaper_windows[:]:
                try:
                    wp.close()
                except Exception as e:
                    print(f"Ошибка при закрытии окна-обои: {e}")
            
            wallpaper_windows.clear()
            print("Закрыты все окна-обои при выходе из режима рабочего стола")
        
    except Exception as e:
        print(f"Ошибка в глобальном обработчике toggle_windows_mode: {e}")
        traceback.print_exc()

def main():
    app = QApplication(sys.argv)
    
    # Подключаем сигналы к слотам
    hotkey_signals.create_window_signal.connect(create_new_window)
    hotkey_signals.toggle_all_windows_mode_signal.connect(toggle_windows_mode)
    hotkey_signals.paste_image_signal.connect(paste_image_from_clipboard)  # Новый сигнал
    
    # Добавляем горячие клавиши
    keyboard.add_hotkey('ctrl+alt+w', hotkey_pressed_create)
    keyboard.add_hotkey('ctrl+alt+d', hotkey_pressed_toggle_mode)
    keyboard.add_hotkey('ctrl+shift+alt+w', hotkey_pressed_paste_image)  # Новая горячая клавиша
    
    # Запускаем приложение
    exit_code = app.exec_()
    
    # Очищаем ресурсы
    keyboard.remove_hotkey('ctrl+alt+w')
    keyboard.remove_hotkey('ctrl+alt+d')
    keyboard.remove_hotkey('ctrl+shift+alt+w')  # Удаляем новую горячую клавишу
    
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
