import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QFileDialog, QLabel, QMessageBox,
    QSplitter, QHBoxLayout, QProgressBar, QFrame, QComboBox
)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl
from PIL import Image
from pysstv.color import Robot36
import os
import tempfile

class EncodeThread(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    image_ready = pyqtSignal(np.ndarray)
    def __init__(self, input_image, output_wav):
        super().__init__()
        self.input_image = input_image
        self.output_wav = output_wav

    def run(self):
        try:
            self.encode_sstv_robot36(self.input_image, self.output_wav)
            self.progress.emit(100)
        except Exception as e:
            print(f"Ошибка кодирования: {e}")
        finally:
            self.finished.emit()

    def encode_sstv_robot36(self, input_image, output_wav):
        """Кодирует изображение в SSTV Robot 36 и сохраняет в WAV-файл."""
        # Открываем изображение
        image = Image.open(input_image)
        # Создаем SSTV-объект (добавляем параметр bits=16)
        sstv = Robot36(image.resize((320, 240)), 44100, 16)  # 44.1 кГц частота дискретизации, 16 бит, разрешение всегда 320х240
        # Генерируем WAV-файл
        sstv.write_wav(output_wav)
        print(f"✅ Файл сохранен: {output_wav}")
        # Отправляем сигнал с изображением
        resized_image = image.resize((600, 600)).convert("RGB")
        self.image_ready.emit(np.array(resized_image))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Robot 36 Encoder")
        self.setGeometry(100, 100, 625, 700)  # Увеличиваем размер окна

        # Основной контейнер
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Верхняя часть с кнопками и прогрессбаром
        self.top_layout = QHBoxLayout()
        self.open_button = QPushButton("Открыть Изображение")
        self.open_button.clicked.connect(self.open_image)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setRange(0, 100)
        self.image_selector = QComboBox()
        self.image_selector.currentIndexChanged.connect(self.select_image)
        self.image_selector.setEnabled(False)
        self.image_selector.setMinimumSize(300, 25)

        self.top_layout.addWidget(self.open_button)
        self.top_layout.addWidget(self.image_selector)
        self.top_layout.addWidget(self.progress_bar)

        self.layout.addLayout(self.top_layout)

        # Разделительная линия
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.HLine)
        self.separator.setFrameShadow(QFrame.Sunken)
        self.layout.addWidget(self.separator)

        # Метка для отображения изображения
        self.image_label = QLabel("Здесь будет отображаться изображение")
        self.image_label.setStyleSheet("border: 1px solid black;")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMaximumSize(600, 600)  # Ограничиваем максимальный размер метки
        self.layout.addWidget(self.image_label)

        # Кнопка воспроизведения/остановки
        self.play_stop_button = QPushButton("Воспроизвести")
        self.play_stop_button.hide()
        self.play_stop_button.clicked.connect(self.toggle_playback)
        self.layout.addWidget(self.play_stop_button)

        # Переменные состояния
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_image)
        self.encoded_images = []
        self.current_frame = 0
        self.is_playing = False  # Флаг состояния воспроизведения
        # Звуковые файлы для воспроизведения
        self.sound_files = []
        self.current_sound_index = 0
        self.media_player = QMediaPlayer()
        self.media_player.stateChanged.connect(self.on_media_state_changed)

    def open_image(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите изображение", "", "Images (*.png *.jpg *.jpeg);;All Files (*)", options=options)
        if file_path:
            # Создаем уникальное имя для WAV-файла
            temp_dir = tempfile.gettempdir()
            output_wav = os.path.join(temp_dir, f"sound_{len(self.encoded_images)}.wav")
            self.sound_files.append(output_wav)
            self.encode_thread = EncodeThread(file_path, output_wav)
            self.encode_thread.finished.connect(self.on_encode_finished)
            self.encode_thread.progress.connect(self.on_encode_progress)
            self.encode_thread.image_ready.connect(self.on_image_ready)
            self.encode_thread.start()
            self.image_selector.addItem(f"Изображение {len(self.encoded_images) + 1}")
            self.image_selector.setEnabled(True)


    def toggle_playback(self):
        """Переключает состояние воспроизведения/остановки."""
        if self.is_playing:
            self.stop_playback()
            self.play_stop_button.setText("Воспроизвести")
        else:
            self.start_playback()
            self.play_stop_button.setText("Остановить")

    def start_playback(self):
        """Запускает таймер для воспроизведения изображений."""

        if not self.encoded_images:
            QMessageBox.warning(self, "Предупреждение", "Сначала выберите изображение для кодирования.")
            return
        #self.timer.start(120)  # Обновление каждые 120 мс
        self.is_playing = True
        # Воспроизводим звук
        self.play_stop_button.setText("Остановить")
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(self.sound_files[self.current_sound_index])))
        self.media_player.play()


    def stop_playback(self):
        """Останавливает таймер воспроизведения."""
        #self.timer.stop()
        self.is_playing = False
        self.media_player.stop()

    def on_media_state_changed(self, state):
        """Обрабатывает изменение состояния воспроизведения."""
        if state == QMediaPlayer.StoppedState:
            self.stop_playback()

    def on_encode_finished(self):
        """Вызывается после завершения кодирования."""
        if self.encode_thread:
            self.encode_thread.quit()
            self.encode_thread.wait()
            self.encode_thread = None
        if self.encoded_images:
            #self.timer.start(120)  # Обновление каждые 120 мс
            self.is_playing = True
            self.play_stop_button.show()
            # Воспроизводим звук
            self.play_stop_button.setText("Остановить")
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(self.sound_files[self.current_sound_index])))
            self.media_player.play()

    def on_encode_progress(self, progress):
        """Обрабатывает прогресс кодирования."""
        self.progress_bar.setValue(progress)

    def on_image_ready(self, encoded_image):
        """Вызывается после загрузки изображения."""
        self.encoded_images.append(encoded_image)
        self.current_frame = len(self.encoded_images) - 1
        self.display_image(self.encoded_images[self.current_frame])

    def update_image(self):
        """Обновляет отображаемое изображение."""
        if self.encoded_images:
            self.current_frame = (self.current_frame + 1) % len(self.encoded_images)
            self.display_image(self.encoded_images[self.current_frame])

    def display_image(self, encoded_image):
        """Отображает изображение на форме."""
        if encoded_image is None:
            return
        decoded_image = Image.fromarray(encoded_image)
        qimage = QImage(decoded_image.tobytes(), decoded_image.size[0], decoded_image.size[1], QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        # Масштабируем изображение под текущий размер метки
        scaled_pixmap = pixmap.scaled(self.image_label.width(), self.image_label.height(), aspectRatioMode=Qt.KeepAspectRatio)
        self.image_label.setPixmap(scaled_pixmap)

    def select_image(self, index):
        """Выбор изображения из комбобокса."""
        if index >= 0 and index < len(self.encoded_images):
            self.current_frame = index
            self.display_image(self.encoded_images[self.current_frame])
            self.current_sound_index = index
            if self.is_playing:
                self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(self.sound_files[self.current_sound_index])))
                self.media_player.play()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())