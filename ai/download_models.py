"""
ErgoGuard AI - Pretrained Model Downloader
Downloads YOLOv8 Person and PPE ONNX models if not already present in ai/models/.
"""

import os
import urllib.request

MODELS = {
    "yolov8n.onnx": "https://huggingface.co/Xuban/yolo_weights_database/resolve/main/yolov8n.onnx",
    "ppe_yolov8.onnx": "https://huggingface.co/ayushgupta7777/safetyvision-yolov8/resolve/main/best.onnx",
    "pose_landmarker_lite.task": "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
}

def download_models():
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
    os.makedirs(target_dir, exist_ok=True)

    for filename, url in MODELS.items():
        dest = os.path.join(target_dir, filename)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000000:
            print(f"[OK] {filename} already exists ({os.path.getsize(dest) / 1024 / 1024:.1f} MB).")
            continue

        print(f"[Downloading] {filename} from {url}...")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(dest, "wb") as f:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while chunk := resp.read(65536):
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = int(downloaded / total * 100)
                    print(f"\r  Progress: {pct}% ({downloaded / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} MB)", end="")
            print(f"\n[OK] Saved {filename} to {dest}")

if __name__ == "__main__":
    download_models()
