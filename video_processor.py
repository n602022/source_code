"""video_processor.py - TV3 Han (Video Engineer)
Doc video mp4, cat thanh tung frame bang OpenCV, co bat loi file hong.
"""
import os
import cv2


def open_video(video_path):
    """Mo video. Tra ve doi tuong VideoCapture, hoac None neu loi."""
    if not os.path.exists(video_path):
        print(f"[LOI FILE] Khong tim thay file: {video_path}")
        return None
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[LOI FILE] Khong mo duoc video (file hong hoac sai dinh dang): {video_path}")
        cap.release()
        return None
    return cap


def get_video_info(video_path):
    """Tra ve dict thong tin video (fps, width, height, total_frames) hoac None."""
    cap = open_video(video_path)
    if cap is None:
        return None
    info = {
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    cap.release()
    return info


def read_frames(video_path, frame_step=1, max_width=960):
    """Generator: moi lan tra ve (so_thu_tu_frame, frame).
    frame_step: cu moi N frame lay 1 frame (vd 5 -> nhe may hon).
    max_width: thu nho frame neu qua rong (video 4K rat nang).
    Neu video hong thi in loi va ket thuc, KHONG bi sap.
    """
    cap = open_video(video_path)
    if cap is None:
        return
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:  # het video hoac frame loi
                break
            if index % frame_step == 0:
                h, w = frame.shape[:2]
                if max_width and w > max_width:
                    scale = max_width / w
                    frame = cv2.resize(frame, (max_width, int(h * scale)))
                yield index, frame
            index += 1
    except Exception as e:
        print(f"[LOI FILE] Loi khi doc video {video_path}: {e}")
    finally:
        cap.release()


def save_frames(video_path, out_dir="frames_out", frame_step=30):
    """Cat video thanh anh .jpg luu vao out_dir. Tra ve so anh da luu."""
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for index, frame in read_frames(video_path, frame_step=frame_step):
        cv2.imwrite(os.path.join(out_dir, f"frame_{index:05d}.jpg"), frame)
        count += 1
    print(f"Da luu {count} frame vao thu muc '{out_dir}'")
    return count


if __name__ == "__main__":
    import glob

    videos = sorted(glob.glob("sample_data/sample_*.mp4"))
    if not videos:
        print("[LOI FILE] Khong thay video nao trong thu muc sample_data")

    for video in videos:
        print("=" * 50)
        print("Video:", video)
        print("Thong tin:", get_video_info(video))
        name = os.path.splitext(os.path.basename(video))[0]
        save_frames(video, f"frames_out/{name}", frame_step=30)

    # Test bat loi: file khong ton tai va file hong (tao tam roi xoa)
    print("=" * 50)
    print("TEST BAT LOI")
    save_frames("sample_data/khong_ton_tai.mp4")
    with open("sample_data/hong.mp4", "w") as f:
        f.write("day khong phai video")
    save_frames("sample_data/hong.mp4", "frames_out/hong")
    os.remove("sample_data/hong.mp4")
    print("Chuong trinh van chay binh thuong, khong bi sap.")