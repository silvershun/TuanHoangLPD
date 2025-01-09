import cv2
import numpy as np
import os
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r'C:/Users/hoan.vo/AppData/Local/Programs/Tesseract-OCR/tesseract.exe'

dict_char_to_int = {'I': '1', 'J': '3', 'A': '4',
                'G': '6', 'S': '5', 'Z': '2',
                'B': '8', 'T': '7', 'D': '0',
                'k': '4', 'O': '0', 'g': '9', 
                'e': '8'} # Kiếm thêm ảnh rồi thêm mấy case ngoại lệ vào

dict_int_to_char = {'1': 'I', '3': 'J', '4': 'A',
                '6': 'G', '5': 'S', '2': 'Z',
                '8': 'B', '7': 'T', '0': 'D'}

vehicles = [1, 2, 3, 5, 6, 7]

class_vehicles = {
    1: 'bicycle',
    2: 'car',
    3: 'motorcycle',
    5: 'bus',
    6: 'train',
    7: 'truck'
}

# Lọc các ký tự không phải là ký tự số hoặc chữ cái
def convert_license_plate_text(license_plate_text):
    license_plate_text = license_plate_text.replace('(', '')
    license_plate_text = license_plate_text.replace(')', '')
    license_plate_text = license_plate_text.replace(']', '')
    license_plate_text = license_plate_text.replace('[', '')
    license_plate_text = license_plate_text.replace('{', '')
    license_plate_text = license_plate_text.replace('}', '')
    license_plate_text = license_plate_text.replace('-', '')
    license_plate_text = license_plate_text.replace('.', '')
    license_plate_text = license_plate_text.replace(',', '')
    license_plate_text = license_plate_text.replace(';', '')
    license_plate_text = license_plate_text.replace(':', '')
    license_plate_text = license_plate_text.replace('!', '')
    license_plate_text = license_plate_text.replace('@', '')
    license_plate_text = license_plate_text.replace('#', '')
    license_plate_text = license_plate_text.replace('$', '')
    license_plate_text = license_plate_text.replace('%', '')
    license_plate_text = license_plate_text.replace('^', '')
    license_plate_text = license_plate_text.replace('&', '')
    license_plate_text = license_plate_text.replace('*', '')
    license_plate_text = license_plate_text.replace('_', '')
    license_plate_text = license_plate_text.replace('+', '')
    license_plate_text = license_plate_text.replace('=', '')
    license_plate_text = license_plate_text.replace('<', '')
    license_plate_text = license_plate_text.replace('>', '')
    license_plate_text = license_plate_text.replace('?', '')
    license_plate_text = license_plate_text.replace('/', '')
    license_plate_text = license_plate_text.replace('//', '')
    license_plate_text = license_plate_text.replace('|', '')
    license_plate_text = license_plate_text.replace('`', '')
    license_plate_text = license_plate_text.replace('~', '')
    license_plate_text = license_plate_text.replace(' ', '')
    return license_plate_text

# Xử lý ký tự số và chữ cái trong biển số
def processing_license_plate_text(license_plate_text):
    license_plate_chars = list(license_plate_text)
    license_plate = ''
    for i in range(len(license_plate_chars)):
        # print(license_plate_chars[i])
        if license_plate_chars[i] in dict_int_to_char and i == 2:
            license_plate_chars[i] = dict_int_to_char[license_plate_chars[i]]
        elif license_plate_chars[i] in dict_char_to_int and i in [0,1,3,4,5,6,7,8]:
            license_plate_chars[i] = dict_char_to_int[license_plate_chars[i]]
        if i == 3:
            license_plate += '-'
            license_plate += license_plate_chars[i]
        elif i == 6:
            license_plate += '.'
            license_plate += license_plate_chars[i]
        else:
            license_plate += license_plate_chars[i]
    return license_plate

# Hàm nhận diện biển số
def OCRLicensePlate(coco_model, license_plate_model, reader, image_path, output_dir):
    # Load the image
    image = cv2.imread(image_path)

    # Detect vehicles
    detections = coco_model(image)[0]
    for detection in detections.boxes.data.tolist():
        isVehicle = False
        x1, y1, x2, y2, score, class_id = detection
        if int(class_id) in vehicles:
            isVehicle = True
            print(f"Vehicle {class_vehicles[int(class_id)]} detected with confidence score {score}")
        else:
            isVehicle = False
            print(f"Object detected with confidence score {score}")

        if isVehicle:
            print(f"Vehicle {class_vehicles[class_id]} detected with confidence score {score}")
            vehicle_crop = image[int(y1):int(y2), int(x1):int(x2)]
            vehicle_crop_path = os.path.join(output_dir, f"{class_vehicles[class_id]}_{score}.jpg")
            cv2.imwrite(vehicle_crop_path, vehicle_crop)
            print(f"Vehicle {class_vehicles[class_id]} cropped and saved at {vehicle_crop_path}")

            # Detect license plate
            license_plate_detections = license_plate_model(vehicle_crop)[0]
            for license_plate in license_plate_detections.boxes.data.tolist():
                if license_plate:
                    lp_x1, lp_y1, lp_x2, lp_y2, lp_score, lp_class_id = license_plate
                    license_plate_crop = vehicle_crop[int(lp_y1):int(lp_y2), int(lp_x1):int(lp_x2)]
                    license_plate_crop_path = os.path.join(output_dir, f"license_plate_{class_vehicles[class_id]}_{lp_score}.jpg")
                    cv2.imwrite(license_plate_crop_path, license_plate_crop)
                    print(f"License plate cropped and saved at {license_plate_crop_path}")

                    # Read license plate text
                    print("Reading license plate text...")
                    result = reader.readtext(license_plate_crop_path)
                    print(result)
                    if result:
                        try:
                            license_plate_text = convert_license_plate_text(result[0][1] + result[1][1])
                            confidence_score = (result[0][2] + result[1][2])/2
                        except:
                            license_plate_text = convert_license_plate_text(result[0][1])
                            confidence_score = result[0][2]
                        print(confidence_score)
                        if confidence_score:
                            license_plate_text = processing_license_plate_text(license_plate_text)
                        print(f"License plate text: {license_plate_text}")
                        return license_plate_text
                else:
                    continue
    return None