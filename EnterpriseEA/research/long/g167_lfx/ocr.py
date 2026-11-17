import json, sys
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
Image.MAX_IMAGE_PIXELS = None
im = Image.open(r"C:\Users\Zbook Studio\Desktop\2026-11-17_214530.png")
W, H = im.size
eng = RapidOCR()
out = []
step, ov = 1600, 200
y = 0
while y < H:
    crop = im.crop((225, y, 800, min(y + step + ov, H)))
    crop = crop.resize((crop.width * 2, crop.height * 2))
    res, _ = eng(crop)
    for box, txt, conf in (res or []):
        yy = y + min(p[1] for p in box) / 2
        xx = 225 + min(p[0] for p in box) / 2
        out.append((round(yy, 1), round(xx, 1), txt, round(float(conf), 3)))
    y += step
    print(y, len(out), file=sys.stderr, flush=True)
json.dump(out, open("ocr.json", "w", encoding="utf-8"), ensure_ascii=False)
