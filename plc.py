import snap7
from snap7.util import *
import time
import threading

from src import CHECKIN_BIT, CHECKOUT_BIT, CONTROL_DB, SLOT_BYTE # type: ignore


class PLCHandler:
    def __init__(
        self,
        ip="192.168.1.1",
        rack=0,
        slot=1,
        control_db=CONTROL_DB,
        checkin_bit=CHECKIN_BIT,
        checkout_bit=CHECKOUT_BIT,
        slot_byte=SLOT_BYTE
    ):
        # Cấu hình kết nối PLC
        self.ip = ip
        self.rack = rack
        self.slot = slot

        # Cấu hình DB cho điều khiển
        self.control_db = control_db  # Sử dụng DB3
        self.checkin_bit = checkin_bit  # DB3.DBX0.0 cho CHECKIN
        self.checkout_bit = checkout_bit  # DB3.DBX0.1 cho CHECKOUT
        self.slot_byte = slot_byte  # DB3.DBB1 cho số slot (1 byte)

        self.plc = None
        self.is_connected = False
        self.max_retries = 3
        self.retry_delay = 1

    def connect(self):
        """Kết nối với PLC với cơ chế thử lại"""
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                if self.plc is None:
                    self.plc = snap7.client.Client()

                if not self.is_connected:
                    self.plc.connect(self.ip, self.rack, self.slot)
                    self.is_connected = True
                    print(f"Kết nối PLC thành công: {self.ip}")
                    return True

            except Exception as e:
                retry_count += 1
                print(f"Lần {retry_count}: Lỗi kết nối PLC: {e}")

                if retry_count < self.max_retries:
                    print(f"Thử kết nối lại sau {self.retry_delay} giây...")
                    time.sleep(self.retry_delay)
                    try:
                        if self.plc:
                            self.plc.disconnect()
                    except:
                        pass
                    self.plc = None
                    self.is_connected = False

        print("Đã hết số lần thử kết nối, kết nối PLC thất bại!")
        return False

    def ensure_connection(self):
        """Đảm bảo kết nối trước khi thực hiện thao tác"""
        if not self.is_connected:
            return self.connect()
        try:
            self.plc.db_read(self.control_db, 0, 1)
            return True
        except Exception as e:
            print(f"Mất kết nối: {e}")
            self.is_connected = False
            return self.connect()

    def reset_control_data(self):
        """Reset toàn bộ dữ liệu điều khiển PLC"""
        if not self.ensure_connection():
            return False
        try:
            # Reset bit CHECKIN và CHECKOUT về 0
            byte_data = self.plc.db_read(self.control_db, 0, 1)
            current_byte = byte_data[0]
            reset_byte = (
                current_byte & ~(1 << self.checkin_bit) & ~(1 << self.checkout_bit)
            )

            # Ghi byte reset
            self.plc.db_write(self.control_db, 0, bytes([reset_byte]))

            # Reset slot về 0 (2 bytes)
            self.plc.db_write(self.control_db, self.slot_byte, bytes([0, 0]))

            print("Đã reset toàn bộ dữ liệu điều khiển PLC")
            return True

        except Exception as e:
            print(f"Lỗi reset dữ liệu điều khiển: {e}")
            self.is_connected = False
            return False

    # def send_check_in(self, slot_number: str):
    #     """Gửi tín hiệu GỬI XE và slot number"""
    #     if not self.ensure_connection():
    #         return False
    #     try:
    #         # Đọc byte điều khiển hiện tại
    #         byte_data = self.plc.db_read(self.control_db, 0, 1)
    #         current_byte = byte_data[0]

    #         # Set bit CHECKIN (bit 0) và reset bit CHECKOUT (bit 1)
    #         new_byte = (current_byte | (1 << self.checkin_bit)) & ~(1 << self.checkout_bit)

    #         # Ghi byte điều khiển
    #         self.plc.db_write(self.control_db, 0, bytes([new_byte]))

    #         # Ghi số slot kiểu Int (2 bytes)
    #         slot_value = int(slot_number)
    #         value_bytes = slot_value.to_bytes(2, byteorder='big', signed=True)  # Convert to 2 bytes cho Int
    #         self.plc.db_write(self.control_db, self.slot_byte, value_bytes)

    #         print(f"Đã gửi tín hiệu GỬI XE cho slot {slot_number}")
    #         return True

    #     except Exception as e:
    #         print(f"Lỗi gửi tín hiệu GỬI XE: {e}")
    #         self.is_connected = False
    #         return False

    # def send_check_out(self, slot_number: str):
    #     """Gửi tín hiệu LẤY XE và slot number"""
    #     if not self.ensure_connection():
    #         return False
    #     try:
    #         # Đọc byte điều khiển hiện tại
    #         byte_data = self.plc.db_read(self.control_db, 0, 1)
    #         current_byte = byte_data[0]

    #         # Set bit CHECKOUT (bit 1) và reset bit CHECKIN (bit 0)
    #         new_byte = (current_byte | (1 << self.checkout_bit)) & ~(1 << self.checkin_bit)

    #         # Ghi byte điều khiển
    #         self.plc.db_write(self.control_db, 0, bytes([new_byte]))

    #         # Ghi số slot kiểu Int (2 bytes)
    #         slot_value = int(slot_number)
    #         value_bytes = slot_value.to_bytes(2, byteorder='big', signed=True)  # Convert to 2 bytes cho Int
    #         self.plc.db_write(self.control_db, self.slot_byte, value_bytes)

    #         print(f"Đã gửi tín hiệu LẤY XE cho slot {slot_number}")
    #         return True

    #     except Exception as e:
    #         print(f"Lỗi gửi tín hiệu LẤY XE: {e}")
    #         self.is_connected = False
    #         return False

    def send_check_in(self, slot_number: str):
        """Gửi tín hiệu GỬI XE và slot number"""
        if not self.ensure_connection():
            return False
        try:
            # Đọc byte điều khiển hiện tại
            byte_data = self.plc.db_read(self.control_db, 0, 1)
            current_byte = byte_data[0]

            # Set bit CHECKIN (bit 0) và reset bit CHECKOUT (bit 1)
            new_byte = (current_byte | (1 << self.checkin_bit)) & ~(
                1 << self.checkout_bit
            )

            # Ghi byte điều khiển
            self.plc.db_write(self.control_db, 0, bytes([new_byte]))

            # Ghi số slot kiểu Int (2 bytes)
            slot_value = int(slot_number)
            value_bytes = slot_value.to_bytes(2, byteorder="big", signed=True)
            self.plc.db_write(self.control_db, self.slot_byte, value_bytes)

            print(f"[PLC] Đã gửi lệnh CHECK-IN cho xe tại vị trí slot {slot_number}")

            # Tạo timer để reset sau 10 giây
            timer = threading.Timer(10, self.reset_control_data)
            timer.start()

            return True

        except Exception as e:
            print(f"[PLC] Lỗi gửi lệnh CHECK-IN: {e}")
            self.is_connected = False
            return False

    def send_check_out(self, slot_number: str):
        """Gửi tín hiệu LẤY XE và slot number"""
        if not self.ensure_connection():
            return False
        try:
            # Đọc byte điều khiển hiện tại
            byte_data = self.plc.db_read(self.control_db, 0, 1)
            current_byte = byte_data[0]

            # Set bit CHECKOUT (bit 1) và reset bit CHECKIN (bit 0)
            new_byte = (current_byte | (1 << self.checkout_bit)) & ~(
                1 << self.checkin_bit
            )

            # Ghi byte điều khiển
            self.plc.db_write(self.control_db, 0, bytes([new_byte]))

            # Ghi số slot kiểu Int (2 bytes)
            slot_value = int(slot_number)
            value_bytes = slot_value.to_bytes(2, byteorder="big", signed=True)
            self.plc.db_write(self.control_db, self.slot_byte, value_bytes)

            print(f"[PLC] Đã gửi lệnh CHECK-OUT cho xe tại vị trí slot {slot_number}")

            # Tạo timer để reset sau 10 giây
            timer = threading.Timer(10, self.reset_control_data)
            timer.start()

            return True

        except Exception as e:
            print(f"[PLC] Lỗi gửi lệnh CHECK-OUT: {e}")
            self.is_connected = False
            return False

    def reset_control_data(self):
        """Reset toàn bộ dữ liệu điều khiển PLC"""
        if not self.ensure_connection():
            return False
        try:
            # Reset bit CHECKIN và CHECKOUT về 0
            byte_data = self.plc.db_read(self.control_db, 0, 1)
            current_byte = byte_data[0]
            reset_byte = (
                current_byte & ~(1 << self.checkin_bit) & ~(1 << self.checkout_bit)
            )

            # Ghi byte reset
            self.plc.db_write(self.control_db, 0, bytes([reset_byte]))

            # Reset slot về 0 (2 bytes)
            self.plc.db_write(self.control_db, self.slot_byte, bytes([0, 0]))

            print("[PLC] Đã reset toàn bộ trạng thái điều khiển")
            return True

        except Exception as e:
            print(f"[PLC] Lỗi reset trạng thái điều khiển: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Ngắt kết nối PLC"""
        if self.plc and self.is_connected:
            try:
                self.plc.disconnect()
            except Exception as e:
                print(f"Lỗi ngắt kết nối: {e}")
            finally:
                self.is_connected = False
                self.plc = None
                print("Đã ngắt kết nối PLC")
