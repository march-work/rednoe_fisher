from PIL import Image

from src.modules.processed_store import signature_from_image, signature_from_text, ProcessedPostStore


def test_signature_from_text_stable():
    a = signature_from_text("大模型 AI")
    b = signature_from_text("大模型  ai ")
    assert a == b


def test_signature_from_image_stable():
    img1 = Image.new("RGB", (32, 32), color=(255, 255, 255))
    img2 = Image.new("RGB", (32, 32), color=(255, 255, 255))
    assert signature_from_image(img1) == signature_from_image(img2)


def test_processed_store_mark_seen(tmp_path):
    path = tmp_path / "store.json"
    store = ProcessedPostStore(str(path), max_size=10)
    assert store.seen("x") is False
    store.mark("x")
    assert store.seen("x") is True
    store.save()

    store2 = ProcessedPostStore(str(path), max_size=10)
    assert store2.seen("x") is True
