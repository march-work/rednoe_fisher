from dataclasses import dataclass
from typing import Literal

Rect = tuple[int, int, int, int]
OptRect = Rect | None


@dataclass(frozen=True)
class PostCard:
    rect: Rect
    image_rect: OptRect
    title_rect: Rect
    meta_rect: OptRect
    click_rect: Rect
    column: Literal["left", "right"]

    def is_complete(self, content_rect, margin=2):
        l, t, r, b = self.rect
        cl, ct, cr, cb = self.click_rect
        image = self.image_rect
        meta = self.meta_rect
        area = max(0, (r - l)) * max(0, (b - t))
        carea = max(0, (cr - cl)) * max(0, (cb - ct))
        if area <= 0:
            return False
        ratio = carea / float(area)
        if ratio < 0.85:
            return False
        if not image or not meta:
            return False
        il, it, ir, ib = image
        ml, mt, mr, mb = meta
        if ib <= it or mb <= mt:
            return False
        if it < t or ib > b or mt < t or mb > b:
            return False
        if abs(ib - self.title_rect[1]) > 1:
            return False
        if abs(self.title_rect[3] - mt) > 1:
            return False
        if il != l or ir != r:
            return False
        if self.title_rect[0] != l or self.title_rect[2] != r:
            return False
        if ml != l or mr != r:
            return False
        title_h = max(1, int(self.title_rect[3] - self.title_rect[1]))
        image_h = int(ib - it)
        if image_h > title_h * 5:
            return False
        if content_rect:
            ol, ot, orr, ob = content_rect
            if l < ol + margin or r > orr - margin or t < ot + margin or b > ob - margin:
                return False
        return True
