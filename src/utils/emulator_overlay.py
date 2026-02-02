import threading
import time

import win32api
import win32con
import win32gui


class EmulatorOverlay:
    def __init__(self, alpha=None, *, mask_alpha=38, fg_alpha=204):
        if alpha is not None:
            mask_alpha = int(alpha)
            fg_alpha = int(alpha)
        self.mask_alpha = int(mask_alpha)
        self.fg_alpha = int(fg_alpha)
        self.mask_hwnd = None
        self.fg_hwnd = None
        self.running = False
        self.thread = None
        self._target_rect = None
        self._render = None
        self._colorkey = (1, 0, 1)
        self._font = None
        self._font_height = 18

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def set_target_rect(self, rect):
        self._target_rect = rect

    def set_render_state(self, state):
        self._render = state

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_PAINT:
            hdc, ps = win32gui.BeginPaint(hwnd)
            try:
                state = self._render or {}

                is_mask = hwnd == self.mask_hwnd
                if is_mask:
                    if state.get("mask", True):
                        brush = win32gui.CreateSolidBrush(win32api.RGB(0, 0, 0))
                        old = win32gui.SelectObject(hdc, brush)
                        w = state.get("w", 0)
                        h = state.get("h", 0)
                        win32gui.Rectangle(hdc, 0, 0, int(w), int(h))
                        win32gui.SelectObject(hdc, old)
                        win32gui.DeleteObject(brush)
                    return 0
                else:
                    ck = win32api.RGB(*self._colorkey)
                    brush = win32gui.CreateSolidBrush(ck)
                    old = win32gui.SelectObject(hdc, brush)
                    w = state.get("w", 0)
                    h = state.get("h", 0)
                    win32gui.Rectangle(hdc, 0, 0, int(w), int(h))
                    win32gui.SelectObject(hdc, old)
                    win32gui.DeleteObject(brush)

                def _pen(color, width=1, style=win32con.PS_SOLID):
                    return win32gui.CreatePen(style, int(width), win32api.RGB(*color))

                def _draw_rect(rect, color, width=1, dashed=False, outline=True):
                    if not rect:
                        return
                    l, t, r, b = rect
                    style = win32con.PS_DASH if dashed else win32con.PS_SOLID
                    if outline and width >= 2:
                        pen2 = _pen((0, 0, 0), width + 2, style=style)
                        old_pen2 = win32gui.SelectObject(hdc, pen2)
                        old_brush2 = win32gui.SelectObject(
                            hdc, win32gui.GetStockObject(win32con.NULL_BRUSH)
                        )
                        win32gui.Rectangle(hdc, int(l), int(t), int(r), int(b))
                        win32gui.SelectObject(hdc, old_brush2)
                        win32gui.SelectObject(hdc, old_pen2)
                        win32gui.DeleteObject(pen2)
                    pen = _pen(color, width, style=style)
                    old_pen = win32gui.SelectObject(hdc, pen)
                    old_brush = win32gui.SelectObject(hdc, win32gui.GetStockObject(win32con.NULL_BRUSH))
                    win32gui.Rectangle(hdc, int(l), int(t), int(r), int(b))
                    win32gui.SelectObject(hdc, old_brush)
                    win32gui.SelectObject(hdc, old_pen)
                    win32gui.DeleteObject(pen)

                def _text(x, y, s, color=(255, 255, 255), bg=(0, 0, 0), padding=3):
                    if self._font is not None:
                        win32gui.SelectObject(hdc, self._font)
                    text = str(s)
                    ix, iy = int(x), int(y)
                    try:
                        tw, th = win32gui.GetTextExtentPoint32(hdc, text)
                    except Exception:
                        tw, th = (len(text) * self._font_height, self._font_height + 4)
                    if tw > 0 and th > 0:
                        brush = win32gui.CreateSolidBrush(win32api.RGB(*bg))
                        old_brush = win32gui.SelectObject(hdc, brush)
                        old_pen = win32gui.SelectObject(hdc, win32gui.GetStockObject(win32con.NULL_PEN))
                        win32gui.Rectangle(
                            hdc,
                            int(ix - padding),
                            int(iy - padding),
                            int(ix + tw + padding),
                            int(iy + th + padding),
                        )
                        win32gui.SelectObject(hdc, old_pen)
                        win32gui.SelectObject(hdc, old_brush)
                        win32gui.DeleteObject(brush)
                    win32gui.SetBkMode(hdc, win32con.TRANSPARENT)
                    win32gui.SetTextColor(hdc, win32api.RGB(*color))
                    if hasattr(win32gui, "TextOut"):
                        win32gui.TextOut(hdc, ix, iy, text)
                    else:
                        win32gui.ExtTextOut(hdc, ix, iy, 0, None, text, None)

                content = state.get("content_rect")
                if content:
                    _draw_rect(content, (0, 255, 0), width=3, dashed=False, outline=True)

                cards = state.get("cards") or []
                for c in cards:
                    rect = c.get("rect")
                    image_rect = c.get("image_rect")
                    title_rect = c.get("title_rect")
                    meta_rect = c.get("meta_rect")
                    click_rect = c.get("click_rect")
                    dashed = bool(c.get("dashed"))
                    label = c.get("label")
                    _draw_rect(rect, (255, 0, 0), width=3, dashed=dashed, outline=True)
                    _draw_rect(image_rect, (0, 200, 255), width=3, dashed=False, outline=True)
                    _draw_rect(title_rect, (255, 165, 0), width=3, dashed=False, outline=True)
                    _draw_rect(meta_rect, (255, 0, 255), width=3, dashed=False, outline=True)
                    _draw_rect(click_rect, (0, 255, 0), width=3, dashed=False, outline=True)
                    if label and rect:
                        _text(rect[0] + 6, rect[1] + 6, label, color=(255, 255, 255), bg=(0, 0, 0))
                    idx = c.get("idx")
                    if idx:
                        if image_rect:
                            _text(image_rect[0] + 6, image_rect[1] + 6, f"img{idx}", color=(0, 0, 0), bg=(0, 200, 255))
                        if title_rect:
                            _text(title_rect[0] + 6, title_rect[1] + 6, f"title{idx}", color=(0, 0, 0), bg=(255, 165, 0))
                        if meta_rect:
                            _text(meta_rect[0] + 6, meta_rect[1] + 6, f"meta{idx}", color=(255, 255, 255), bg=(120, 0, 120))

                active = state.get("active_rect")
                if active:
                    _draw_rect(active, (0, 255, 0), width=5, dashed=False, outline=True)
                    _text(
                        active[0] + 6,
                        max(0, active[1] - 28),
                        "当前操作区",
                        color=(0, 0, 0),
                        bg=(0, 255, 0),
                        padding=4,
                    )
            finally:
                win32gui.EndPaint(hwnd, ps)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _run_loop(self):
        def _register_class(name):
            wc = win32gui.WNDCLASS()
            wc.lpfnWndProc = self._wnd_proc
            wc.lpszClassName = name
            wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
            wc.hbrBackground = win32gui.GetStockObject(win32con.NULL_BRUSH)
            try:
                return win32gui.RegisterClass(wc)
            except Exception:
                return win32gui.GetClassInfo(win32api.GetModuleHandle(None), name)

        class_atom_mask = _register_class("FisherEmulatorOverlayMask")
        class_atom_fg = _register_class("FisherEmulatorOverlayFG")

        ex_style = (
            win32con.WS_EX_LAYERED
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_TOOLWINDOW
            | win32con.WS_EX_TRANSPARENT
        )
        style = win32con.WS_POPUP

        self.mask_hwnd = win32gui.CreateWindowEx(
            ex_style, class_atom_mask, "FisherEmulatorOverlayMask", style, 0, 0, 10, 10, 0, 0, 0, None
        )
        self.fg_hwnd = win32gui.CreateWindowEx(
            ex_style, class_atom_fg, "FisherEmulatorOverlayFG", style, 0, 0, 10, 10, 0, 0, 0, None
        )

        try:
            self._font = win32gui.CreateFont(
                -int(self._font_height),
                0,
                0,
                0,
                win32con.FW_BOLD,
                0,
                0,
                0,
                win32con.DEFAULT_CHARSET,
                win32con.OUT_DEFAULT_PRECIS,
                win32con.CLIP_DEFAULT_PRECIS,
                win32con.DEFAULT_QUALITY,
                win32con.DEFAULT_PITCH | win32con.FF_DONTCARE,
                "Microsoft YaHei",
            )
        except Exception:
            self._font = None

        win32gui.SetLayeredWindowAttributes(self.mask_hwnd, 0, self.mask_alpha, win32con.LWA_ALPHA)
        ck = win32api.RGB(*self._colorkey)
        win32gui.SetLayeredWindowAttributes(
            self.fg_hwnd, ck, self.fg_alpha, win32con.LWA_ALPHA | win32con.LWA_COLORKEY
        )

        while self.running:
            try:
                win32gui.PumpWaitingMessages()
            except Exception:
                pass

            rect = self._target_rect
            if rect:
                l, t, r, b = rect
                w = max(1, int(r - l))
                h = max(1, int(b - t))
                win32gui.SetWindowPos(
                    self.mask_hwnd,
                    win32con.HWND_TOPMOST,
                    int(l),
                    int(t),
                    int(w),
                    int(h),
                    win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
                )
                win32gui.SetWindowPos(
                    self.fg_hwnd,
                    self.mask_hwnd,
                    int(l),
                    int(t),
                    int(w),
                    int(h),
                    win32con.SWP_SHOWWINDOW | win32con.SWP_NOACTIVATE,
                )
                if self._render is not None:
                    self._render["w"] = w
                    self._render["h"] = h
                win32gui.InvalidateRect(self.mask_hwnd, None, True)
                win32gui.InvalidateRect(self.fg_hwnd, None, True)
            else:
                win32gui.ShowWindow(self.mask_hwnd, win32con.SW_HIDE)
                win32gui.ShowWindow(self.fg_hwnd, win32con.SW_HIDE)

            time.sleep(0.03)

        for hwnd in [self.fg_hwnd, self.mask_hwnd]:
            try:
                if hwnd:
                    win32gui.DestroyWindow(hwnd)
            except Exception:
                pass
        try:
            if self._font:
                win32gui.DeleteObject(self._font)
        except Exception:
            pass
