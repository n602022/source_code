
from pathlib import Path

from ultralytics import YOLO

# Duong dan den thu muc project
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "best.pt"

# Kiem tra file mo hinh
if not MODEL_PATH.is_file():
    raise FileNotFoundError(
        f"Khong tim thay mo hinh: {MODEL_PATH}"
    )

# Nap mo hinh mot lan khi import module
_model = YOLO(str(MODEL_PATH))


def detect_frame(frame, conf=0.45):
    """
    Nhan dien cac doi tuong trong mot khung hinh.

    Input:
        frame: Anh dang mang NumPy, thuong doc bang OpenCV.

    Output:
        Danh sach cac doi tuong duoc phat hien.
        Moi doi tuong gom label, confidence va bbox.
        bbox co dang [x1, y1, x2, y2], don vi pixel.
    """
    if frame is None:
        raise ValueError("Khung hinh dau vao dang rong.")

    results = _model.predict(
        source=frame,
        conf=conf,
        verbose=False
    )

    detections = []

    for result in results:
        if result.boxes is None:
            continue

        for box in result.boxes:
            class_id = int(box.cls.item())
            confidence = float(box.conf.item())
            coordinates = box.xyxy[0].tolist()

            detections.append({
                "label": result.names[class_id],
                "confidence": round(confidence, 4),
                "bbox": [
                    int(round(value))
                    for value in coordinates
                ]
            })

    return detections
