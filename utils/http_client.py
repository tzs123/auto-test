import requests
import allure

class HttpClient:
    def __init__(self, base_url, timeout=30, headers=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    def set_token(self, token):
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def request(self, method, path, **kwargs):
        url = self.base_url + path
        with allure.step(f"{method.upper()} {url}"):
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            allure.attach(str(resp.status_code), name="状态码")
            allure.attach(resp.text[:500], name="响应体")
        return resp

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)
