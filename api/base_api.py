import requests

class BaseAPI:

    def __init__(self, base_url):
        self.base_url = base_url

    def post(self, url, json=None):
        return requests.post(self.base_url + url, json=json).json()

    def get(self, url):
        return requests.get(self.base_url + url).json()
