import sys
import os
import json
import threading
from datetime import datetime
from PyQt5.QtGui import QFont, QPixmap, QColor, QIntValidator, QPainter, QFontDatabase
from PyQt5.QtCore import Qt, QTimer, QSize, QPropertyAnimation, QUrl
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QMessageBox, QHBoxLayout,
    QProgressBar, QSpinBox, QFrame, QStyledItemDelegate,
    QListWidgetItem, QStyle, QGraphicsDropShadowEffect,
    QFileDialog, QSizePolicy
)
from playsound import playsound

CONFIG_FILE = "app_config.json"
DEFAULT_POMODORO_DURATION = 25 * 60
TARGET_DATE = datetime(2026, 6, 20, 0, 0, 0)
DEFAULT_TOTAL_QUESTION_TARGET = 5000
DEFAULT_INCREMENT_SOLVED_QUESTIONS = 500

FILE_SOURCE_RESOURCES = "resources_solved.json"
FILE_TOPIC_RESOURCES = "resources_topics.json"

COLOR_BACKGROUND = "#181A1B"
COLOR_CARD = "#212426"
COLOR_ACCENT = "#00C8FF"
COLOR_SECONDARY_ACCENT = "#FFD700"
COLOR_TEXT = "#F3F3F3"
COLOR_MUTED_TEXT = "#AAAAAA"
COLOR_BORDER = "#222"
COLOR_BUTTON_BG = "#23272E"
COLOR_BUTTON_TEXT = "#FFD700"
COLOR_BUTTON_HOVER = "#222"
COLOR_LIST_BG = "rgba(24,26,27,0.75)"
COLOR_WIDGET_BG = "rgba(30,30,30,0.75)"
COLOR_CARD_BG = "rgba(32,36,38,0.75)"

class BaseResource:
    def __init__(self, name: str, added_date: str = None):
        self.name = name
        self.added_date = added_date if added_date else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    def to_dict(self):
        return {"name": self.name, "added_date": self.added_date}
    @staticmethod
    def from_dict(data: dict):
        return BaseResource(data["name"], data["added_date"])

class Topic(BaseResource):
    pass

class SolvedResource(BaseResource):
    pass

class ResourceDataManager:
    def __init__(self, source_file: str, topic_file: str):
        self.source_file = source_file
        self.topic_file = topic_file
        self.solved_resources = self._load_resources(self.source_file, SolvedResource)
        self.topic_resources = self._load_resources(self.topic_file, Topic)
    def _load_resources(self, file_path: str, resource_class) -> list:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return [resource_class(item["name"], item["added_date"]) for item in data]
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                return []
        return []
    def save_resources(self):
        try:
            with open(self.source_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.solved_resources], f, ensure_ascii=False, indent=2)
            with open(self.topic_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.topic_resources], f, ensure_ascii=False, indent=2)
        except IOError as e:
            QMessageBox.critical(None, "Hata", f"Kaynak verileri kaydedilirken hata oluştu: {e}")
    def get_resources(self, resource_type: str) -> list:
        return self.topic_resources if resource_type == "topic" else self.solved_resources
    def add_resource(self, resource_type: str, resource_name: str) -> bool:
        resources = self.get_resources(resource_type)
        if resource_name.lower() in [r.name.lower() for r in resources]:
            return False
        resource_class = Topic if resource_type == "topic" else SolvedResource
        resources.append(resource_class(resource_name))
        self.save_resources()
        return True
    def remove_resource(self, resource_type: str, resource_name: str) -> bool:
        resources = self.get_resources(resource_type)
        original_len = len(resources)
        if resource_type == "topic":
            self.topic_resources[:] = [r for r in resources if r.name.lower() != resource_name.lower()]
        else:
            self.solved_resources[:] = [r for r in resources if r.name.lower() != resource_name.lower()]
        if len(self.get_resources(resource_type)) < original_len:
            self.save_resources()
            return True
        return False
    def clear_resources(self, resource_type: str):
        if resource_type == "topic":
            self.topic_resources.clear()
        else:
            self.solved_resources.clear()
        self.save_resources()

class ResourceItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        item_data: BaseResource = index.data(Qt.UserRole)
        is_topic = isinstance(item_data, Topic)
        if item_data:
            painter.save()
            if option.state & QStyle.State_Selected:
                painter.fillRect(option.rect, QColor(COLOR_ACCENT))
                text_color = QColor(COLOR_CARD)
                date_color = QColor(COLOR_CARD)
            else:
                painter.fillRect(option.rect, QColor(COLOR_CARD))
                text_color = QColor(COLOR_TEXT)
                date_color = QColor(COLOR_MUTED_TEXT)
            icon = "📝" if is_topic else "✅"
            text_rect = option.rect.adjusted(15, 5, -15, -5)
            font = painter.font()
            font.setFamily('Poppins')
            font.setPointSize(13)
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(text_color)
            painter.drawText(text_rect, Qt.AlignVCenter, f"{icon} {item_data.name}")
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(date_color)
            painter.drawText(text_rect, Qt.AlignRight | Qt.AlignBottom, item_data.added_date.split(' ')[0])
            painter.restore()
        else:
            super().paint(painter, option, index)
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 55)

class KaynakApp(QWidget):
    def __init__(self):
        super().__init__()
        self.bg_pixmap = None
        self._load_config()
        self._load_background()
        self.data_manager = ResourceDataManager(FILE_SOURCE_RESOURCES, FILE_TOPIC_RESOURCES)
        self.current_resource_type = "solved"
        self._setup_timer()
        self._setup_ui()
        self.list_resources(self.resource_list_solved, "solved")
        self.list_resources(self.resource_list_topic, "topic")
        self.update_day_counter()
        self.update_total_progress()
        self.update_daily_progress_label()
        self._timer_tick()
    def _load_background(self):
        self.bg_path = self.config.get("background_path", os.path.join("assets", "background_image.jpg")) if hasattr(self, 'config') else os.path.join("assets", "background_image.jpg")
        pixmap = QPixmap(self.bg_path)
        if not pixmap.isNull():
            self.bg_pixmap = pixmap
    def paintEvent(self, event):
        if self.bg_pixmap:
            painter = QPainter(self)
            scaled = self.bg_pixmap.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            painter.drawPixmap(0, 0, scaled)
        else:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(COLOR_BACKGROUND))
    def _load_config(self):
        self.pomodoro_duration = DEFAULT_POMODORO_DURATION
        self.total_target_question_count = DEFAULT_TOTAL_QUESTION_TARGET
        self.daily_questions = {}
        self.music_path = os.path.join("assets", "wake_up copy.wav")
        self.music_path = os.path.join("assets", "wake_up.mp3")
        self.bg_path = os.path.join("assets", "background_image.jpg")
        self.config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.config = config
                    self.pomodoro_duration = config.get("pomodoro_duration", DEFAULT_POMODORO_DURATION)
                    self.total_target_question_count = config.get("total_target_question_count", DEFAULT_TOTAL_QUESTION_TARGET)
                    self.daily_questions = config.get("daily_questions", {})
                    self.music_path = config.get("music_path", self.music_path)
                    self.bg_path = config.get("background_path", self.bg_path)
            except Exception as e:
                print(f"Error loading config: {e}. Using defaults.")
    def _save_config(self):
        config = {
            "pomodoro_duration": self.pomodoro_duration,
            "total_target_question_count": self.total_target_question_count,
            "daily_questions": self.daily_questions,
            "music_path": self.music_path,
            "background_path": self.bg_path
        }
        self.config = config
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except IOError as e:
            QMessageBox.critical(self, "Hata", f"Ayarlar kaydedilirken hata oluştu: {e}")
    def _update_total_target(self, value: int):
        self.total_target_question_count = value
        self._save_config()
        self.update_total_progress()
    def _get_today_date(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")
    def get_today_solved_count(self) -> int:
        today = self._get_today_date()
        return self.daily_questions.get(today, 0)
    def update_daily_progress_label(self):
        today_count = self.get_today_solved_count()
        self.daily_progress_label.setText(
            f"<span style='color:{COLOR_SECONDARY_ACCENT}; font-size:20px; font-weight:bold;'>{today_count}</span> "
            f"<span style='color:{COLOR_TEXT}; font-size:16px;'>Soru</span>"
        )
        self.daily_progress_label.setAlignment(Qt.AlignCenter)
    def _setup_timer(self):
        self.pomodoro_timer = QTimer(self)
        self.pomodoro_timer.timeout.connect(self._timer_tick)
        self.current_time_left = self.pomodoro_duration
        self.is_timer_running = False
    def _create_button(self, text: str, handler) -> QPushButton:
        btn = QPushButton(text)
        btn.clicked.connect(handler)
        btn.setFont(QFont("Poppins", 12, QFont.Bold))
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setColor(QColor(COLOR_ACCENT))
        shadow.setOffset(0, 0)
        btn.setGraphicsEffect(shadow)
        return btn
    def _create_label(self, text: str, size=12, bold=True) -> QLabel:
        label = QLabel(text)
        f = QFont("Poppins", size)
        f.setBold(bold)
        label.setFont(f)
        label.setStyleSheet(f"color: {COLOR_TEXT};")
        return label
    def _update_pomodoro_duration(self, seconds: int):
        self.pomodoro_duration = seconds
        self._save_config()
        if not self.is_timer_running:
            self.current_time_left = self.pomodoro_duration
            self._timer_tick()
    def select_background(self):
        path, _ = QFileDialog.getOpenFileName(self, "Arka Plan Resmi Seç", "", "Resimler (*.jpg *.png *.jpeg *.bmp)")
        if path:
            self.bg_path = path
            self._save_config()
            self._load_background()
            self.update()
            QMessageBox.information(self, "Başarılı", "Arka plan resmi başarıyla değiştirildi.")
    def play_alarm_sound(self):
        # playsound thread ile çağrılır, böylece GUI donmaz
        try:
            threading.Thread(target=playsound, args=(self.music_path,), daemon=True).start()
        except Exception as e:
            print("Ses çalınamadı:", e)
    def _setup_ui(self):
        QFontDatabase.addApplicationFont("assets/Poppins-Regular.ttf")
        QFontDatabase.addApplicationFont("assets/Poppins-Bold.ttf")
        self.setObjectName("KaynakApp")
        self.setStyleSheet(f"""
            QWidget {{
                color: {COLOR_TEXT};
                font-family: 'Poppins', 'Inter', 'Segoe UI', sans-serif;
                background: transparent;
            }}
            QLineEdit, QSpinBox {{
                background-color: {COLOR_WIDGET_BG};
                border: 1px solid {COLOR_BORDER}; border-radius: 12px;
                padding: 12px; color: {COLOR_TEXT}; font-size: 16px;
            }}
            QListWidget {{
                background-color: {COLOR_LIST_BG};
                border: 1px solid {COLOR_BORDER}; border-radius: 15px; padding: 0px;
                color: {COLOR_TEXT};
            }}
            QFrame#cardFrame {{
                background-color: {COLOR_CARD_BG};
                border-radius: 20px; padding: 20px; border: 1px solid {COLOR_BORDER};
            }}
            QLabel {{
                color: {COLOR_TEXT};
            }}
            QPushButton {{
                background-color: {COLOR_BUTTON_BG};
                color: {COLOR_BUTTON_TEXT};
                border-radius: 9px;
                padding: 11px 20px;
                font-weight: 700;
                font-size: 15px;
                transition: background 0.25s, color 0.25s;
            }}
            QPushButton:hover {{
                background-color: {COLOR_BUTTON_HOVER};
                color: {COLOR_ACCENT};
            }}
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        header_frame = QFrame()
        header_frame.setObjectName("cardFrame")
        header_layout = QHBoxLayout(header_frame)
        self.image_label = QLabel()
        try:
            pixmap = QPixmap(self.bg_path).scaled(200, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_label.setPixmap(pixmap)
        except Exception:
            self.image_label.setText("🏛️ Ankara Tıp")
            self.image_label.setFont(QFont("Poppins", 16, QFont.Bold))
            self.image_label.setStyleSheet(f"color: {COLOR_SECONDARY_ACCENT}; padding: 10px; border: 1px dashed {COLOR_MUTED_TEXT}; border-radius: 10px;")
        header_layout.addWidget(self.image_label)
        title_label = QLabel("🎯 TOPLAM HEDEF TAKİBİ")
        title_label.setFont(QFont("Poppins", 26, QFont.ExtraBold))
        title_label.setStyleSheet(f"color: {COLOR_SECONDARY_ACCENT};")
        title_label.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title_label, 1)
        main_layout.addWidget(header_frame)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLOR_CARD_BG};
                color: {COLOR_TEXT};
                border-radius: 8px;
                height: 26px;
                text-align: center;
                font-size: 16px;
                font-weight: bold;
            }}
            QProgressBar::chunk {{
                background-color: {COLOR_ACCENT};
                border-radius: 8px;
            }}
        """)
        main_layout.addWidget(self.progress_bar)
        top_section_layout = QHBoxLayout()
        # --- Sol Kart (Günlük Takip + Genel Ayarlar) ---
        target_card = QFrame()
        target_card.setObjectName("cardFrame")
        target_layout = QVBoxLayout(target_card)
        target_layout.setSpacing(10)
        daily_input_layout = QHBoxLayout()
        daily_card = QFrame()
        daily_card.setObjectName("cardFrame")
        daily_card.setStyleSheet(f"QFrame#cardFrame {{ border: 2px solid {COLOR_SECONDARY_ACCENT}; background:{COLOR_CARD_BG}; }}")
        daily_layout = QVBoxLayout(daily_card)
        daily_layout.addWidget(self._create_label("✏️ BUGÜN ÇÖZÜLEN SORU:", 13))
        self.daily_progress_label = QLabel()
        daily_layout.addWidget(self.daily_progress_label)
        daily_input_layout.addWidget(daily_card)
        self.daily_question_input = QLineEdit()
        self.daily_question_input.setPlaceholderText("Bugün Çözülen Soru Sayısı")
        self.daily_question_input.setValidator(QIntValidator(1, 99999))
        daily_input_layout.addWidget(self.daily_question_input)
        add_daily_btn = self._create_button("EKLE", self.add_daily_questions)
        add_daily_btn.setStyleSheet(f"background-color: {COLOR_SECONDARY_ACCENT}; color: #222; font-weight: 900; font-size:18px;")
        daily_input_layout.addWidget(add_daily_btn)
        target_layout.addLayout(daily_input_layout)
        target_layout.addStretch()
        target_layout.addWidget(self._create_label("📈 Genel Soru Hedefi:", 12))
        self.total_target_spinbox = QSpinBox()
        self.total_target_spinbox.setRange(1, 999999)
        self.total_target_spinbox.setValue(self.total_target_question_count)
        self.total_target_spinbox.valueChanged.connect(self._update_total_target)
        target_layout.addWidget(self.total_target_spinbox)
        target_layout.addWidget(self._create_label("⏳ Pomodoro Süresi (dk):", 12))
        self.pomodoro_duration_spinbox = QSpinBox()
        self.pomodoro_duration_spinbox.setRange(1, 60)
        self.pomodoro_duration_spinbox.setValue(self.pomodoro_duration // 60)
        self.pomodoro_duration_spinbox.valueChanged.connect(lambda v: self._update_pomodoro_duration(v * 60))
        target_layout.addWidget(self.pomodoro_duration_spinbox)
        # --- Sadece Arka Plan Seçim Butonu ---
        select_box = QFrame()
        select_box.setObjectName("cardFrame")
        select_box.setStyleSheet("background: transparent; border: none;")
        select_box_layout = QVBoxLayout(select_box)
        select_box_layout.setAlignment(Qt.AlignCenter)
        select_box_layout.setSpacing(20)
        select_bg_btn = self._create_button("Arka Plan Seç", self.select_background)
        select_bg_btn.setMinimumWidth(220)
        select_bg_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        select_bg_btn.setStyleSheet(
            "background-color: #00C8FF; color: #121212; font-weight: bold; font-size: 18px;"
            "border-radius: 15px; padding: 16px 0;")
        select_box_layout.addWidget(select_bg_btn, alignment=Qt.AlignCenter)
        target_layout.addStretch()
        target_layout.addWidget(select_box, alignment=Qt.AlignCenter)
        target_layout.addStretch()
        # ---
        top_section_layout.addWidget(target_card, 2)
        # --- Pomodoro Kartı ---
        timer_card = QFrame()
        timer_card.setObjectName("cardFrame")
        timer_layout = QVBoxLayout(timer_card)
        timer_layout.setSpacing(10)
        timer_layout.setAlignment(Qt.AlignCenter)
        self.timer_label = QLabel("⏱️ 25:00")
        self.timer_label.setFont(QFont("Poppins", 40, QFont.ExtraBold))
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setStyleSheet(f"color: {COLOR_ACCENT}; padding: 10px;")
        timer_layout.addWidget(self.timer_label)
        self.start_timer_btn = self._create_button("ODAKLANMAYA BAŞLA", self.start_pomodoro_timer)
        timer_layout.addWidget(self.start_timer_btn)
        control_btn_layout = QHBoxLayout()
        self.stop_timer_btn = self._create_button("DURAKLAT", self.stop_pomodoro_timer)
        self.stop_timer_btn.setEnabled(False)
        control_btn_layout.addWidget(self.stop_timer_btn)
        self.reset_timer_btn = self._create_button("SIFIRLA", self.reset_pomodoro_timer)
        self.reset_timer_btn.setEnabled(False)
        control_btn_layout.addWidget(self.reset_timer_btn)
        timer_layout.addLayout(control_btn_layout)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setColor(QColor(COLOR_ACCENT))
        shadow.setOffset(0, 0)
        self.timer_label.setGraphicsEffect(shadow)
        top_section_layout.addWidget(timer_card, 1)
        # --- Gün Sayacı Kartı ---
        day_counter_card = QFrame()
        day_counter_card.setObjectName("cardFrame")
        day_counter_layout = QVBoxLayout(day_counter_card)
        day_counter_layout.setAlignment(Qt.AlignCenter)
        self.remaining_days_label = QLabel("")
        self.remaining_days_label.setAlignment(Qt.AlignCenter)
        self.remaining_days_label.setFont(QFont("Poppins", 13, QFont.Bold))
        day_counter_layout.addWidget(self.remaining_days_label)
        top_section_layout.addWidget(day_counter_card, 1)
        main_layout.addLayout(top_section_layout)
        # --- Kaynak Listeleri (Alt Kısım) ---
        lists_layout = QHBoxLayout()
        solved_list_widget = QWidget()
        solved_list_layout = QVBoxLayout(solved_list_widget)
        solved_list_layout.setContentsMargins(0, 0, 0, 0)
        solved_list_layout.addWidget(self._create_list_header("✅ ÇÖZÜLEN KAYNAKLAR", "solved"))
        self.resource_name_input_solved = QLineEdit()
        self.resource_name_input_solved.setPlaceholderText(f"Çözülen Kaynak Adı (Eklendiğinde +{DEFAULT_INCREMENT_SOLVED_QUESTIONS} Soru)")
        self.resource_name_input_solved.returnPressed.connect(lambda: self.add_resource("solved"))
        solved_list_layout.addWidget(self.resource_name_input_solved)
        self.resource_list_solved = QListWidget()
        self.resource_list_solved.setItemDelegate(ResourceItemDelegate(self.resource_list_solved))
        # BULANIKLIK KALDIRILDI
        # blur = QGraphicsBlurEffect()
        # blur.setBlurRadius(8)
        # self.resource_list_solved.setGraphicsEffect(blur)
        solved_list_layout.addWidget(self.resource_list_solved)
        solved_list_layout.addWidget(self._create_action_buttons("solved"))
        lists_layout.addWidget(solved_list_widget)
        topic_list_widget = QWidget()
        topic_list_layout = QVBoxLayout(topic_list_widget)
        topic_list_layout.setContentsMargins(0, 0, 0, 0)
        topic_list_layout.addWidget(self._create_list_header("📝 ÇALIŞILMASI GEREKEN KONULAR", "topic"))
        self.resource_name_input_topic = QLineEdit()
        self.resource_name_input_topic.setPlaceholderText("Konu Adı (örn: Sinir Sistemi, Türev)")
        self.resource_name_input_topic.returnPressed.connect(lambda: self.add_resource("topic"))
        topic_list_layout.addWidget(self.resource_name_input_topic)
        self.resource_list_topic = QListWidget()
        self.resource_list_topic.setItemDelegate(ResourceItemDelegate(self.resource_list_topic))
        # BULANIKLIK KALDIRILDI
        # blur2 = QGraphicsBlurEffect()
        # blur2.setBlurRadius(8)
        # self.resource_list_topic.setGraphicsEffect(blur2)
        topic_list_layout.addWidget(self.resource_list_topic)
        topic_list_layout.addWidget(self._create_action_buttons("topic"))
        lists_layout.addWidget(topic_list_widget)
        main_layout.addLayout(lists_layout)
        main_layout.addStretch()
    def _create_list_header(self, text: str, resource_type: str) -> QWidget:
        header_widget = QWidget()
        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(0, 0, 0, 5)
        label = QLabel(text)
        label.setFont(QFont("Poppins", 15, QFont.Bold))
        label.setStyleSheet(f"color: {COLOR_ACCENT};")
        layout.addWidget(label)
        layout.addStretch()
        clear_btn = QPushButton("Temizle")
        clear_btn.setStyleSheet(f"""
            QPushButton {{ background-color: {COLOR_CARD_BG}; color: {COLOR_MUTED_TEXT}; border: 1px solid {COLOR_MUTED_TEXT}; border-radius: 8px; padding: 5px 10px; font-size: 13px; font-weight: bold; }}
            QPushButton:hover {{ background-color: #2a2a2a; color: {COLOR_TEXT}; }}
        """)
        clear_btn.clicked.connect(lambda: self.clear_all_resources(resource_type))
        layout.addWidget(clear_btn)
        return header_widget
    def _create_action_buttons(self, resource_type: str) -> QWidget:
        button_widget = QWidget()
        layout = QHBoxLayout(button_widget)
        layout.setContentsMargins(0, 5, 0, 0)
        remove_btn = QPushButton("SEÇİLİ ÖĞEYİ SİL")
        remove_btn.setStyleSheet(f"QPushButton {{ background-color: #A00000; color: {COLOR_TEXT}; border-radius: 8px; padding: 10px; font-weight: 700; font-size: 14px; min-height: 33px;}}")
        remove_btn.clicked.connect(lambda: self.remove_selected_resource(resource_type))
        layout.addWidget(remove_btn)
        return button_widget
    def get_list_widget(self, resource_type: str) -> QListWidget:
        return self.resource_list_topic if resource_type == "topic" else self.resource_list_solved
    def get_input_widget(self, resource_type: str) -> QLineEdit:
        return self.resource_name_input_topic if resource_type == "topic" else self.resource_name_input_solved
    def add_resource(self, resource_type: str):
        input_widget = self.get_input_widget(resource_type)
        resource_name = input_widget.text().strip()
        if not resource_name:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir isim girin.")
            return
        if self.data_manager.add_resource(resource_type, resource_name):
            if resource_type == "solved":
                QMessageBox.information(self, "Başarılı", f"'{resource_name}' eklendi ve toplam soru adedinize {DEFAULT_INCREMENT_SOLVED_QUESTIONS} soru eklendi.")
            self.list_resources(self.get_list_widget(resource_type), resource_type)
            input_widget.clear()
            self.check_celebration()
        else:
            QMessageBox.information(self, "Bilgi", f"'{resource_name}' zaten eklenmiş.")
    def remove_selected_resource(self, resource_type: str):
        list_widget = self.get_list_widget(resource_type)
        selected_items = list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen listeden bir öğe seçin.")
            return
        item_to_remove = selected_items[0]
        resource_obj: BaseResource = item_to_remove.data(Qt.UserRole)
        if QMessageBox.question(self, "Silme Onayı",
                                 f"'{resource_obj.name}' silinecek. Emin misiniz?",
                                 QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self.data_manager.remove_resource(resource_type, resource_obj.name):
                self.list_resources(list_widget, resource_type)
            else:
                QMessageBox.warning(self, "Hata", "Öğe silinirken bir sorun oluştu.")
    def clear_all_resources(self, resource_type: str):
        list_name = "KONU" if resource_type == "topic" else "KAYNAK"
        if QMessageBox.question(self, "Listeyi Temizle",
                                 f"Tüm '{list_name}' listesini silmek istediğinize emin misiniz?",
                                 QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.data_manager.clear_resources(resource_type)
            self.list_resources(self.get_list_widget(resource_type), resource_type)
    def list_resources(self, list_widget: QListWidget, resource_type: str):
        list_widget.clear()
        current_resources = self.data_manager.get_resources(resource_type)
        current_resources.sort(key=lambda r: r.added_date, reverse=True)
        for resource in current_resources:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, resource)
            list_widget.addItem(item)
        list_widget.updateGeometries()
    def add_daily_questions(self):
        try:
            questions_to_add = int(self.daily_question_input.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Uyarı", "Lütfen geçerli bir soru sayısı girin (örneğin: 250).")
            return
        if questions_to_add <= 0:
            QMessageBox.warning(self, "Uyarı", "Sıfırdan büyük bir sayı girmelisiniz.")
            return
        today = self._get_today_date()
        current_today_count = self.daily_questions.get(today, 0)
        self.daily_questions[today] = current_today_count + questions_to_add
        self._save_config()
        self.update_daily_progress_label()
        QMessageBox.information(self, "Başarılı", f"Bugün çözülen soru sayınıza {questions_to_add} eklendi.")
        self.daily_question_input.clear()
        self.check_celebration()
    def update_total_progress(self):
        solved = sum(self.daily_questions.values())
        target = self.total_target_question_count
        progress_percentage = int((solved / target) * 100) if target > 0 else 0
        self.progress_bar.setValue(min(progress_percentage, 100))
        if solved >= target and target > 0:
            self.progress_bar.setFormat(f"HEDEF TAMAMLANDI! 🎉 ({solved} / {target})")
            self.show_celebration()
        else:
            self.progress_bar.setFormat(f"Genel İlerleme: {solved} / {target} Soru - %{min(progress_percentage, 100)}")
    def start_pomodoro_timer(self):
        if not self.is_timer_running:
            if self.current_time_left <= 0:
                self.current_time_left = self.pomodoro_duration
            self.pomodoro_timer.start(1000)
            self.is_timer_running = True
            self.start_timer_btn.setEnabled(False)
            self.stop_timer_btn.setEnabled(True)
            self.reset_timer_btn.setEnabled(False)
            self.start_timer_btn.setText("ODAKLANIYOR...")
            self.stop_timer_btn.setText("DURAKLAT")
            self._timer_tick()
    def stop_pomodoro_timer(self):
        if self.is_timer_running:
            self.pomodoro_timer.stop()
            self.is_timer_running = False
            self.start_timer_btn.setEnabled(True)
            self.stop_timer_btn.setEnabled(False)
            self.reset_timer_btn.setEnabled(True)
            self.start_timer_btn.setText("DEVAM ET")
            self.stop_timer_btn.setText("DURAKLADI")
            self._timer_tick()
    def reset_pomodoro_timer(self):
        self.pomodoro_timer.stop()
        self.is_timer_running = False
        self.current_time_left = self.pomodoro_duration
        self._timer_tick()
        self.start_timer_btn.setEnabled(True)
        self.stop_timer_btn.setEnabled(False)
        self.reset_timer_btn.setEnabled(False)
        self.start_timer_btn.setText("ODAKLANMAYA BAŞLA")
        self.timer_label.setStyleSheet(f"color: {COLOR_ACCENT}; padding: 10px;")
    def _timer_tick(self):
        if self.is_timer_running:
            self.current_time_left -= 1
        minutes, seconds = divmod(max(0, self.current_time_left), 60)
        current_color = COLOR_ACCENT
        if self.current_time_left < 60 and self.current_time_left > 0:
            current_color = COLOR_SECONDARY_ACCENT
        self.timer_label.setText(f"⏱️ {minutes:02d}:{seconds:02d}")
        self.timer_label.setStyleSheet(f"color: {current_color}; padding: 10px;")
        if self.current_time_left <= 0 and self.is_timer_running:
            self.pomodoro_timer.stop()
            self.is_timer_running = False
            self.start_timer_btn.setEnabled(True)
            self.stop_timer_btn.setEnabled(False)
            self.reset_timer_btn.setEnabled(True)
            self.timer_label.setText("⏱️ MOLA ZAMANI!")
            self.timer_label.setStyleSheet(f"color: {COLOR_SECONDARY_ACCENT}; padding: 10px;")
            self.start_timer_btn.setText("MOLA BİTTİ, TEKRAR BAŞLA")
            self.play_alarm_sound()
            QMessageBox.information(self, "Süre Bitti", f"{self.pomodoro_duration // 60} dakikalık odaklanma süren doldu! Mola ver. 🔔")
    def update_day_counter(self):
        now = datetime.now()
        time_difference = TARGET_DATE - now
        if time_difference.total_seconds() <= 0:
            self.remaining_days_label.setText(f"<span style='color:{COLOR_SECONDARY_ACCENT}; font-size:18px; font-weight:bold;'>🎉 HEDEF TARİH GEÇTİ! 🎉</span>")
            return
        days = time_difference.days
        hours = time_difference.seconds // 3600
        self.remaining_days_label.setText(
            f"<span style='color:{COLOR_MUTED_TEXT}; font-size:14px;'>🗓️ Hedef Tarihe Kalan:</span><br>"
            f"<span style='color:{COLOR_ACCENT}; font-size:24px; font-weight:bold;'>{days}</span> <span style='color:{COLOR_TEXT}; font-size:16px;'>Gün</span> "
            f"<span style='color:{COLOR_ACCENT}; font-size:24px; font-weight:bold;'>{hours}</span> <span style='color:{COLOR_TEXT}; font-size:16px;'>Saat</span>"
        )
        self.remaining_days_label.setFont(QFont("Poppins", 13, QFont.Bold))
        QTimer.singleShot(60000, self.update_day_counter)
    def closeEvent(self, event):
        self._save_config()
        super().closeEvent(event)
    def show_celebration(self):
        label = QLabel("🎉", self)
        label.setStyleSheet("font-size: 90px; background: transparent;")
        label.setAttribute(Qt.WA_TranslucentBackground, True)
        label.move(self.width()//2-45, self.height()//2-45)
        label.raise_()
        label.show()
        anim = QPropertyAnimation(label, b"windowOpacity")
        anim.setDuration(1500)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.finished.connect(label.deleteLater)
        anim.start()
    def check_celebration(self):
        solved = sum(self.daily_questions.values())
        if solved >= self.total_target_question_count > 0:
            self.show_celebration()

if __name__ == "__main__":
    if not os.path.exists("assets"):
        os.makedirs("assets")
        print("UYARI: 'assets' klasörü oluşturuldu. Görselleri (örn: background_image.jpg, Poppins-Regular.ttf, Poppins-Bold.ttf, wake_up.mp3) buraya ekleyin.")
    app = QApplication(sys.argv)
    app.setFont(QFont('Poppins', 11))
    window = KaynakApp()
    window.showMaximized()
    sys.exit(app.exec_())