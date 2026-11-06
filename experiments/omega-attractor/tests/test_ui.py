from pathlib import Path
from playwright.sync_api import sync_playwright
import hashlib

source = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    for width, height in [(430, 844), (1000, 750), (1440, 900)]:
        page = browser.new_page(viewport={"width": width, "height": height}, has_touch=width<500, is_mobile=width<500)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.set_content(source)
        page.wait_for_timeout(500)
        assert page.locator("input[type=range]").count() == 31
        assert page.evaluate("document.body.scrollWidth <= innerWidth")
        assert page.locator(".stage").bounding_box()["height"] >= height - 1
        assert not page.locator("#panel").is_visible()
        assert page.locator("p, article, h1, h2, h3").count() == 0, "No reading-mode bait or text wall"
        first = hashlib.md5(page.locator("canvas").screenshot()).hexdigest()
        page.wait_for_timeout(240)
        assert hashlib.md5(page.locator("canvas").screenshot()).hexdigest() != first, "Orbit should animate without tapping"
        page.locator("#controlsButton").click()
        assert page.locator("#panel").is_visible()
        assert page.locator("#p_rho").is_visible()
        page.locator("#pause").click()
        before = float(page.locator("#timeRead").inner_text())
        page.locator("#p_rho").fill("40")
        page.wait_for_timeout(350)
        assert page.locator("#pause").inner_text() == "Pause"
        assert float(page.locator("#timeRead").inner_text()) > before
        page.locator("#p_kx").fill("4")
        assert page.locator("#p_kx").input_value() == "4"
        page.locator("#p_statwindow").fill("1000")
        assert page.locator("#colorMode").input_value() == "omega"
        page.locator("#closeControls").click()
        assert not page.locator("#panel").is_visible()
        assert not errors, errors
        print(f"PASS {width}x{height}: visual-only, fullscreen plot, 31 sliders, live morph, no JS errors")
        page.close()
    browser.close()
