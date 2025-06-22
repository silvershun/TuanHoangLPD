import warnings

from src import DEVICE_CAMERA
# from src import DEVICE_CAMERA
warnings.filterwarnings('ignore')

import cv2
import numpy as np
import easyocr
import re
import threading
import time
import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from PyQt5.QtGui import QImage, QPixmap

# Cấu hình logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CameraConfig:
    """Cấu hình camera"""
    FRAME_WIDTH: int = 640
    FRAME_HEIGHT: int = 480  
    FPS: int = 30
    CAMERA_INDEX: int = DEVICE_CAMERA
    OCR_CONFIDENCE: float = 0.5
    CAPTURE_DELAY: float = 0.01
    PLATE_READ_DELAY: float = 0.1
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0
    MAX_CONSECUTIVE_ERRORS: int = 5

class Camera:
    def __init__(self, config: CameraConfig = None):
        """Khởi tạo Camera instance với config tùy chọn"""
        self.config = config or CameraConfig()
        self.cap = None
        self.threads = {}
        self._setup_locks()
        try:
            self._init_system()
        except Exception as e:
            print(f"Lỗi khởi tạo camera: {str(e)}")
            self.cleanup()
            raise

    def _setup_locks(self) -> None:
        """Khởi tạo locks và shared resources"""
        self._locks = {
            "frame": threading.Lock(),
            "plate": threading.Lock()
        }
        self._shared = {
            "frame": None,
            "plate": None,
            "running": True
        }

    def _init_system(self) -> None:
        """Khởi tạo toàn bộ hệ thống camera"""
        try:
            self._init_camera_with_retry()
            
            self._init_ocr()
            
            self._start_threads()
            
        except Exception as e:
            print(f"Lỗi khởi tạo camera system: {str(e)}")
            self.cleanup()
            raise

    def _init_camera_with_retry(self) -> None:
        """Khởi tạo camera với retry mechanism"""
        for attempt in range(self.config.MAX_RETRIES):
            try:
                print(f"Thử kết nối camera lần {attempt + 1}/{self.config.MAX_RETRIES}")
                self.cap = cv2.VideoCapture(self.config.CAMERA_INDEX)
                
                if not self.cap.isOpened():
                    raise RuntimeError("Không thể mở camera")
                
                self._configure_camera()
                self._check_camera_working()
                return
                
            except Exception as e:
                print(f"Lần thử {attempt + 1} thất bại: {str(e)}")
                if self.cap:
                    self.cap.release()
                    self.cap = None
                if attempt < self.config.MAX_RETRIES - 1:
                    time.sleep(self.config.RETRY_DELAY)
                    
        raise RuntimeError(f"Không thể kết nối camera sau {self.config.MAX_RETRIES} lần thử")

    def _configure_camera(self) -> None:
        """Cấu hình thông số camera"""
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, self.config.FPS)

    def _check_camera_working(self) -> None:
        """Kiểm tra camera có hoạt động không"""
        ret, frame = self.cap.read()
        if not ret or frame is None:
            raise RuntimeError("Không thể đọc frame từ camera")

    def _init_ocr(self) -> None:
        """Khởi tạo OCR reader"""
        try:
            self.reader = easyocr.Reader(['en'])
        except Exception as e:
            raise

    def _start_threads(self) -> None:
        """Khởi tạo và start worker threads"""
        self.threads = {
            "capture": threading.Thread(target=self._capture_thread, daemon=True),
            "plate": threading.Thread(target=self._read_plate_thread, daemon=True)
        }
        
        for name, thread in self.threads.items():
            print(f"Starting {name} thread...")
            thread.start()

    def _safe_get(self, key: str, lock_name: str) -> any:
        """Thread-safe getter cho shared resources"""
        with self._locks[lock_name]:
            return self._shared[key]

    def _safe_set(self, key: str, value: any, lock_name: str) -> None:
        """Thread-safe setter cho shared resources"""
        with self._locks[lock_name]:
            self._shared[key] = value

    def _capture_thread(self) -> None:
        """Worker thread cho việc đọc frame từ camera"""
        consecutive_errors = 0
        
        while self._safe_get("running", "frame"):
            try:
                if not self.cap or not self.cap.isOpened():
                    raise RuntimeError("Camera không khả dụng")
                    
                ret, frame = self.cap.read()
                if not ret or frame is None:
                    consecutive_errors += 1
                    logger.warning(f"Lỗi đọc frame: {consecutive_errors}/{self.config.MAX_CONSECUTIVE_ERRORS}")
                    
                    if consecutive_errors >= self.config.MAX_CONSECUTIVE_ERRORS:
                        break
                        
                    time.sleep(0.1)
                    continue
                    
                consecutive_errors = 0
                self._safe_set("frame", frame, "frame")
                
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= self.config.MAX_CONSECUTIVE_ERRORS:
                    break
                    
            time.sleep(self.config.CAPTURE_DELAY)

    def _process_image(self, frame: np.ndarray) -> np.ndarray:
        """Xử lý ảnh trước OCR"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        return clahe.apply(gray)

    def _process_plate_text(self, text: str, conf: float) -> Optional[str]:
        """Xử lý text biển số"""
        if conf > self.config.OCR_CONFIDENCE:
            return re.sub(r'[^A-Z0-9.]', '', text.upper())
        return None

    def _read_plate_thread(self) -> None:
        """Worker thread cho việc đọc biển số"""
        while self._safe_get("running", "frame"):
            try:
                frame = self._safe_get("frame", "frame")
                if frame is None:
                    continue

                processed_img = self._process_image(frame.copy())
                results = self.reader.readtext(processed_img)
                
                if results:
                    plate_texts = [
                        self._process_plate_text(text, conf)
                        for _, text, conf in results
                        if self._process_plate_text(text, conf)
                    ]
                    
                    plate = (f"{plate_texts[0]}-{plate_texts[1]}" 
                            if len(plate_texts) >= 2 else None)
                    self._safe_set("plate", plate, "plate")

            except Exception as e:
                print(f"Lỗi đọc biển số: {str(e)}")
                self._safe_set("plate", None, "plate")
            
            time.sleep(self.config.PLATE_READ_DELAY)

    def _create_plate_text(self, plate: Optional[str]) -> Tuple[str, Tuple[int, int, int]]:
        """Tạo text biển số và màu"""
        text = f"Plate: {plate if plate else '___'}"
        color = (0, 255, 0)  # Green
        return text, color

    def _draw_plate_text(self, frame: np.ndarray, plate: Optional[str]) -> None:
        """Vẽ text biển số lên frame"""
        text, color = self._create_plate_text(plate)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2

        (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        x = (frame.shape[1] - w) // 2
        y = frame.shape[0] - 20

        cv2.putText(frame, text, (x, y), font, font_scale, color, thickness)

    def _convert_to_qpixmap(self, frame: np.ndarray) -> QPixmap:
        """Chuyển frame OpenCV sang QPixmap"""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qt_image = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        return QPixmap.fromImage(qt_image)

    def get_frame_with_plate(self) -> Optional[QPixmap]:
        """Lấy frame hiện tại với biển số được vẽ lên"""
        frame = self._safe_get("frame", "frame")
        if frame is None:
            return None

        try:
            display_frame = frame.copy()
            plate = self._safe_get("plate", "plate")
            self._draw_plate_text(display_frame, plate)
            return self._convert_to_qpixmap(display_frame)
        except Exception as e:
            print(f"Lỗi xử lý frame: {str(e)}")
            return None

    def get_current_plate(self) -> Optional[str]:
        """Lấy biển số hiện tại"""
        return self._safe_get("plate", "plate")

    def cleanup(self) -> None:
        """Dọn dẹp resources"""
        print("Bắt đầu cleanup camera...")
        self._safe_set("running", False, "frame")
        
        try:
            # Dừng tất cả threads
            for name, thread in self.threads.items():
                try:
                    print(f"Đang dừng {name} thread...")
                    thread.join(timeout=1.0)
                    print(f"Đã dừng {name} thread")
                except Exception as e:
                    logger.error(f"Lỗi khi dừng {name} thread: {str(e)}")
            
            # Giải phóng camera
            if self.cap:
                if self.cap.isOpened():
                    self.cap.release()
                self.cap = None
                print("Đã giải phóng camera")
                
        except Exception as e:
            logger.error(f"Lỗi trong quá trình cleanup: {str(e)}")