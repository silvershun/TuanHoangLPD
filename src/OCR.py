import cv2
import numpy as np
import os
from skimage.filters import threshold_local
from skimage import measure
import imutils

dict_char_to_int = {'I': '1', 'J': '3', 'A': '4',
                    'G': '6', 'S': '5', 'Z': '2',
                    'B': '8', 'T': '7', 'D': '0',
                    'k': '4', 'O': '0', 'g': '9', 
                    'e': '8'}

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
    for char in "()-[]{}-.,;:!@#$%^&*_+=<>?/\\|`~ ":
        license_plate_text = license_plate_text.replace(char, '')
    return license_plate_text

# Xử lý ký tự số và chữ cái trong biển số
def processing_license_plate_text(license_plate_text):
    license_plate_chars = list(license_plate_text)
    license_plate = ''
    for i, char in enumerate(license_plate_chars):
        if char in dict_int_to_char and i == 2:
            license_plate_chars[i] = dict_int_to_char[char]
        elif char in dict_char_to_int and i in [0, 1, 3, 4, 5, 6, 7, 8]:
            license_plate_chars[i] = dict_char_to_int[char]
        if i == 3:
            license_plate += '-'
        elif i == 6:
            license_plate += '.'
        license_plate += license_plate_chars[i]
    return license_plate

# Hàm segmentation để tách ký tự từ vùng biển số
def segmentation(license_plate_crop):
    V = cv2.split(cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2HSV))[2]
    T = threshold_local(V, 15, offset=10, method="gaussian")
    thresh = (V > T).astype("uint8") * 255
    thresh = cv2.bitwise_not(thresh)
    thresh = imutils.resize(thresh, width=400)
    thresh = cv2.medianBlur(thresh, 5)
    
    labels = measure.label(thresh, connectivity=2, background=0)
    characters = []
    for label in np.unique(labels):
        if label == 0:
            continue
        mask = np.zeros(thresh.shape, dtype="uint8")
        mask[labels == label] = 255
        contours = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]
        if contours:
            contour = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(contour)
            aspectRatio = w / float(h)
            solidity = cv2.contourArea(contour) / float(w * h)
            heightRatio = h / float(license_plate_crop.shape[0])
            if 0.1 < aspectRatio < 1.0 and solidity > 0.1 and 0.35 < heightRatio < 2.0:
                char = thresh[y:y+h, x:x+w]
                characters.append(char)
    return characters

# Hàm nhận diện biển số
def OCRLicensePlate(coco_model, license_plate_model, reader, image_path, output_dir):
    # Load the image
    image = cv2.imread(image_path)

    # Detect vehicles
    detections = coco_model(image)[0]
    for detection in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = detection
        if int(class_id) in vehicles:
            print(f"Vehicle {class_vehicles[int(class_id)]} detected with confidence score {score}")
            vehicle_crop = image[int(y1):int(y2), int(x1):int(x2)]
            license_plate_detections = license_plate_model(vehicle_crop)[0]
            for license_plate in license_plate_detections.boxes.data.tolist():
                lp_x1, lp_y1, lp_x2, lp_y2, lp_score, lp_class_id = license_plate
                license_plate_crop = vehicle_crop[int(lp_y1):int(lp_y2), int(lp_x1):int(lp_x2)]
                print("Segmenting characters from license plate...")
                characters = segmentation(license_plate_crop)
                license_plate_text = ""
                for char in characters:
                    result = reader.readtext(char)
                    if result:
                        license_plate_text += result[0][1]
                license_plate_text = convert_license_plate_text(license_plate_text)
                license_plate_text = processing_license_plate_text(license_plate_text)
                
                # Thêm thông tin hình ảnh đầu vào
                image_name = os.path.basename(image_path)  # Lấy tên tệp hình ảnh
                print(f"License plate detected from image: {image_name}")
                print(f"License plate text: {license_plate_text}")
                
                # Trả về kết quả bao gồm tên tệp hình ảnh và biển số
                return {
                    "image_name": image_name,
                    "license_plate": license_plate_text
                }
    return {"error": "No license plate detected"}
