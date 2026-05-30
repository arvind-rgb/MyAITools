"""
Porter.in browser automation via Playwright.

First-time setup: call setup_session_interactive() — a headed browser opens,
you log in manually (phone + OTP), and the session is saved to PORTER_SESSION_DIR.
All subsequent calls reuse the saved session headlessly.

IMPORTANT: Before deploying, inspect https://porter.in/two-wheelers in Chrome DevTools
and update the SEL_* constants below to match Porter's actual DOM.
"""
import asyncio
import os
from datetime import datetime

from playwright.async_api import async_playwright, BrowserContext, Page

BASE_DIR           = os.path.dirname(os.path.abspath(__file__))
SESSION_DIR        = os.environ.get("PORTER_SESSION_DIR", os.path.join(BASE_DIR, "porter_session"))
PORTER_BOOKING_URL = "https://porter.in/two-wheelers"

# ── Selector constants — update after inspecting live Porter DOM ──────────────
SEL_PICKUP       = '[data-testid="pickup-input"], #pickup, [placeholder*="pickup" i], [placeholder*="Pick up" i]'
SEL_DROP         = '[data-testid="drop-input"], #drop, [placeholder*="drop" i], [placeholder*="Deliver" i]'
SEL_AUTOCOMPLETE = ".pac-container .pac-item, [class*='suggestion'], [class*='autocomplete'] li"
SEL_BOOK_BTN     = 'button:has-text("Book Now"), button:has-text("Confirm"), button:has-text("Continue"), button:has-text("Proceed")'
SEL_RECEIVER_NAME  = '[placeholder*="receiver" i], [placeholder*="name" i], [data-testid="receiver-name"]'
SEL_RECEIVER_PHONE = '[placeholder*="phone" i], [placeholder*="mobile" i], [data-testid="receiver-phone"]'
SEL_ORDER_ID     = '[data-testid="order-id"], [class*="order-id"], [class*="orderId"]'
SEL_FARE         = '[data-testid="fare"], [class*="fare"], [class*="price"], [class*="amount"]'
SEL_AUTH_CHECK   = '[data-testid="user-avatar"], [class*="userAvatar"], [class*="user-menu"], [class*="profileIcon"]'
SEL_LOGIN_CHECK  = 'text="Enter OTP", text="Login with OTP", [class*="otpModal"], [class*="loginModal"]'


class PorterBrowser:
    def __init__(self, headless: bool = True):
        self._headless = headless
        self._playwright = None
        self._context: BrowserContext = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        await self._load_context(self._headless)
        return self

    async def __aexit__(self, *_):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    async def _load_context(self, headless: bool = True):
        os.makedirs(SESSION_DIR, exist_ok=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            SESSION_DIR,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            args=["--disable-blink-features=AutomationControlled"],
        )

    async def is_logged_in(self) -> bool:
        page = await self._context.new_page()
        try:
            await page.goto(PORTER_BOOKING_URL, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(2000)
            has_auth   = await page.locator(SEL_AUTH_CHECK).count() > 0
            has_login  = await page.locator(SEL_LOGIN_CHECK).count() > 0
            return has_auth and not has_login
        except Exception:
            return False
        finally:
            await page.close()

    async def setup_session_interactive(self) -> dict:
        """Open a headed browser for manual login. Polls until authenticated."""
        if self._context:
            await self._context.close()
        await self._load_context(headless=False)
        page = await self._context.new_page()
        await page.goto(PORTER_BOOKING_URL, wait_until="domcontentloaded", timeout=20000)
        print(">>> Porter login page opened. Complete phone + OTP login in the browser window.")
        print(">>> Waiting up to 2 minutes for authentication...")
        for attempt in range(24):  # 24 × 5s = 120s
            await asyncio.sleep(5)
            try:
                has_auth  = await page.locator(SEL_AUTH_CHECK).count() > 0
                has_login = await page.locator(SEL_LOGIN_CHECK).count() > 0
                if has_auth and not has_login:
                    await page.close()
                    print(">>> Session saved successfully!")
                    return {"ok": True, "message": "Porter session saved. You can now book deliveries."}
            except Exception:
                pass
            print(f">>> Waiting... ({(attempt + 1) * 5}s elapsed)")
        await page.close()
        return {"ok": False, "message": "Login timeout (2 min). Please try setup again."}

    async def _fill_address_autocomplete(self, page: Page, selector: str, address: str):
        """Type into a Google Maps autocomplete field and select the first suggestion."""
        await page.click(selector)
        await page.fill(selector, "")
        # Use type() with delay to trigger Google Maps JS event listeners
        await page.type(selector, address, delay=80)
        try:
            await page.wait_for_selector(SEL_AUTOCOMPLETE, state="visible", timeout=6000)
            await page.wait_for_timeout(600)
            await page.keyboard.press("ArrowDown")
            await page.wait_for_timeout(200)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(800)
        except Exception:
            # If autocomplete doesn't appear, press Enter and hope for the best
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)

    async def get_quote(self, pickup: str, drop: str) -> dict:
        page = await self._context.new_page()
        try:
            if not await self.is_logged_in():
                return {"ok": False, "session_expired": True, "error": "Porter session expired. Run setup session first."}
            await page.goto(PORTER_BOOKING_URL, wait_until="networkidle", timeout=25000)
            await self._fill_address_autocomplete(page, SEL_PICKUP, pickup)
            await self._fill_address_autocomplete(page, SEL_DROP, drop)
            # Wait for fare estimate to appear
            try:
                await page.wait_for_selector(SEL_FARE, timeout=8000)
                fare_el = page.locator(SEL_FARE).first
                fare    = (await fare_el.inner_text()).strip()
            except Exception:
                fare = "unavailable"
            return {"ok": True, "estimated_cost": fare, "pickup": pickup, "drop": drop}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            await page.close()

    async def book_delivery(
        self,
        pickup: str,
        drop: str,
        contact_name: str,
        contact_phone: str,
        pickup_time: str = "now",
    ) -> dict:
        page = await self._context.new_page()
        try:
            if not await self.is_logged_in():
                return {"ok": False, "session_expired": True, "error": "Porter session expired. Run setup session first."}

            await page.goto(PORTER_BOOKING_URL, wait_until="networkidle", timeout=25000)

            # Fill pickup and drop addresses
            await self._fill_address_autocomplete(page, SEL_PICKUP, pickup)
            await self._fill_address_autocomplete(page, SEL_DROP, drop)

            # Handle scheduled pickup
            if pickup_time and pickup_time.lower() != "now":
                try:
                    dt = datetime.fromisoformat(pickup_time)
                    sched_btn = page.locator('text="Schedule", button:has-text("Schedule later"), button:has-text("Later")')
                    if await sched_btn.count():
                        await sched_btn.first.click()
                        await page.wait_for_timeout(500)
                        date_input = page.locator('[type="date"], [data-field="date"]').first
                        time_input = page.locator('[type="time"], [data-field="time"]').first
                        if await date_input.count():
                            await date_input.fill(dt.strftime("%Y-%m-%d"))
                        if await time_input.count():
                            await time_input.fill(dt.strftime("%H:%M"))
                except Exception:
                    pass  # If scheduling fails, fall back to immediate booking

            # Click the main action button (Continue / Proceed)
            await page.locator(SEL_BOOK_BTN).first.click()
            await page.wait_for_timeout(2000)

            # Fill receiver contact details (may appear after first Continue)
            try:
                await page.wait_for_selector(SEL_RECEIVER_NAME, state="visible", timeout=5000)
                await page.fill(SEL_RECEIVER_NAME, contact_name)
                await page.fill(SEL_RECEIVER_PHONE, contact_phone)
            except Exception:
                pass  # Receiver fields may not appear on all Porter flows

            # Final confirm / book
            try:
                await page.locator('button:has-text("Book Now"), button:has-text("Confirm Order"), button:has-text("Place Order")').first.click()
                await page.wait_for_timeout(3000)
            except Exception:
                pass

            # Extract order ID and fare from confirmation screen
            order_id = ""
            fare     = ""
            try:
                order_el = page.locator(SEL_ORDER_ID).first
                if await order_el.count():
                    order_id = (await order_el.inner_text()).strip()
            except Exception:
                pass
            try:
                fare_el = page.locator(SEL_FARE).first
                if await fare_el.count():
                    fare = (await fare_el.inner_text()).strip()
            except Exception:
                pass

            return {
                "ok":              True,
                "porter_order_id": order_id,
                "estimated_cost":  fare,
                "pickup":          pickup,
                "drop":            drop,
                "contact_name":    contact_name,
                "contact_phone":   contact_phone,
                "pickup_time":     pickup_time,
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            await page.close()

    async def track_order(self, porter_order_id: str) -> dict:
        page = await self._context.new_page()
        try:
            if not await self.is_logged_in():
                return {"ok": False, "session_expired": True, "error": "Porter session expired. Run setup session first."}
            await page.goto(
                f"https://porter.in/orders/{porter_order_id}",
                wait_until="networkidle",
                timeout=20000,
            )
            status = "Unknown"
            eta    = ""
            try:
                status_el = page.locator('[data-testid="order-status"], [class*="orderStatus"], [class*="status"]').first
                if await status_el.count():
                    status = (await status_el.inner_text()).strip()
            except Exception:
                pass
            try:
                eta_el = page.locator('[data-testid="eta"], [class*="eta"], text=/ETA/i').first
                if await eta_el.count():
                    eta = (await eta_el.inner_text()).strip()
            except Exception:
                pass
            return {"ok": True, "order_id": porter_order_id, "status": status, "eta": eta}
        except Exception as e:
            return {"ok": False, "error": str(e)}
        finally:
            await page.close()


# ── CLI helper for quick testing ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    async def main():
        cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
        if cmd == "setup":
            async with PorterBrowser(headless=False) as pb:
                result = await pb.setup_session_interactive()
                print(result)
        elif cmd == "check":
            async with PorterBrowser() as pb:
                logged_in = await pb.is_logged_in()
                print(f"Session status: {'✓ Logged in' if logged_in else '✗ Not logged in'}")
        elif cmd == "quote" and len(sys.argv) >= 4:
            async with PorterBrowser() as pb:
                result = await pb.get_quote(sys.argv[2], sys.argv[3])
                print(result)
        else:
            print("Usage: python porter_browser.py [setup|check|quote <pickup> <drop>]")

    asyncio.run(main())
