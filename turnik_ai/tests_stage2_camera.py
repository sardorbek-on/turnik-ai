"""2-bosqich testi: kamera ro'yxati, ulanish, haqiqiy FPS."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cv2
from camera import Camera, list_cameras

cams = list_cameras()
print("Kameralar:", cams)
assert cams, "Kamera topilmadi"
cam = Camera()
assert cam.start(cams[0]["index"], 1280, 720, 30), "Kamera ochilmadi"
print("Haqiqiy o'lcham/FPS:", cam.actual_size())
seq, got, t0 = -1, 0, time.perf_counter()
last = None
while time.perf_counter() - t0 < 4:
    r = cam.read(seq)
    if r:
        last, _, seq = r
        got += 1
    else:
        time.sleep(0.002)
fps = got / (time.perf_counter() - t0)
print(f"Olingan kadrlar: {got}, o'qish FPS: {fps:.1f}, capture FPS: {cam.capture_fps:.1f}")
out = Path(__file__).parent / "data"
out.mkdir(exist_ok=True)
cv2.imwrite(str(out / "test_frame.jpg"), last)
mean, peak = float(last.mean()), int(last.max())
print("Kadr o'rtacha yorqinligi:", round(mean, 1), "| eng yorqin piksel:", peak)
cam.stop()
assert fps >= 20, "FPS past"
assert peak > 60, ("Kadr deyarli qora: obyektivni yopib turgan narsani (qopqoq/shutter) olib tashlang "
                   "yoki xonani yoriting. Bu apparat muammosi, kod emas.")
print("2-BOSQICH: OK")
