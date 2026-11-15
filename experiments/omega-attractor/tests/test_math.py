from playwright.sync_api import sync_playwright
from pathlib import Path
import math

app = Path(__file__).resolve().parents[1] / "index.html"

with sync_playwright() as pw:
    chromium = Path("/usr/bin/chromium")
    kwargs = {"headless": True}
    if chromium.exists():
        kwargs["executable_path"] = str(chromium)
        kwargs["args"] = ["--no-sandbox"]
    browser = pw.chromium.launch(**kwargs)
    page = browser.new_page(viewport={"width": 1024, "height": 768})
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    page.set_content(app.read_text(encoding="utf-8"))
    page.locator("#pause").click()
    for key, value in {"w01":1, "w12":1, "w02":0, "tau":1, "g":1, "threshold":0.5}.items():
        page.locator("#p_" + key).fill(str(value))

    heat = float(page.locator("#heatRead").inner_text())
    w2 = float(page.locator("#wasserRead").inner_text())
    kl = float(page.locator("#klRead").inner_text())
    betti = page.locator("#bettiRead").inner_text()

    expected_heat = 1 + math.exp(-1) + math.exp(-3)
    expected_w2 = (1-1/math.sqrt(2))**2 + (1-0.5)**2
    expected_kl = 0.5 * ((0.5-1-math.log(0.5)) + (0.25-1-math.log(0.25)))

    assert abs(heat-expected_heat) < 1e-4, (heat,expected_heat)
    assert abs(w2-expected_w2) < 1e-4, (w2,expected_w2)
    assert abs(kl-expected_kl) < 1e-4, (kl,expected_kl)
    assert betti == "1 / 0", betti

    page.locator("#p_threshold").fill("1.5")
    assert page.locator("#bettiRead").inner_text() == "3 / 0"
    assert page.locator("input[type=range]").count() == 31

    previous_heat = page.locator("#heatRead").inner_text()
    page.locator("#p_tau").fill("2.1")
    page.wait_for_timeout(100)
    assert page.locator("#heatRead").inner_text() != previous_heat
    page.locator("#observable").select_option("fiedler")
    page.locator("#colorMode").select_option("omega")
    assert page_errors == [], page_errors

    print("PASS: 31 sliders, spectral identities, topology and controls")
    browser.close()
