from pathlib import Path
from playwright.sync_api import sync_playwright

source = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for width, height in [(430, 844), (1000, 750), (1440, 900)]:
        page = browser.new_page(viewport={"width": width, "height": height}, has_touch=width<500, is_mobile=width<500)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(source)
        page.wait_for_timeout(300)
        assert page.locator("input[type=range]").count() == 31
        assert page.evaluate("document.body.scrollWidth <= innerWidth")
        page.locator("#pause").click()
        before = float(page.locator("#timeRead").inner_text())
        page.locator("#p_rho").fill("40")
        page.wait_for_timeout(350)
        assert page.locator("#pause").inner_text() == "Pause"
        assert float(page.locator("#timeRead").inner_text()) > before
        page.locator("#focusButton").click()
        assert page.locator("body").evaluate("b=>b.classList.contains('focus-view')")
        assert page.locator(".stage").bounding_box()["height"] >= height-1
        assert not page.locator(".controlpane").is_visible()
        page.locator("#controlsButton").click()
        assert page.locator("#p_rho").is_visible()
        page.locator("#p_kx").fill("4")
        assert page.locator("#p_kx").input_value() == "4"
        page.locator("#closeControls").click()
        assert not page.locator(".controlpane").is_visible()
        page.locator("#focusButton").click()
        assert not page.locator("body").evaluate("b=>b.classList.contains('focus-view')")
        assert not errors, errors
        print(f"PASS {width}x{height}: fullscreen, sliders, live morph, no JS errors")
        page.close()
    browser.close()
