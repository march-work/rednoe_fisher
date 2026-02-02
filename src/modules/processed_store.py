import json
import os
import hashlib

from PIL import Image


def _normalize_text(text):
    if not text:
        return ""
    return "".join(ch for ch in str(text).strip().upper() if ch.isalnum())


def signature_from_text(text):
    s = _normalize_text(text)
    if not s:
        return ""
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def signature_from_image(image: Image.Image, size=8):
    if image is None:
        return ""
    img = image.convert("L").resize((size, size))
    pixels = list(img.getdata())
    avg = sum(pixels) / float(len(pixels))
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    return hashlib.sha1(bits.encode("utf-8")).hexdigest()


class ProcessedPostStore:
    def __init__(self, path, max_size=5000):
        self.path = path
        self.max_size = int(max_size)
        self._seen = set()
        self._load()

    def _load(self):
        try:
            if self.path and os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for x in data.get("seen", []):
                    if x:
                        self._seen.add(str(x))
        except Exception:
            self._seen = set()

    def save(self):
        if not self.path:
            return
        try:
            folder = os.path.dirname(self.path)
            if folder:
                os.makedirs(folder, exist_ok=True)
            data = {"seen": list(self._seen)[-self.max_size :]}
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            return

    def seen(self, sig):
        return bool(sig) and sig in self._seen

    def mark(self, sig):
        if not sig:
            return
        self._seen.add(sig)
        if len(self._seen) > self.max_size * 2:
            self._seen = set(list(self._seen)[-self.max_size :])
