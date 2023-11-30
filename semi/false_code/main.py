# 필요한 모듈 임포트
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, StreamingResponse
import cv2
import threading
import queue
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from utils import visualize

app = FastAPI()

frame_queue = queue.Queue()
stop_thread = False


detection_result_list = []
def visualize_callback(result: vision.ObjectDetectorResult,
                         output_image: mp.Image, timestamp_ms: int):
    result.timestamp_ms = timestamp_ms
    detection_result_list.append(result)

def capture_frames(camera_id, width, height):
    global stop_thread

    # 객체 탐지 모델 초기화
    model = 'model/efficientdet_lite2.tflite'  # 모델 경로 정의
    base_options = python.BaseOptions(model_asset_path=model)

    options = vision.ObjectDetectorOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.LIVE_STREAM,  # LIVE_STREAM 모드 사용
        detection_timeout_ms=5000,  # 탐지 시간 초과 설정 (원하는 값으로 변경)
        score_threshold=0.5,
        result_callback=visualize_callback,
        category_allowlist=["person"],
    )

    # 이미지 처리 모드 설정 (output_static_image_format 대신)
    options.base_options.model_image_format = mp.ImageFormat.SRGB
    options.base_options.model_image_channel_order = mp.ImageChannelOrder.BGR
    options.base_options.flip_horizontally = False

    detector = vision.ObjectDetector.create_from_options(options)


    cap = cv2.VideoCapture(camera_id)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    while not stop_thread and cap.isOpened():
        success, frame = cap.read()
        if not success:
            break

        # 객체 탐지 수행
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        results = detector.detect(mp_frame)

        # 결과 시각화
        visualized_frame = visualize(frame, results) if results.detections else frame
        frame_queue.put(visualized_frame)

    cap.release()

@app.on_event("startup")
def start_camera_thread():
    camera_thread = threading.Thread(target=capture_frames, args=(0, 1280, 720), daemon=True)
    camera_thread.start()

@app.on_event("shutdown")
def stop_camera_thread():
    global stop_thread
    stop_thread = True

@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open("index.html", "r") as file:
        html_content = file.read()
    return HTMLResponse(content=html_content)    

# @app.get("/")
# def index():
#     # HTML 페이지 반환
#     return HTMLResponse("""
#     <html>
#         <head>
#             <title>Camera Stream</title>
#         </head>
#         <body>
#             <h1>Camera Stream</h1>
#             <img id="videoFeed" src="/video_feed">
#         </body>
#     </html>
#     """)

def generate():
    while True:
        if not frame_queue.empty():
            frame = frame_queue.get()
            ret, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + b'\r\n')

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")
