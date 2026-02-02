import win32gui


class CoordinateSpace:
    def __init__(self, hwnd=None):
        self.hwnd = hwnd

    def set_target(self, hwnd):
        self.hwnd = hwnd

    def get_client_size(self):
        if not self.hwnd:
            return 0, 0
        l, t, r, b = win32gui.GetClientRect(self.hwnd)
        return int(r - l), int(b - t)

    def get_client_screen_rect(self):
        if not self.hwnd:
            return None
        l, t, r, b = win32gui.GetClientRect(self.hwnd)
        sl, st = win32gui.ClientToScreen(self.hwnd, (l, t))
        sr, sb = win32gui.ClientToScreen(self.hwnd, (r, b))
        return (int(sl), int(st), int(sr), int(sb))

    def client_to_screen(self, x, y):
        if not self.hwnd:
            return int(x), int(y)
        sx, sy = win32gui.ClientToScreen(self.hwnd, (int(x), int(y)))
        return int(sx), int(sy)

    def screen_to_client(self, x, y):
        if not self.hwnd:
            return int(x), int(y)
        cx, cy = win32gui.ScreenToClient(self.hwnd, (int(x), int(y)))
        return int(cx), int(cy)
