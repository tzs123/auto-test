import requests
import json
import hashlib
import time
import os

class MeterSphereReporter:
    def __init__(self, base_url, access_key, secret_key):
        self.base_url = base_url.rstrip("/")
        self.access_key = access_key
        self.secret_key = secret_key

    def _get_headers(self):
        """生成签名 headers"""
        timestamp = str(int(time.time() * 1000))
        signature = hashlib.md5(
            f"{self.access_key}{timestamp}{self.secret_key}".encode()
        ).hexdigest()
        return {
            "Content-Type": "application/json",
            "accessKey": self.access_key,
            "signature": signature,
            "timestamp": timestamp,
        }

    def get_projects(self):
        """获取项目列表"""
        resp = requests.get(
            f"{self.base_url}/api/project/list/all",
            headers=self._get_headers(),
            timeout=10
        )
        return resp.json()

    def upload_report(self, project_id: str, report_name: str,
                      passed: int, failed: int, total: int):
        """上报测试结果"""
        payload = {
            "projectId": project_id,
            "name": report_name,
            "description": f"pytest 自动化回归 | 通过:{passed} 失败:{failed} 总计:{total}",
            "status": "Success" if failed == 0 else "Error",
        }
        resp = requests.post(
            f"{self.base_url}/api/test/report/create",
            headers=self._get_headers(),
            json=payload,
            timeout=10
        )
        return resp.json()
