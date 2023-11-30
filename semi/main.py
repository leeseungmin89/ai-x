from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, Request, HTTPException,Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

import cv2
import base64
import json
import hashlib
import models
import datetime
import os

from database import engine, SessionLocal
from models import User, Date
from sqlalchemy.orm import Session
from utils import visualize


models.Base.metadata.create_all(bind=engine)
templates = Jinja2Templates(directory="templates")
users = {"user1": "password1"}

videos_dir = "videos"
if not os.path.exists(videos_dir):
    os.makedirs(videos_dir)

# DB 설정
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        # 마지막에 무조건 닫음
        db.close()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# 객체 탐지 모델 설정
model = 'model/ssd_mobilenet_v2.tflite'
base_options = python.BaseOptions(model_asset_path=model)
options = vision.ObjectDetectorOptions(base_options=base_options,
                                       score_threshold=0.5,
                                       category_allowlist=["person"])
detector = vision.ObjectDetector.create_from_options(options)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

class DetectionTracker:
    def __init__(self):
        self.is_detected = False

    def update(self, detected):
        changed = False
        if detected and not self.is_detected:
            self.is_detected = True
            changed = True
        elif not detected and self.is_detected:
            self.is_detected = False
            changed = True
        return changed

tracker = DetectionTracker()

@app.get("/")
async def get_root():
    return RedirectResponse(url="/login")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    recording = False
    out = None

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # mediapipe을 사용하여 이미지 처리    
            frame = cv2.flip(frame, 1)
            rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

            # mediapipe 이미지를 numpy 배열로 변환하고 BGR 형식으로 변환
            current_frame = mp_image.numpy_view()
            current_frame = cv2.cvtColor(current_frame, cv2.COLOR_RGB2BGR)

            # 객체 탐지
            det_val = detector.detect(mp_image)
            person_detected = "person" in str(det_val)
            # print(person_detected)

            # 이미지 시각화 및 웹전송
            vis_image = visualize(current_frame, det_val)
            ref, buffer = cv2.imencode('.jpg', vis_image)
            if ref:
               img_str = base64.b64encode(buffer.tobytes()).decode('utf-8')
               msg = json.dumps({'image': img_str, 'detection': str(det_val)})
               await websocket.send_text(msg)
            else:
                print("Error in image encoding")
            img_str =base64.b64encode(buffer.tobytes()).decode('utf-8')
            msg = json.dumps({'image': img_str, 'detection': str(det_val)})
            await websocket.send_text(msg)

            # 사람 객체 탐지 상태값 변경
            state_changed = tracker.update(person_detected)

            # 녹화 시작 & 중단
            if state_changed:
                event = Date()
                db.add(event)
                db.commit()
                if person_detected and not recording:
                    # 현재 시간을 기반으로 파일명 생성
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"videos/recording_{timestamp}.mp4"

                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    out = cv2.VideoWriter(filename, fourcc, 20.0, (640, 360))
                    recording = True

                elif not person_detected and recording:
                    recording = False
                    out.release()
                    out = None    

            if recording:
                out.write(frame)


    except WebSocketDisconnect:
        cap.release()

@app.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # 비밀번호 해싱
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    # 사용자 조회
    user = db.query(User).filter(User.username == username).first()

    # 사용자 존재 여부와 비밀번호 일치 여부 확인
    if user and user.hashed_password == hashed_password:
        # 로그인 성공 시 상태와 리디렉션 URL 전송
        return JSONResponse({"status": "success", "redirect": "/webcam"})
    else:
        # 로그인 실패 시 상태와 오류 메시지 전송
        return JSONResponse({"status": "failed", "message": "Login Failed"}, status_code=401)


@app.get("/webcam")
async def webcam_page(request: Request):
    # 웹캠 페이지 표시
    return templates.TemplateResponse("webcam.html", {"request": request})

@app.get("/register")
async def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    # 비밀번호 해싱
    hashed_password = hashlib.sha256(password.encode()).hexdigest()

    # 사용자 이름 중복 확인
    user = db.query(User).filter(User.username == username).first()
    if user:
        raise HTTPException(status_code=400, detail="Username already registered")

    new_user = User(username=username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()

    return RedirectResponse(url="/login", status_code=303)

