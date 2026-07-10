from core.step_executor import StepExecutor

class LoanFlow:

    def __init__(self, page):
        self.exec = StepExecutor(page)

    def run_apply_flow(self, case):

        for step in case["steps"]:
            self.exec.execute(step)
