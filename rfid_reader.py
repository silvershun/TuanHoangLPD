from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from dataclasses import dataclass
from typing import Optional, List, Callable
import logging

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RFIDConfig:
    """Cấu hình cho RFID Reader"""

    buffer_timeout: int = 100  # ms
    min_card_length: int = 4  # độ dài tối thiểu của mã thẻ
    max_card_length: int = 20  # độ dài tối đa của mã thẻ


class RFIDReader(QObject):
    # Signal phát khi đọc được thẻ
    card_read = pyqtSignal(str)
    # Signal phát khi có lỗi
    error_occurred = pyqtSignal(str)

    def __init__(self, config: RFIDConfig = None):
        super().__init__()
        self.config = config or RFIDConfig()
        self._buffer: List[str] = []
        self._is_running: bool = False
        self._setup_timer()

    def _setup_timer(self) -> None:
        """Khởi tạo timer cho buffer"""
        self._timer = QTimer()
        self._timer.timeout.connect(self._clear_buffer)
        self._timer.setInterval(self.config.buffer_timeout)

    def _validate_card(self, card_id: str) -> bool:
        """Kiểm tra tính hợp lệ của mã thẻ"""
        if not card_id.isalnum():
            return False
        if not (
            self.config.min_card_length <= len(card_id) <= self.config.max_card_length
        ):
            return False
        return True

    def _process_card(self, card_id: str) -> None:
        """Xử lý mã thẻ hợp lệ"""
        try:
            if self._validate_card(card_id):
                logger.info(f"RFID Card detected: {card_id}")
                self.card_read.emit(card_id)
            else:
                logger.warning(f"Invalid card format: {card_id}")
                self.error_occurred.emit(f"Invalid card format: {card_id}")
        except Exception as e:
            logger.error(f"Error processing card: {str(e)}")
            self.error_occurred.emit(f"Error processing card: {str(e)}")

    def _on_input(self, event) -> None:
        """Xử lý input từ event"""
        if not hasattr(event, "text"):
            return

        text = event.text()
        if text in ["\r", "\n"]:  # Enter key
            if self._buffer:
                card_id = "".join(self._buffer)
                self._process_card(card_id)
            self._clear_buffer()
        elif text.isalnum():
            if len(self._buffer) < self.config.max_card_length:
                self._buffer.append(text)
                self._timer.start()  # Reset timer mỗi khi có input mới

    def _clear_buffer(self) -> None:
        """Xóa buffer và dừng timer"""
        if self._buffer:
            logger.debug("Clearing input buffer due to timeout")
        self._buffer.clear()
        self._timer.stop()

    def start(self, callback: Optional[Callable[[str], None]] = None) -> bool:
        """Bắt đầu đọc thẻ RFID"""
        if self._is_running:
            logger.warning("RFID Reader is already running")
            return False

        try:
            if callback:
                self.card_read.connect(callback)
            self._is_running = True
            print("RFID Reader started")
            return True
        except Exception as e:
            logger.error(f"Error starting RFID Reader: {str(e)}")
            self.error_occurred.emit(f"Error starting RFID Reader: {str(e)}")
            return False

    def stop(self) -> None:
        """Dừng đọc thẻ RFID"""
        if not self._is_running:
            return

        try:
            self._timer.stop()
            self._is_running = False
            self._clear_buffer()
            logger.info("RFID Reader stopped")
        except Exception as e:
            logger.error(f"Error stopping RFID Reader: {str(e)}")
            self.error_occurred.emit(f"Error stopping RFID Reader: {str(e)}")

    def is_running(self) -> bool:
        """Kiểm tra trạng thái hoạt động"""
        return self._is_running

    def process_input(self, event) -> None:
        """Xử lý input từ event của QWidget"""
        if self._is_running:
            self._on_input(event)

    def cleanup(self) -> None:
        """Dọn dẹp resources"""
        self.stop()
        try:
            self.card_read.disconnect()
            self.error_occurred.disconnect()
        except:
            pass
