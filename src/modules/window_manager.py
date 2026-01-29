import win32gui
import win32con
import re

class WindowManager:
    def __init__(self, logger):
        self.logger = logger
        self.target_hwnd = None
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

    def focus_window(self):
        """Bring the target window to foreground."""
        if not self.target_hwnd:
            return False
        try:
            win32gui.ShowWindow(self.target_hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(self.target_hwnd)
            return True
        except Exception as e:
            self.logger.error(f"Error focusing window: {e}")
            return False
