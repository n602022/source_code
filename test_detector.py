
from pathlib import Path

import cv2
from detector import detect_frame

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "sample_data"
OUTPUT_DIR = BASE_DIR / "evidence"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}

input_paths = sorted(
    path for path in INPUT_DIR.iterdir()
    if path.is_file() and (path.suffix.lower() in image_extensions or path.suffix.lower() in video_extensions)
)

if not input_paths:
    raise SystemExit(
        "Chua co du lieu kiem thu. "
        "Hay them anh (.jpg/.png) hoac video (.mp4) vao thu muc sample_data."
    )

success_count = 0

for input_path in input_paths:
    if input_path.suffix.lower() in image_extensions:
        frame = cv2.imread(str(input_path))
        frames_to_process = [(input_path, frame)]
    else:
        cap = cv2.VideoCapture(str(input_path))
        if not cap.isOpened():
            print(f"Khong doc duoc video: {input_path.name}")
            continue
        frames_to_process = []
        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames_to_process.append((input_path, frame.copy()))
            frame_index += 1
        cap.release()

    if not frames_to_process:
        print(f"Khong co frame nao trong video: {input_path.name}")
        continue

    for frame_index, (_, frame) in enumerate(frames_to_process):
        if frame is None:
            print(f"Khong doc duoc frame thu {frame_index} trong {input_path.name}")
            continue

        detections = detect_frame(frame)
        annotated = frame.copy()

        for item in detections:
            x1, y1, x2, y2 = item["bbox"]
            label = item["label"]
            confidence = item["confidence"]
            text = f"{label} {confidence:.2f}"

            if label.startswith("NO-"):
                color = (0, 0, 255)
            elif label in ("machinery", "vehicle"):
                color = (0, 165, 255)
            else:
                color = (0, 255, 0)

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(
                annotated,
                text,
                (x1, max(y1 - 8, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
            )

        output_name = f"{input_path.stem}_{frame_index:03d}_result.jpg"
        output_path = OUTPUT_DIR / output_name

        if not cv2.imwrite(str(output_path), annotated):
            print(f"Khong luu duoc ket qua: {output_path.name}")
            continue

        success_count += 1

        print(f"\nDu lieu kiem thu: {input_path.name} | frame #{frame_index}")
        print(f"So doi tuong phat hien: {len(detections)}")

        if detections:
            for item in detections:
                print(
                    f"- {item['label']}: "
                    f"confidence={item['confidence']:.4f}, "
                    f"bbox={item['bbox']}"
                )
        else:
            print("Khong phat hien doi tuong nao.")

        print(f"Anh ket qua: {output_path}")

print(f"\nDa xu ly thanh cong {success_count} frame(s) tu {len(input_paths)} file(s) dau vao.")
