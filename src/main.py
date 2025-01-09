from fastapi import FastAPI
from ultralytics import YOLO
import easyocr
from src.OCR import *
from fastapi.middleware.cors import CORSMiddleware
import random
from src.local_utils import detect_lp
from os.path import splitext, basename
from keras.models import model_from_json

app = FastAPI()

origins = [
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize FastAPI
app = FastAPI()

# Initialize models
coco_model = YOLO('./models/yolov8n.pt')
license_plate_model = YOLO('./models/license_plate_detector.pt')

# Initialize the OCR reader
reader = easyocr.Reader(['en'], gpu=False)

# Initialize WPOD-NET
def load_model(path):
    try:
        path = splitext(path)[0]
        with open('%s.json' % path, 'r') as json_file:
            model_json = json_file.read()
        model = model_from_json(model_json, custom_objects={})
        model.load_weights('%s.h5' % path)
        print("Loading model successfully...")
        return model
    except Exception as e:
        print(e)
        
wpod_net_path = "./models/wpod-net.json"
wpod_net = load_model(wpod_net_path)
print(wpod_net)

# Path to input and output images
output_dir = 'D:/Project/TuanHoang/data/output'


@app.post("/OCRLicensePlate")
def post_OCRLicensePlate():
    image_path = random.choice(os.listdir('D:/Project/TuanHoang/data/image/'))
    image_path = 'D:/Project/TuanHoang/data/image/' + image_path

    # image_path = 'D:/Project/TuanHoang/data/image/CarLongPlate20_jpg.rf.9218573c6249c89f9d361c4925026be0.jpg' # Input image path

    # print(wpod_net_model)
    licenseplate = OCRLicensePlate(coco_model, license_plate_model, reader, image_path, output_dir)
    return licenseplate