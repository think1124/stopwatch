import sys
import os
import time
import base64
import tempfile
import threading
import traceback
import queue
import json
import subprocess
import requests
import pygetwindow as gw
from pynput import keyboard
from PyQt5.QtWidgets import QApplication, QWidget, QMenu, QAction, QMessageBox, QGridLayout, QLabel
from PyQt5.QtGui import QIcon, QImage, QPixmap, QFont, QColor, QPainter, QPen, QFontDatabase, QFontMetrics
from PyQt5.QtCore import Qt, QTimer, QRect
import cv2
import win32gui
import win32process
import psutil
import pywintypes

try:
    from multi_video_data import video_data_dict
    from font_data import font_base64
    from icon_data import icon_base64
except ImportError:
    video_data_dict = {}
    font_base64 = ""
    icon_base64 = ""

# ================== 버전 설정 ==================
CURRENT_VERSION = "0.9"
DISABLED_VIDEOS = ["Sunset Cat"] # 메뉴에서 비활성화할 영상 이름
# ============================================

BLOCK_CHECK_URL = "https://raw.githubusercontent.com/think1124/stopwatch/main/status.json"
VERSION_CHECK_URL = "https://raw.githubusercontent.com/think1124/stopwatch/main/version.json"

def check_block_status():
    try:
        response = requests.get(BLOCK_CHECK_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("is_blocked") is True
    except Exception:
        return False

def show_critical_error(exctype, value, tb):
    error_message = "".join(traceback.format_exception(exctype, value, tb))
    QMessageBox.critical(None, "치명적 오류 발생", f"프로그램 실행 중 오류가 발생했습니다.\n\n{error_message}")
    sys.exit(1)
sys.excepthook = show_critical_error

class KeyboardListener(threading.Thread):
    def __init__(self, output_queue, window_ref):
        super().__init__()
        self.daemon = True
        self.output_queue = output_queue
        self.window = window_ref
        self.listener = None

    def on_press(self, key):
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd: return
        if self.window.is_setting_target:
            if hwnd != self.window.winId(): self.output_queue.put(('set_target', hwnd))
        else:
            self.output_queue.put(('check_activity', hwnd))

    def run(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        self.listener.join()

    def stop(self):
        if self.listener: self.listener.stop()

class VideoStopwatch(QWidget):
    def __init__(self):
        super().__init__()
        self.save_file_path = os.path.join(tempfile.gettempdir(), "think_stopwatch_save.json")
        self.target_process_names = ["없음", "없음", "없음"]
        self.is_setting_target = False
        self.target_selection_index = -1
        self.video_paths = self.create_video_temp_files(video_data_dict)
        self.current_video_path = list(self.video_paths.values())[0] if self.video_paths else None
        self.temp_font_path = self.create_temp_file(font_base64, ".ttf")
        self.time_in_seconds = 0
        self.is_running = False
        self.current_pixmap = None
        self.current_grayscale_pixmap = None
        self.main_timer = QTimer(self)
        self.video_timer = QTimer(self)
        self.inactivity_timer = QTimer(self)
        self.queue_check_timer = QTimer(self)
        self.fade_timer = QTimer(self)
        self.is_fading = False
        self.fade_opacity = 1.0
        self.fade_direction = 0
        self.drag_position = None
        self.border_width = 8
        self.is_resizing = False
        self.aspect_ratio = 1920.0 / 1080.0
        self.resize_edges = {"left": False, "right": False, "top": False, "bottom": False}
        self.font_scale = 1.0
        self.base_stopwatch_size = 157
        self.base_date_size = 31
        self.base_time_size = 40
        self.icon_pixmap = QPixmap()
        self.cap = None

        self.initUI()
        self.initVideo()
        self.main_timer.timeout.connect(self.update_stopwatch)
        self.inactivity_timer.setSingleShot(True)
        self.inactivity_timer.timeout.connect(self.pause_due_to_inactivity)
        self.key_event_queue = queue.Queue()
        self.keyboard_listener = KeyboardListener(self.key_event_queue, self)
        self.keyboard_listener.start()
        self.queue_check_timer.timeout.connect(self.process_key_queue)
        self.queue_check_timer.start(50)
        self.fade_timer.timeout.connect(self.update_fade_effect)

    def initUI(self):
        self.setWindowTitle("GO"); self.resize(1440, 810)
        self.setMinimumSize(480, 270)
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMouseTracking(True)
        try:
            decoded_icon_data = base64.b64decode(icon_base64)
            self.icon_pixmap.loadFromData(decoded_icon_data)
            self.setWindowIcon(QIcon(self.icon_pixmap))
        except Exception:
            pass

        font_id = QFontDatabase.addApplicationFont(self.temp_font_path)
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        self.font_family = font_families[0] if font_families else "Arial"
        
        self.stopwatch_font = QFont(self.font_family); self.stopwatch_font.setWeight(62); self.stopwatch_font.setLetterSpacing(QFont.AbsoluteSpacing, -9); self.stopwatch_font.setStyleHint(QFont.Monospace); self.stopwatch_font.setHintingPreference(QFont.PreferFullHinting)
        self.date_font = QFont(self.font_family); self.date_font.setWeight(62); self.date_font.setLetterSpacing(QFont.AbsoluteSpacing, -0.1); self.date_font.setStyleHint(QFont.Monospace); self.date_font.setHintingPreference(QFont.PreferNoHinting)
        self.time_font = QFont(self.font_family); self.time_font.setWeight(62); self.time_font.setLetterSpacing(QFont.AbsoluteSpacing, -0.3); self.time_font.setStyleHint(QFont.Monospace); self.time_font.setHintingPreference(QFont.PreferNoHinting)
        self.update_font_sizes()
        self.show()

    def update_font_sizes(self):
        self.stopwatch_font.setPixelSize(int(self.base_stopwatch_size * self.font_scale))
        self.date_font.setPixelSize(int(self.base_date_size * self.font_scale))
        self.time_font.setPixelSize(int(self.base_time_size * self.font_scale))
        self.update()

    def change_font_size(self, scale):
        self.font_scale = scale
        self.update_font_sizes()

    def paintEvent(self, event):
        painter = QPainter(self); painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.HighQualityAntialiasing)
        if self.current_pixmap:
            painter.drawPixmap(self.rect(), self.current_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if self.current_grayscale_pixmap and self.fade_opacity > 0:
                painter.setOpacity(self.fade_opacity)
                painter.drawPixmap(self.rect(), self.current_grayscale_pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                painter.setOpacity(1.0)
        painter.setFont(self.stopwatch_font); painter.setPen(Qt.white); painter.drawText(self.rect(), Qt.AlignCenter, self.format_time(self.time_in_seconds))
        now = time.localtime(); date_str = time.strftime("%Y.%m.%d. %a", now).upper(); time_str = time.strftime("%H:%M:%S", now)
        RIGHT_MARGIN, BOTTOM_MARGIN = 140, 25
        painter.setFont(self.time_font); fm_time = QFontMetrics(self.time_font); time_rect = fm_time.boundingRect(time_str); time_x = self.width() - time_rect.width() - RIGHT_MARGIN; time_y = self.height() - BOTTOM_MARGIN
        painter.drawText(time_x, time_y, time_str)
        painter.setFont(self.date_font); fm_date = QFontMetrics(self.date_font); date_rect = fm_date.boundingRect(date_str); date_x = self.width() - date_rect.width() - RIGHT_MARGIN; date_y = time_y - time_rect.height() + 2
        painter.drawText(date_x, date_y, date_str)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        target_menu = menu.addMenu("타겟 창 설정")
        for i in range(3):
            action_text = f"타겟 {i+1} 설정 - {self.target_process_names[i]}"
            action = QAction(action_text, self)
            action.triggered.connect(lambda checked, index=i: self.start_target_selection(index))
            target_menu.addAction(action)
        target_menu.addSeparator()
        clear_targets_action = QAction("모든 타겟 초기화", self)
        clear_targets_action.triggered.connect(self.clear_targets)
        target_menu.addAction(clear_targets_action)

        load_action = QAction('불러오기', self); load_action.triggered.connect(self.load_last_time); menu.addAction(load_action)
        menu.addSeparator()
        background_menu = menu.addMenu("배경 영상 변경")
        if self.video_paths:
            for video_name in self.video_paths.keys():
                if video_name in DISABLED_VIDEOS:
                    continue # 비활성화된 영상은 메뉴에 추가하지 않고 건너뜁니다.
                
                action = QAction(video_name, self, checkable=True)
                if self.current_video_path == self.video_paths[video_name]: action.setChecked(True)
                action.triggered.connect(lambda checked, name=video_name: self.change_video(name))
                background_menu.addAction(action)
        menu.addSeparator()
        font_size_menu = menu.addMenu("폰트 크기 변경")
        for text, scale in [("아주 작게", 0.6), ("작게", 0.8), ("기본", 1.0), ("크게", 1.2), ("매우 크게", 1.4)]:
            action = QAction(text, self, checkable=True)
            if self.font_scale == scale: action.setChecked(True)
            action.triggered.connect(lambda checked, s=scale: self.change_font_size(s))
            font_size_menu.addAction(action)
        menu.addSeparator()
        update_action = QAction('업데이트', self); update_action.triggered.connect(self.check_for_updates); menu.addAction(update_action)
        menu.addSeparator()
        exit_action = QAction('종료', self); exit_action.triggered.connect(self.close); menu.addAction(exit_action)
        menu.addSeparator()
        version_action = QAction(f'v{CURRENT_VERSION}', self)
        version_action.setEnabled(False)
        menu.addAction(version_action)
        menu.exec_(self.mapToGlobal(event.pos()))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            self.resize_edges["left"] = pos.x() < self.border_width; self.resize_edges["right"] = pos.x() > self.width() - self.border_width
            self.resize_edges["top"] = pos.y() < self.border_width; self.resize_edges["bottom"] = pos.y() > self.height() - self.border_width
            self.is_resizing = any(self.resize_edges.values())
            if self.is_resizing: self.resize_start_pos = event.globalPos(); self.resize_start_geometry = self.geometry()
            else: self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if self.is_resizing:
                start_geom = self.resize_start_geometry; new_rect = QRect(start_geom); delta = event.globalPos() - self.resize_start_pos
                if self.resize_edges["right"]: new_rect.setWidth(start_geom.width() + delta.x())
                if self.resize_edges["bottom"]: new_rect.setHeight(start_geom.height() + delta.y())
                if self.resize_edges["left"]: new_rect.setLeft(start_geom.left() + delta.x())
                if self.resize_edges["top"]: new_rect.setTop(start_geom.top() + delta.y())
                width_changed, height_changed = self.resize_edges["left"] or self.resize_edges["right"], self.resize_edges["top"] or self.resize_edges["bottom"]
                if width_changed and not height_changed: new_rect.setHeight(int(new_rect.width() / self.aspect_ratio))
                elif height_changed and not width_changed: new_rect.setWidth(int(new_rect.height() * self.aspect_ratio))
                elif width_changed and height_changed:
                    if abs(delta.x()) > abs(delta.y()) * self.aspect_ratio: new_rect.setHeight(int(new_rect.width() / self.aspect_ratio))
                    else: new_rect.setWidth(int(new_rect.height() * self.aspect_ratio))
                if self.resize_edges["top"] and self.resize_edges["left"]: new_rect.moveTopLeft(start_geom.bottomRight() - new_rect.size())
                elif self.resize_edges["top"]: new_rect.moveTop(start_geom.bottom() - new_rect.height())
                elif self.resize_edges["left"]: new_rect.moveLeft(start_geom.right() - new_rect.width())
                if new_rect.width() >= self.minimumWidth() and new_rect.height() >= self.minimumHeight(): self.setGeometry(new_rect)
            elif self.drag_position: self.move(event.globalPos() - self.drag_position); event.accept()
        else:
            pos = event.pos(); on_left, on_right, on_top, on_bottom = pos.x() < self.border_width, pos.x() > self.width() - self.border_width, pos.y() < self.border_width, pos.y() > self.height() - self.border_width
            if (on_top and on_left) or (on_bottom and on_right): self.setCursor(Qt.SizeFDiagCursor)
            elif (on_top and on_right) or (on_bottom and on_left): self.setCursor(Qt.SizeBDiagCursor)
            elif on_left or on_right: self.setCursor(Qt.SizeHorCursor)
            elif on_top or on_bottom: self.setCursor(Qt.SizeVerCursor)
            else: self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        self.is_resizing = False; self.drag_position = None; self.resize_edges = {key: False for key in self.resize_edges}
    
    def _create_message_box(self, title, text):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.NoIcon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        
        grid_layout = msg_box.layout()
        if isinstance(grid_layout, QGridLayout):
            text_label = msg_box.findChild(QLabel, "qt_msgbox_label")
            if text_label:
                for i in range(grid_layout.count()):
                    item = grid_layout.itemAt(i)
                    if item and item.widget() == text_label:
                        grid_layout.takeAt(i)
                        grid_layout.addWidget(text_label, 0, 0, 1, grid_layout.columnCount())
                        break
        return msg_box

    def check_for_updates(self):
        try:
            headers = {'Cache-Control': 'no-cache'}
            response = requests.get(VERSION_CHECK_URL, headers=headers, timeout=5)
            response.raise_for_status()
            latest_info = response.json()
            latest_version_str = latest_info.get("version")

            current_version_tuple = tuple(map(int, (CURRENT_VERSION.split("."))))
            latest_version_tuple = tuple(map(int, (latest_version_str.split("."))))

            if latest_version_str and latest_version_tuple > current_version_tuple:
                msg_box = self._create_message_box("업데이트", f"{latest_version_str} 버전으로 업데이트합니다.")
                msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                msg_box.setDefaultButton(QMessageBox.Ok)
                reply = msg_box.exec_()
                
                if reply == QMessageBox.Ok:
                    self.start_update(latest_info)
            else:
                msg_box = self._create_message_box("업데이트", "최신 버전입니다.")
                msg_box.exec_()
                
        except Exception:
            msg_box = self._create_message_box("업데이트", "최신 버전을 확인하지 못했습니다.")
            msg_box.exec_()

    def cleanup(self):
        if hasattr(self, 'keyboard_listener'): self.keyboard_listener.stop()
        if self.cap:
            self.cap.release()
            
        temp_files_to_delete = list(getattr(self, 'video_paths', {}).values())
        if hasattr(self, 'temp_font_path') and self.temp_font_path: temp_files_to_delete.append(self.temp_font_path)
        for path in temp_files_to_delete:
            if path and os.path.exists(path):
                try: os.remove(path)
                except Exception: pass

    def start_fade(self, to_grayscale):
        if self.is_fading: return
        self.is_fading = True; self.fade_direction = 1 if to_grayscale else -1; self.fade_timer.start(20)

    def update_fade_effect(self):
        self.fade_opacity += 0.04 * self.fade_direction; self.fade_opacity = max(0.0, min(1.0, self.fade_opacity))
        if self.fade_opacity >= 1.0 or self.fade_opacity <= 0.0: self.is_fading = False; self.fade_direction = 0; self.fade_timer.stop()
        self.update()

    def pause_due_to_inactivity(self):
        if self.is_running: self.is_running = False; self.start_fade(to_grayscale=True); self.main_timer.stop()

    def format_time(self, seconds):
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def update_frame(self):
        if not self.cap or not self.cap.isOpened(): return
        
        ret, frame = self.cap.read()
        
        if ret:
            color_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = color_frame.shape
            self.current_pixmap = QPixmap.fromImage(QImage(color_frame.data, w, h, w * ch, QImage.Format_RGB888))

            gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_frame_rgb = cv2.cvtColor(gray_frame, cv2.COLOR_GRAY2RGB)
            self.current_grayscale_pixmap = QPixmap.fromImage(QImage(gray_frame_rgb.data, w, h, w * ch, QImage.Format_RGB888))
            
            if not self.is_fading: self.update()
        else:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def start_update(self, latest_info):
        try:
            updater_path = os.path.join(os.path.dirname(sys.executable), 'updater.py') if getattr(sys, 'frozen', False) else 'updater.py'
            
            if not os.path.exists(updater_path):
                 updater_url = "https://raw.githubusercontent.com/think1124/stopwatch/main/updater.py"
                 with requests.get(updater_url, stream=True) as r:
                     r.raise_for_status()
                     with open(updater_path, 'wb') as f:
                         for chunk in r.iter_content(chunk_size=8192): f.write(chunk)

            main_program_name = os.path.basename(sys.executable)
            subprocess.Popen([sys.executable, updater_path, main_program_name, latest_info['url']])
            self.close()
        except Exception as e:
            QMessageBox.critical(self, '업데이트 오류', f'업데이트 준비 중 오류가 발생했습니다.\n{e}')

    def create_temp_file(self, base64_data, suffix):
        try:
            if not base64_data: return None
            decoded_data = base64.b64decode(base64_data)
            temp_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False); temp_file.write(decoded_data); temp_file.close()
            return temp_file.name
        except Exception: return None

    def create_video_temp_files(self, data_dict):
        paths = {}
        if not data_dict: return paths
        for name, data in data_dict.items():
            path = self.create_temp_file(data, ".mp4")
            if path: paths[name] = path
        return paths

    def initVideo(self):
        if not self.current_video_path or not os.path.exists(self.current_video_path): return
        
        if self.cap: self.cap.release()
        self.cap = cv2.VideoCapture(self.current_video_path)
        
        if not self.cap.isOpened():
            QMessageBox.critical(self, "비디오 오류", f"비디오 파일을 열 수 없습니다:\n{os.path.basename(self.current_video_path)}")
            return
            
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        try: self.video_timer.timeout.disconnect()
        except TypeError: pass
        
        self.video_timer.timeout.connect(self.update_frame)
        self.video_timer.start(int(1000 / max(fps, 1)))

    def change_video(self, video_name):
        new_path = self.video_paths.get(video_name)
        if new_path and self.current_video_path != new_path: self.current_video_path = new_path; self.initVideo()

    def start_target_selection(self, target_index):
        self.is_setting_target = True
        self.target_selection_index = target_index
        msg_box = self._create_message_box("\u200b", f"타겟 {target_index + 1}으로 지정할 창을 활성화한 후, 해당 창에서 아무 키나 눌러주세요.")
        msg_box.exec_()
        
    def set_new_target(self, hwnd):
        if not self.is_setting_target or self.target_selection_index == -1: return
        
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid <= 0:
                new_process_name = "정보 없음"
            else:
                new_process_name = psutil.Process(pid).name()
        except (psutil.NoSuchProcess, psutil.AccessDenied, pywintypes.error):
            new_process_name = "정보 없음"
        
        self.target_process_names[self.target_selection_index] = new_process_name
        self.is_setting_target = False
        self.target_selection_index = -1
        
        text = f"타겟이 '{new_process_name}'(으)로 설정되었습니다." if new_process_name != "정보 없음" else "프로세스 정보를 가져올 수 없는 창입니다."
        msg_box = self._create_message_box("\u200b", text)
        msg_box.exec_()

    def clear_targets(self):
        self.target_process_names = ["없음", "없음", "없음"]
        msg_box = self._create_message_box("\u200b", "모든 타겟이 초기화되었습니다.")
        msg_box.exec_()

    def handle_activity(self, hwnd):
        if all(name == "없음" for name in self.target_process_names): return
        
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid <= 0: return
            
            current_process_name = psutil.Process(pid).name()
            
            is_target_active = any(target.lower() == current_process_name.lower() for target in self.target_process_names if target not in ["없음", "정보 없음"])

            if is_target_active:
                if not self.is_running: self.is_running = True; self.start_fade(to_grayscale=False); self.main_timer.start(1000)
                self.inactivity_timer.start(10000)
        except (psutil.NoSuchProcess, psutil.AccessDenied, pywintypes.error): pass

    def process_key_queue(self):
        try:
            while not self.key_event_queue.empty():
                event_type, hwnd = self.key_event_queue.get_nowait()
                if event_type == 'set_target' and self.is_setting_target: self.set_new_target(hwnd)
                elif event_type == 'check_activity': self.handle_activity(hwnd)
        except queue.Empty: pass

    def load_last_time(self):
        if not os.path.exists(self.save_file_path):
            msg_box = self._create_message_box("\u200b", "저장된 기록이 없습니다.")
            msg_box.exec_()
            return
        try:
            with open(self.save_file_path, 'r') as f: saved_data = json.load(f)
            if time.time() - saved_data.get('save_timestamp', 0) <= 14400:
                self.time_in_seconds = saved_data.get('last_time', 0); self.update()
                msg_box = self._create_message_box("\u200b", "기록을 불러왔습니다.")
            else:
                msg_box = self._create_message_box("\u200b", "4시간이 경과하여 기록을 불러오지 않았습니다.")
        except Exception:
            msg_box = self._create_message_box("\u200b", "기록을 불러오는 중 오류가 발생했습니다.")
        msg_box.exec_()
            
    def update_stopwatch(self): self.time_in_seconds += 1
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape: self.close()

    def closeEvent(self, e):
        try:
            with open(self.save_file_path, 'w') as f: json.dump({'last_time': self.time_in_seconds, 'save_timestamp': time.time()}, f)
        except Exception: pass
        self.cleanup(); e.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = VideoStopwatch()
    if check_block_status():
        QMessageBox.warning(None, "서비스 점검", "현재 서비스를 이용할 수 없습니다.")
        sys.exit()
    sys.exit(app.exec_())
