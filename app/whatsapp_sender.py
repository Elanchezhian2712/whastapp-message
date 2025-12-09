import time
import os
import logging
import pyperclip
from typing import List, Dict

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from app.utils.message_variation import mutate_message
from app.utils.safe_delays import human_delay, batch_pause

# LOGGING SETUP
logger = logging.getLogger("whatsapp_sender")
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler("logs/whatsapp_sender.log")
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
fh.setFormatter(formatter)
logger.addHandler(fh)


class WhatsAppSender:
    def __init__(self):
        self.driver = None
        self.running = False
        self.events = []

    # -------------------------------------------------------------
    def start(self):
        """Start undetected Chrome with saved WhatsApp session"""
        profile_path = os.path.abspath("data/selenium_session")
        logger.info(f"Using Chrome profile: {profile_path}")

        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--start-maximized")

        self.driver = uc.Chrome(options=options)
        logger.info("Undetected Chrome started.")

        self.running = True

    # -------------------------------------------------------------
    def ensure_login(self):
        """Open WhatsApp Web and wait until the user is logged in."""
        self.driver.get("https://web.whatsapp.com")
        logger.info("Waiting for WhatsApp login...")

        while True:
            try:
                self.driver.find_element(By.XPATH, '//div[@role="textbox"]')
                logger.info("WhatsApp logged in successfully.")
                break
            except:
                time.sleep(1)

    # -------------------------------------------------------------
    def close_popups(self):
        """Close any dialog/popups that block clicking the message box."""
        try:
            popups = self.driver.find_elements(
                By.XPATH, '//div[@role="dialog"]//button'
            )
            for p in popups:
                try:
                    p.click()
                    logger.info("Closed WhatsApp popup.")
                except:
                    pass
        except:
            pass

    # -------------------------------------------------------------
    def find_message_box(self):
        """Find the WhatsApp message input box."""
        selectors = [
            '//div[@aria-label="Type a message"]',
            '//footer//div[@contenteditable="true"]',
            '//div[contains(@class,"selectable-text") and @contenteditable="true"]'
        ]

        for s in selectors:
            try:
                return self.driver.find_element(By.XPATH, s)
            except:
                pass

        return None

    # -------------------------------------------------------------
    def open_chat(self, phone: str) -> bool:
        """Open WhatsApp chat using phone link"""

        clean = phone.replace("+", "").strip()
        url = (
            f"https://web.whatsapp.com/send/?phone={clean}&type=phone_number&app_absent=0"
        )

        logger.info(f"Opening chat for {clean}")
        self.driver.get(url)

        timeout = time.time() + 20

        while time.time() < timeout:
            page = self.driver.page_source.lower()

            if "phone number shared via url is invalid" in page:
                logger.error(f"Invalid WhatsApp number: {phone}")
                return False

            try:
                self.driver.find_element(By.XPATH, '//canvas[contains(@aria-label,"Loading")]')
                time.sleep(1)
                continue
            except:
                pass

            # Chat is ready
            box = self.find_message_box()
            if box:
                return True

            time.sleep(1)

        logger.error(f"Timeout while opening chat for {phone}")
        return False

    # -------------------------------------------------------------
    def send_text(self, phone: str, message: str) -> bool:
        """Send text message via clipboard paste (fixes BMP/emoji issues)"""

        if not self.open_chat(phone):
            self.events.append({"event": "failed", "phone": phone})
            return False

        self.close_popups()

        box = self.find_message_box()
        if box is None:
            logger.error("Message box not found for %s", phone)
            self.events.append({"event": "failed", "phone": phone})
            return False

        try:
            # Copy message to clipboard
            pyperclip.copy(message)

            # Ensure box visible
            self.driver.execute_script(
                "arguments[0].scrollIntoView(true);", box
            )
            box.click()
            time.sleep(0.2)

            # Paste (handles all Unicode/emojis)
            box.send_keys(Keys.CONTROL, 'v')
            time.sleep(0.3)

            # Send
            box.send_keys(Keys.ENTER)
            time.sleep(0.8)

            logger.info("Message sent to %s", phone)
            self.events.append({"event": "sent", "phone": phone})
            return True

        except Exception as e:
            logger.error(f"Failed to send message to {phone}: {e}")
            self.events.append({"event": "failed", "phone": phone})
            return False

    # -------------------------------------------------------------
    def send_bulk(self, contacts: List[Dict], template: str, batch_size=30):
        results = []
        total = len(contacts)
        logger.info(f"Bulk sending to {total} contacts...")

        for c in contacts:
            phone = c["mobile"]
            name = c.get("name", "")
            link = c.get("link", "")

            msg = mutate_message(template, name, link)
            ok = self.send_text(phone, msg)
            results.append(ok)

            human_delay(1.2, 2.0)

        logger.info("Bulk sending finished.")
        return results

    # -------------------------------------------------------------
    def get_events(self):
        return self.events[-200:]

    # -------------------------------------------------------------
    def stop(self):
        try:
            self.driver.quit()
        except:
            pass
        self.running = False
