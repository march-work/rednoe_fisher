import sys
import time
import os

# Add src to python path to allow imports if running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.logger import setup_logger
from src.utils.config_loader import ConfigLoader
from src.modules.window_manager import WindowManager
from src.modules.vision_engine import VisionEngine
from src.modules.interaction_simulator import InteractionSimulator
from src.modules.data_processor import DataProcessor

def main():
    # 1. Initialize
    logger = setup_logger()
    logger.info("Starting Fisher - Xiaohongshu Scraper")
    
    try:
        config_loader = ConfigLoader()
        logger.info("Configuration loaded")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # 2. Setup Modules
    window_manager = WindowManager(logger)
    vision_engine = VisionEngine(logger, config_loader.get_ocr_config())
    interaction = InteractionSimulator(logger, config_loader.get_scroll_config())
    data_processor = DataProcessor(logger, config_loader.get_output_config())

    # 3. Window Selection
    logger.info("Please select the target window (Browser or Emulator)...")
    if not window_manager.select_window_interactive():
        logger.error("No window selected. Exiting.")
        return

    # Focus window
    window_manager.focus_window()
    time.sleep(1) # Wait for window to come to front

    # 4. Main Loop (Simplified for Demo)
    logger.info("Starting main scraping loop. Press Ctrl+C to stop.")
    try:
        while True:
            # Get Window Rect
            rect = window_manager.get_window_rect()
            if not rect:
                logger.error("Window lost.")
                break

            # Capture Screen
            logger.info("Capturing screen...")
            image = vision_engine.capture_screen(rect)
            
            # OCR & Analyze
            text = vision_engine.extract_text(image)
            logger.info(f"Extracted text length: {len(text)}")
            
            # Keyword Matching
            keywords = config_loader.get("keywords", [])
            matched = [k for k in keywords if k in text]
            
            if matched:
                logger.info(f"Found keywords: {matched}")
                # TODO: Implement precise click logic based on text location
                # For now, we just simulate the "found" event and save dummy data
                
                data = {
                    "title": "Detected Title Placeholder", # Needs more complex parsing
                    "content": text[:100] + "...",
                    "keywords_matched": matched,
                    "source_type": "desktop"
                }
                data_processor.save_post(data)
                
                # Simulate interaction (e.g. scroll down to see more)
                interaction.scroll_down(rect[0] + 100, rect[1] + 100)
            else:
                logger.info("No keywords found. Scrolling...")
                interaction.scroll_down(rect[0] + 100, rect[1] + 100)

            # Pause between iterations
            time.sleep(2)

    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
