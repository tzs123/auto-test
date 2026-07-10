import requests, hashlib, hmac, time, os, json, glob, warnings
warnings.filterwarnings("ignore")

class MeterSphereSync:
    def __init__(self, base_url, access_key, secret_key, project_id):
        self.base_url = base_url.rstrip("/")
        self.access_key = access_key
        self.secret_key = secret_key
        self.project_id = project_id

    def _headers(self):
        ts = str(int(time.time() * 1000))
        # MeterSphere v3 用 HMAC-SHA256
        message = (self.access_key + ts).encode("utf-8")
        sig_hmac = hmac.new(
            self.secret_key.encode("utf-8"), message, hashlib.sha256
        ).hexdigest()
        # 同时保留 MD5 备用
        sig_md5 = hashlib.md5(
            f"{self.access_key}{ts}{self.secret_key}".encode()
        ).hexdigest()
        return {
            "Content-Type": "application/json",
            "accessKey": self.access_key,
            "signature": sig_hmac,   # v3 用 HMAC-SHA256
            "timestamp": ts,
        }

    def _get(self, path):
        try:
            r = requests.get(
                f"{self.base_url}{path}",
                headers=self._headers(), timeout=10, verify=False
            )
            return r.status_code, r.json() if r.text else {}
        except Exception as e:
            return 0, {"error": str(e)}

    def _post(self, path, data):
        try:
            r = requests.post(
                f"{self.base_url}{path}",
                json=data, headers=self._headers(), timeout=10, verify=False
            )
            return r.status_code, r.json() if r.text else {}
        except Exception as e:
            return 0, {"error": str(e)}

    def check_connection(self):
        """尝试多个 API 路径验证连通"""
        paths = [
            "/api/user/current",
            "/api/user/get/current",
            "/api/project/list/all",
            "/api/v1/project/list",
        ]
        for path in paths:
            code, resp = self._get(path)
            if code == 200:
                print(f"  ✅ 连接成功: {path} -> HTTP {code}")
                return True
            print(f"  尝试 {path} -> HTTP {code}")
        return False

    def parse_results(self, results_dir):
        passed = failed = broken = total = 0
        cases = []
        for f in glob.glob(f"{results_dir}/*-result.json"):
            try:
                d = json.load(open(f, encoding="utf-8"))
                s = d.get("status", "unknown")
                total += 1
                if s == "passed": passed += 1
                elif s == "failed": failed += 1
                elif s == "broken": broken += 1
                cases.append({"name": d.get("name", ""), "status": s})
            except Exception:
                pass
        return {"total": total, "passed": passed, "failed": failed,
                "broken": broken, "cases": cases}

    def sync(self, results_dir):
        print(f"\n{'='*20} MeterSphere 同步 {'='*20}")
        stats = self.parse_results(results_dir)
        total  = stats["total"]
        passed = stats["passed"]
        failed = stats["failed"] + stats["broken"]
        print(f"  总计:{total} 通过:{passed} 失败:{failed}")

        if total == 0:
            print("  ⚠️  无结果文件，跳过")
            return

        ok = self.check_connection()
        if not ok:
            print("\n  ⚠️  API 连接失败，改用手动导入方式：")
            print("  MeterSphere → 测试计划 → 新建计划 → 报告 → 导入")
            print(f"  Allure 报告路径: {results_dir}")
            return

        # 创建测试报告
        plan_name = f"今东车融回归_{time.strftime('%Y%m%d_%H%M%S')}"
        for path in ["/api/test-plan/report/create",
                     "/api/testPlan/report/create",
                     "/api/report/create"]:
            code, resp = self._post(path, {
                "projectId": self.project_id,
                "name": plan_name,
                "status": "Success" if failed == 0 else "Error",
                "description": f"通过:{passed} 失败:{failed} 合计:{total}",
            })
            if code in (200, 201):
                print(f"  ✅ 报告已上报: {path}")
                return
        print("  ⚠️  上报接口未匹配，请手动导入 Allure 报告到 MeterSphere")


def sync_to_ms():
    ms_url = os.getenv("MS_URL", "")
    ms_ak  = os.getenv("MS_ACCESS_KEY", "")
    ms_sk  = os.getenv("MS_SECRET_KEY", "")
    ms_pid = os.getenv("MS_PROJECT_ID", "")
    if not all([ms_url, ms_ak, ms_sk, ms_pid]):
        print("[MeterSphere] 环境变量未配置")
        return
    MeterSphereSync(ms_url, ms_ak, ms_sk, ms_pid).sync(
        "/Users/tanzsongsen/auto_test/reports/allure-results"
    )

if __name__ == "__main__":
    sync_to_ms()
