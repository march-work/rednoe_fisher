import win32gui
import win32con
import win32api
import threading
import time

class VisualOverlay:
    def __init__(self):
        self.hwnd = None
        self.running = False
        self.thread = None
        self._target_pos = None # (x, y) or None to hide

    def start(self):
        """Start the overlay thread."""
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_PAINT:
            hdc, paint_struct = win32gui.BeginPaint(hwnd)
            # Draw a semi-transparent white circle
            # Note: For pure white, we use RGB(255, 255, 255).
            # The transparency is handled by SetLayeredWindowAttributes(LWA_ALPHA)
            brush = win32gui.CreateSolidBrush(win32api.RGB(255, 255, 255)) 
            old_brush = win32gui.SelectObject(hdc, brush)
            win32gui.Ellipse(hdc, 0, 0, 20, 20)
            win32gui.SelectObject(hdc, old_brush)
            win32gui.DeleteObject(brush)
            win32gui.EndPaint(hwnd, paint_struct)
            return 0
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _run_loop(self):
        """Main Win32 GUI loop."""
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "FisherOverlay"
        wc.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        wc.hbrBackground = win32gui.GetStockObject(win32con.NULL_BRUSH) # Transparent bg logic requires layered
        
        try:
            class_atom = win32gui.RegisterClass(wc)
        except Exception:
            class_atom = win32gui.GetClassInfo(win32api.GetModuleHandle(None), "FisherOverlay")

        # Create Layered Window (Transparent)
        # WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW (no taskbar icon) | WS_EX_TRANSPARENT (click through)
        ex_style = win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST | win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TRANSPARENT
        style = win32con.WS_POPUP
        
        self.hwnd = win32gui.CreateWindowEx(
            ex_style,
            class_atom,
            "FisherOverlay",
            style,
            0, 0, 20, 20,
            0, 0, 0, None
        )

        # Set transparency key (Black 0x000000 will be transparent)
        # Or simply use SetLayeredWindowAttributes with LWA_COLORKEY
        # Make the window semi-transparent overall (alpha=200) or just color key?
        # Let's use Color Key for full transparency of background, but we need a background color.
        # But we didn't paint background.
        
        # Simpler approach for "Dot":
        # Make the whole window Red, then apply Alpha.
        # Or better: Use SetWindowRgn to make it round?
        # Let's stick to Layered + ColorKey.
        
        # Set window background to Black (Key) and draw Red circle.
        # Actually in WM_PAINT we only drew circle.
        # Let's set the whole window to be Red and Round using Region.
        
        # Create a round region
        # win32gui.CreateEllipticRgn is not available in all pywin32 builds or requires specific import
        # Let's simplify and skip SetWindowRgn. We rely on WM_PAINT drawing a circle and LWA_COLORKEY if needed
        # Or just a semi-transparent square window is fine for debug purpose if EllipticRgn fails.
        # But wait, we can try to use CreateEllipticRgn from gdi32 via ctypes if needed, 
        # or just simply not set the region and have a square overlay with a drawn circle.
        
        # Set background color (Solid Red)
        try:
            # Try SetClassLongPtr first (64-bit safe)
            # Note: pywin32 might not expose SetClassLongPtr directly or maps SetClassLong to it.
            # If SetClassLong fails, we catch it.
            # Actually, we don't strictly need to set the background brush if we draw everything in WM_PAINT
            # or if we accept default background.
            # Let's just try to skip this if it fails, or use a safer GDI object.
            
            # Alternative: Don't set class background, just let WM_PAINT handle it.
            # But if we don't set it, the background might be unpainted/garbage until WM_PAINT.
            pass
        except:
            pass
        
        # Set Layered attributes (Alpha)
        # We use a try-block here too just in case
        try:
            win32gui.SetLayeredWindowAttributes(self.hwnd, 0, 180, win32con.LWA_ALPHA)
        except Exception as e:
            print(f"Overlay warning: Failed to set transparency: {e}")

        # Main Loop
        last_pos = None
        
        while self.running:
            # Handle Windows messages
            if win32gui.PumpWaitingMessages():
                break

            # Update position
            if self._target_pos:
                x, y = self._target_pos
                # Move window
                win32gui.SetWindowPos(self.hwnd, win32con.HWND_TOPMOST, int(x)-10, int(y)-10, 0, 0, win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
            else:
                # Hide
                win32gui.ShowWindow(self.hwnd, win32con.SW_HIDE)
            
            time.sleep(0.01)

        win32gui.DestroyWindow(self.hwnd)

    def show_dot(self, x, y):
        """Move dot to x, y and show it."""
        self._target_pos = (x, y)

    def hide_dot(self):
        """Hide the dot."""
        self._target_pos = None

    def stop(self):
        self.running = False
