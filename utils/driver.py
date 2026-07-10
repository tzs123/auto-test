from playwright.sync_api import sync_playwright

class Driver:

    def __init__(self):
        self.p = sync_playwright().start()
        self.browser = self.p.chromium.launch(headless=False, slow_mo=200)
        self.context = self.browser.new_context(viewport={"width": 390, "height": 844})
        self.page = self.context.new_page()

    def get_page(self):
        return self.page

    def close(self):
        self.context.close()
        self.browser.close()
        self.p.stop()
