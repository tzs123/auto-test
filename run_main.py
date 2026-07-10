import subprocess

def run():

    print("===== 1. pytest执行 =====")

    subprocess.run([
        "pytest",
        "tests/",
        "--alluredir=reports/allure-results"
    ], check=True)

    print("===== 2. 生成Allure报告 =====")

    subprocess.run([
        "allure",
        "generate",
        "reports/allure-results",
        "-o",
        "reports/html",
        "--clean"
    ], check=True)

    print("===== 完成 =====")
    print("报告路径: reports/html/index.html")

if __name__ == "__main__":
    run()
