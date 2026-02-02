import win32gui
import win32con
import win32api
import time
import random

from src.utils.overlay import VisualOverlay

class InteractionSimulator:
    def __init__(self, logger, scroll_config):
        self.logger = logger
        self.config = scroll_config
        self.hwnd = None
        self.overlay = VisualOverlay()
        # Start overlay thread
        self.overlay.start()

    def set_target_window(self, hwnd):
        """Set the target window handle for background interaction."""
        self.hwnd = hwnd
        self.logger.info(f"Interaction target set to HWND: {hwnd}")

    def _get_client_center(self):
        """Get the center coordinates of the client area."""
        if not self.hwnd:
            return 0, 0
        try:
            rect = win32gui.GetClientRect(self.hwnd)
            # rect is (left, top, right, bottom). left/top are always 0 for client rect
            width = rect[2]
            height = rect[3]
            return width // 2, height // 2
        except Exception as e:
            self.logger.error(f"Failed to get client rect: {e}")
            return 0, 0

    def _client_to_screen(self, x, y):
        """Convert client coordinates to screen coordinates."""
        if not self.hwnd:
            return x, y
        try:
            point = win32gui.ClientToScreen(self.hwnd, (int(x), int(y)))
            return point
        except:
            return x, y

    def _make_lparam(self, x, y):
        """Construct the LPARAM for Windows messages (y << 16 | x)."""
        return (int(y) << 16) | (int(x) & 0xFFFF)

    def _random_sleep(self, min_time=None, max_time=None):
        if min_time is None:
            min_time = self.config.get("pause_range", [1.0, 3.0])[0]
        if max_time is None:
            max_time = self.config.get("pause_range", [1.0, 3.0])[1]
        
        sleep_time = random.uniform(min_time, max_time)
        time.sleep(sleep_time)

    def click(self, x=None, y=None):
        """Simulate a background mouse click at specific client coordinates."""
        if not self.hwnd:
            self.logger.error("No target window set for interaction")
            return

        if x is None or y is None:
            x, y = self._get_client_center()

        # Show visual feedback
        sx, sy = self._client_to_screen(x, y)
        self.overlay.show_dot(sx, sy)

        lparam = self._make_lparam(x, y)
        try:
            self.logger.info(f"Background Clicking at ({x}, {y})")
            # PostMessage is non-blocking and safer for background interaction
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lparam)
            time.sleep(random.uniform(0.05, 0.15)) # Short hold
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, lparam)
            
            self._random_sleep(0.5, 1.0)
        except Exception as e:
            self.logger.error(f"Click failed: {e}")
        finally:
            self.overlay.hide_dot()

    def scroll_down(self, start_x=None, start_y=None, distance=None):
        """
        Simulate scrolling down by dragging UP in the background.
        Coordinates are relative to the client area (not screen).
        """
        if not self.hwnd:
             self.logger.error("No target window set")
             return

        try:
            cx, cy = self._get_client_center()
            rect = win32gui.GetClientRect(self.hwnd)
            height = rect[3]

            # Default to swiping from bottom 3/4 to top 1/4 (Swipe Up)
            if start_x is None: start_x = cx
            if start_y is None: start_y = int(height * 0.75)
            
            if distance is None:
                distance = int(height * 0.4) 

            end_y = start_y - distance
            if end_y < 10: end_y = 10

            self.logger.info(f"Background Scrolling down (Drag {start_x},{start_y} -> {start_x},{end_y})...")
            
            # Show overlay at start
            sx, sy = self._client_to_screen(start_x, start_y)
            self.overlay.show_dot(sx, sy)

            speed_range = self.config.get("speed_range", [0.5, 1.5])
            duration = random.uniform(speed_range[0], speed_range[1])
            step_count = int(duration * 20) 
            if step_count < 10: step_count = 10 # More steps for smooth drag

            # 1. Mouse Down
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, self._make_lparam(start_x, start_y))
            time.sleep(0.05)

            # 2. Mouse Move (Drag)
            for i in range(step_count):
                curr_y = int(start_y + (end_y - start_y) * (i + 1) / step_count)
                
                # Update overlay
                sx, sy = self._client_to_screen(start_x, curr_y)
                self.overlay.show_dot(sx, sy)

                win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, self._make_lparam(start_x, curr_y))
                time.sleep(duration / step_count)

            # 3. Mouse Up
            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, self._make_lparam(start_x, end_y))
            
            self._random_sleep()
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")
        finally:
            self.overlay.hide_dot()

    def scroll_down_wheel(self, clicks=3):
        if not self.hwnd:
            self.logger.error("No target window set")
            return

        try:
            cx, cy = self._get_client_center()
            sx, sy = self._client_to_screen(cx, cy)
            self.overlay.show_dot(sx, sy)

            delta = -120 * int(clicks)
            wparam = (delta << 16) & 0xFFFFFFFF
            lparam = self._make_lparam(sx, sy)
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
            self._random_sleep()
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")
        finally:
            self.overlay.hide_dot()

    def scroll_up(self, start_x=None, start_y=None, distance=None):
        """Simulate scrolling up by dragging DOWN in the background."""
        if not self.hwnd:
             return

        try:
            cx, cy = self._get_client_center()
            rect = win32gui.GetClientRect(self.hwnd)
            height = rect[3]

            if start_x is None: start_x = cx
            if start_y is None: start_y = int(height * 0.25)
            
            if distance is None:
                distance = int(height * 0.4)

            end_y = start_y + distance
            if end_y > height - 10: end_y = height - 10

            self.logger.info("Background Scrolling up (Drag)...")
            
            sx, sy = self._client_to_screen(start_x, start_y)
            self.overlay.show_dot(sx, sy)

            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, self._make_lparam(start_x, start_y))
            time.sleep(0.05)
            
            steps = 10
            for i in range(steps):
                curr_y = int(start_y + (end_y - start_y) * (i + 1) / steps)
                
                sx, sy = self._client_to_screen(start_x, curr_y)
                self.overlay.show_dot(sx, sy)

                win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEMOVE, win32con.MK_LBUTTON, self._make_lparam(start_x, curr_y))
                time.sleep(0.02)

            win32gui.PostMessage(self.hwnd, win32con.WM_LBUTTONUP, 0, self._make_lparam(start_x, end_y))
            
            self._random_sleep()
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")
        finally:
            self.overlay.hide_dot()

    def scroll_up_wheel(self, clicks=3):
        if not self.hwnd:
            return

        try:
            cx, cy = self._get_client_center()
            sx, sy = self._client_to_screen(cx, cy)
            self.overlay.show_dot(sx, sy)

            delta = 120 * int(clicks)
            wparam = (delta << 16) & 0xFFFFFFFF
            lparam = self._make_lparam(sx, sy)
            win32gui.PostMessage(self.hwnd, win32con.WM_MOUSEWHEEL, wparam, lparam)
            self._random_sleep()
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")
        finally:
            self.overlay.hide_dot()


    def return_back(self):
        """Simulate ESC key for back."""
        if not self.hwnd:
            return
        self.logger.info("Sending ESC key background...")
        # WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101, VK_ESCAPE = 0x1B
        win32gui.PostMessage(self.hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
        time.sleep(0.1)
        win32gui.PostMessage(self.hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
        self._random_sleep()
