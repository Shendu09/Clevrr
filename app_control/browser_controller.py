"""Browser controller using Playwright.

Controls any browser without extensions.
Supports all major browsers on all platforms.
"""

import logging

logger = logging.getLogger(__name__)


class BrowserController:
    """Playwright-based browser automation."""

    def __init__(self):
        try:
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()
            self.browser = None
            self.page = None
            self._connect_to_existing_browser()
        except ImportError:
            raise ImportError(
                "playwright not installed. Run: pip install playwright"
            )

    def _connect_to_existing_browser(self):
        """Try to connect to already-running browser, or launch new one."""
        try:
            self.browser = self.playwright.chromium.connect_over_cdp(
                "http://localhost:9222"
            )
            contexts = self.browser.contexts
            if contexts:
                self.page = contexts[0].pages[0]
                logger.info("Connected to existing browser")
                return
        except Exception:
            pass

        # Open new browser if none running
        self.browser = self.playwright.chromium.launch(
            headless=False,
            args=["--remote-debugging-port=9222"],
        )
        context = self.browser.new_context()
        self.page = context.new_page()
        logger.info("Launched new browser")

    def navigate(self, url: str) -> dict:
        """Navigate to URL."""
        try:
            if not url.startswith("http"):
                url = "https://" + url
            self.page.goto(url, wait_until="domcontentloaded")
            return {"success": True, "url": url}
        except Exception as exc:
            logger.error(f"Navigate failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def search(self, query: str) -> dict:
        """Search via Google."""
        return self.navigate(f"https://www.google.com/search?q={query}")

    def click_element(self, description: str) -> dict:
        """Click element by description."""
        try:
            selectors = [
                f'[aria-label*="{description}" i]',
                f'[placeholder*="{description}" i]',
                f'button:has-text("{description}")',
                f'a:has-text("{description}")',
                f'[title*="{description}" i]',
            ]

            for selector in selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible():
                        element.click()
                        return {"success": True}
                except Exception:
                    continue

            return {
                "success": False,
                "reason": f"Element not found: {description}",
            }
        except Exception as exc:
            logger.error(f"Click element failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def fill_field(self, field_description: str, value: str) -> dict:
        """Fill input field by description."""
        try:
            selectors = [
                f'input[placeholder*="{field_description}" i]',
                f'textarea[placeholder*="{field_description}" i]',
                f'[aria-label*="{field_description}" i]',
            ]

            for selector in selectors:
                try:
                    element = self.page.locator(selector).first
                    if element.is_visible():
                        element.fill(value)
                        return {"success": True}
                except Exception:
                    continue

            return {"success": False, "reason": "Field not found"}
        except Exception as exc:
            logger.error(f"Fill field failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def read_content(self) -> dict:
        """Read all visible text from page."""
        try:
            content = self.page.evaluate("() => document.body.innerText")
            return {"success": True, "content": content[:5000]}
        except Exception as exc:
            logger.error(f"Read content failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def new_tab(self) -> dict:
        """Open new tab."""
        try:
            self.page = self.browser.contexts[0].new_page()
            return {"success": True}
        except Exception as exc:
            logger.error(f"New tab failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def close_tab(self) -> dict:
        """Close current tab."""
        try:
            self.page.close()
            pages = self.browser.contexts[0].pages
            if pages:
                self.page = pages[-1]
            return {"success": True}
        except Exception as exc:
            logger.error(f"Close tab failed: {exc}")
            return {"success": False, "reason": str(exc)}

    def get_current_url(self) -> str:
        """Get current page URL."""
        try:
            return self.page.url
        except Exception:
            return ""

    def take_screenshot(self) -> str:
        """Take screenshot of current page."""
        import os
        from datetime import datetime

        os.makedirs("data/screenshots", exist_ok=True)
        path = (
            f"data/screenshots/"
            f"browser_{datetime.now().strftime('%H%M%S')}"
            f".png"
        )
        self.page.screenshot(path=path)
        return path
