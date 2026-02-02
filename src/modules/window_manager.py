import win32gui
import win32con
import win32api
import win32process
import re
import ctypes

class WindowManager:
    def __init__(self, logger):
        self.logger = logger
        self.target_hwnd = None
        self.target_title = None
        self.window_rect = None

    def enum_windows(self):
        """List all visible windows with titles."""
        windows = []
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append((hwnd, title))
        win32gui.EnumWindows(callback, windows)
        return windows

    def find_window_by_title(self, title_pattern):
        """Find a window by title using regex."""
        windows = self.enum_windows()
        for hwnd, title in windows:
            if re.search(title_pattern, title, re.IGNORECASE):
                return hwnd, title
        return None, None

    def select_window_by_pattern(self, pattern):
        """Select a window non-interactively by pattern."""
        hwnd, title = self.find_window_by_title(pattern)
        if hwnd:
            self.target_hwnd = hwnd
            self.target_title = title
            self.logger.info(f"Auto-selected window: {title}")
            return True
        else:
            self.logger.error(f"No window found matching pattern: {pattern}")
            return False

    def select_window_interactive(self):
        """Interactive selection of window (CLI based)."""
        windows = self.enum_windows()
        print("\nAvailable Windows:")
        valid_windows = []
        for i, (hwnd, title) in enumerate(windows):
            # Filter out empty or likely system windows for cleaner list
            if title and title != "Default IME" and title != "MSCTFIME UI":
                valid_windows.append((hwnd, title))
                print(f"{len(valid_windows)}. {title}")

        if not valid_windows:
            self.logger.warning("No visible windows found.")
            return False

        try:
            choice = input("\nEnter the number of the window to capture: ")
            index = int(choice) - 1
            if 0 <= index < len(valid_windows):
                self.target_hwnd = valid_windows[index][0]
                self.target_title = valid_windows[index][1]
                self.logger.info(f"Selected window: {valid_windows[index][1]}")
                return True
            else:
                self.logger.error("Invalid selection.")
                return False
        except ValueError:
            self.logger.error("Invalid input.")
            return False

    def get_window_rect(self):
        """Get the current rectangle of the target window."""
        if not self.target_hwnd:
            return None
        try:
            # GetWindowRect returns (left, top, right, bottom)
            rect = win32gui.GetWindowRect(self.target_hwnd)
            self.window_rect = rect
            return rect
        except Exception as e:
            self.logger.error(f"Error getting window rect: {e}")
            return None

    def get_client_screen_rect(self):
        """Get the current rectangle of the target window client area in screen coordinates."""
        if not self.target_hwnd:
            return None
        try:
            left, top, right, bottom = win32gui.GetClientRect(self.target_hwnd)
            screen_left, screen_top = win32gui.ClientToScreen(self.target_hwnd, (left, top))
            screen_right, screen_bottom = win32gui.ClientToScreen(self.target_hwnd, (right, bottom))
            return (screen_left, screen_top, screen_right, screen_bottom)
        except Exception as e:
            self.logger.error(f"Error getting client rect: {e}")
            return None

    def focus_window(self):
        """Bring the target window to foreground using advanced techniques."""
        if not self.target_hwnd:
            return False
        
        try:
            if win32gui.IsIconic(self.target_hwnd):
                win32gui.ShowWindow(self.target_hwnd, win32con.SW_RESTORE)
            
            win32gui.ShowWindow(self.target_hwnd, win32con.SW_SHOW)
            win32gui.SetWindowPos(
                self.target_hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )

            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd == self.target_hwnd:
                return True
                
            current_tid = win32api.GetCurrentThreadId()
            foreground_tid = win32process.GetWindowThreadProcessId(foreground_hwnd)[0]
            
            attached = False
            if current_tid != foreground_tid:
                ctypes.windll.user32.AttachThreadInput(foreground_tid, current_tid, True)
                attached = True
            
            try:
                win32gui.SetForegroundWindow(self.target_hwnd)
                win32gui.BringWindowToTop(self.target_hwnd)
                ctypes.windll.user32.SwitchToThisWindow(self.target_hwnd, True)
            finally:
                if attached:
                    ctypes.windll.user32.AttachThreadInput(foreground_tid, current_tid, False)
            
            return True
        except Exception as e:
            self.logger.error(f"Error focusing window: {e}")
            return False

    def find_input_window(self, root_hwnd):
        """Recursively find the best child window for input events."""
        best_hwnd = root_hwnd
        max_area = 0
        
        def callback(hwnd, _):
            nonlocal best_hwnd, max_area
            if win32gui.IsWindowVisible(hwnd):
                rect = win32gui.GetWindowRect(hwnd)
                area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                # Heuristic: Input window is usually large but smaller than root
                # And usually has a class name suggesting it renders content (e.g. Chrome_RenderWidgetHostHWND)
                # For now, we just pick the largest visible child that isn't the root itself
                if area > max_area:
                    max_area = area
                    best_hwnd = hwnd
        
        try:
            win32gui.EnumChildWindows(root_hwnd, callback, None)
            if best_hwnd != root_hwnd:
                self.logger.info(f"Found child input window: {best_hwnd} (Parent: {root_hwnd})")
            return best_hwnd
        except Exception as e:
            self.logger.error(f"Error finding child window: {e}")
            return root_hwnd
