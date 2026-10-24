"""Offline smoke for the browser runtime shipped with the desktop app."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mediaharvester.dynamic import browser_options
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,**browser_options())
    try:
        page=browser.new_page()
        page.set_content('<body><script>document.body.dataset.ready="yes"</script></body>')
        assert page.locator('body').get_attribute('data-ready')=='yes'
    finally:
        browser.close()
print('Deep parsing Chromium runtime: startup, JavaScript and shutdown passed')
