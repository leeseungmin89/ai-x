
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import numpy as np

app = FastAPI()
# app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

# Load the object detection model
model = 'model/efficientdet_lite2.tflite'
base_options = python.BaseOptions(model_asset_path=model)
options = vision.ObjectDetectorOptions(base_options=base_options,
                                       running_mode=vision.RunningMode.LIVE_STREAM,
                                       score_threshold=0.5,
                                       result_callback=None,  # 여기에 추가
                                       category_allowlist=["person"])
detector = vision.ObjectDetector.create_from_options(options)

# FastAPI endpoint for the main page
@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# FastAPI endpoint for processing webcam image
@app.post("/predict")
async def predict_api(request: Request, file: UploadFile = File(...)):
    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # Run object detection using the model.
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
    detection_result_list = []

    async def visualize_callback(result: vision.ObjectDetectorResult,
                                 output_image: mp.Image, timestamp_ms: int):
        result.timestamp_ms = timestamp_ms
        detection_result_list.append(result)
    detector.detect_async(mp_image, 0)

    while not detection_result_list:
        pass  # 기다림

    result = detection_result_list[0]    

        # Processing and rendering code can be placed here
    current_frame = output_image.numpy_view()
    current_frame = cv2.cvtColor(current_frame, cv2.COLOR_RGB2BGR)
    mp_drawing.draw_landmarks(
            current_frame, result.detection_boxes, mp_pose.POSE_CONNECTIONS)

        # 결과를 HTML로 렌더링하여 반환
    return templates.TemplateResponse("result.html", {"request": request, "image": current_frame})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)