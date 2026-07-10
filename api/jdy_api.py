from api.base_api import BaseAPI

class JDYAPI(BaseAPI):

    def evaluate(self, data):
        return self.post("/business/submit/evaluate", data)

    def monthly_supply(self, data):
        return self.post("/business/monthlySupply", data)

    def submit(self, data):
        return self.post("/business/submit/loan", data)
