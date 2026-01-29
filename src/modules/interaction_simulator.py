import pyautogui
import time
import random

class InteractionSimulator:
    def __init__(self, logger, scroll_config):
        self.logger = logger
        self.config = scroll_config
        # Fail-safe: moving mouse to upper-left corner will abort
        pyautogui.FAILSAFE = True

    def _random_sleep(self, min_time=None, max_time=None):
        if min_time is None:
            min_time = self.config.get("pause_range", [1.0, 3.0])[0]
        if max_time is None:
            max_time = self.config.get("pause_range", [1.0, 3.0])[1]
        
        sleep_time = random.uniform(min_time, max_time)
        time.sleep(sleep_time)

    def click(self, x, y):
        """Simulate a mouse click at specific coordinates."""
        try:
            self.logger.info(f"Clicking at ({x}, {y})")
            pyautogui.click(x, y)
            self._random_sleep(0.5, 1.0)
        except Exception as e:
            self.logger.error(f"Click failed: {e}")

    def scroll_down(self, x, y, distance=300):
        """Simulate scrolling down (drag up)."""
        try:
            speed_range = self.config.get("speed_range", [0.5, 1.5])
            duration = random.uniform(speed_range[0], speed_range[1])
            
            self.logger.info("Scrolling down...")
            # Move to start position
            pyautogui.moveTo(x, y)
            
            # Drag up to scroll down
            # Using dragRel or dragTo. 
            # Note: For mobile emulators/touch interfaces, "scroll down" usually means "swipe up".
            pyautogui.dragRel(0, -distance, duration=duration, button='left')
            
            self._random_sleep()
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")

    def scroll_up(self, x, y, distance=300):
        """Simulate scrolling up (drag down)."""
        try:
            speed_range = self.config.get("speed_range", [0.5, 1.5])
            duration = random.uniform(speed_range[0], speed_range[1])
            
            self.logger.info("Scrolling up...")
            pyautogui.moveTo(x, y)
            pyautogui.dragRel(0, distance, duration=duration, button='left')
            
            self._random_sleep()
        except Exception as e:
            self.logger.error(f"Scroll failed: {e}")

    def return_back(self):
        """Simulate return/back action (could be a specific key or button)."""
        # This implementation depends on context. Often ESC works or a specific back button.
        # For now, let's assume we might need to find a back button or use a key.
        # Using ESC as a generic "back" for now.
        self.logger.info("Pressing ESC to go back...")
        pyautogui.press('esc')
        self._random_sleep()
