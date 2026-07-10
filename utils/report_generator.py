import os
import time
import json
from datetime import datetime


def generate_html_report(results, output_path):
    """生成轻量级静态HTML报告"""
    passed = results.get("passed", 0)
    failed = results.get("failed", 0)
    error = results.get("error", 0)
    total = passed + failed + error
    duration = results.get("duration", 0)
    timestamp = results.get("timestamp", time.time())

    summary_color = "#4CAF50" if failed == 0 else "#F44336"

    run_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>测试报告 - {run_time}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); overflow: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 24px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .header .meta {{ font-size: 14px; opacity: 0.9; margin-top: 8px; }}
        .summary {{ display: flex; gap: 16px; padding: 24px; border-bottom: 1px solid #eee; }}
        .summary-item {{ flex: 1; text-align: center; padding: 16px; border-radius: 8px; }}
        .summary-item.total {{ background: #f8f9fa; }}
        .summary-item.passed {{ background: #e8f5e9; color: #2e7d32; }}
        .summary-item.failed {{ background: #ffebee; color: #c62828; }}
        .summary-item .count {{ font-size: 36px; font-weight: bold; }}
        .summary-item .label {{ font-size: 14px; margin-top: 4px; }}
        .stats {{ padding: 16px 24px; background: #fff3e0; border-bottom: 1px solid #ffe0b2; }}
        .stats span {{ margin-right: 24px; font-size: 14px; color: #e65100; }}
        .results {{ padding: 24px; }}
        .section-title {{ font-size: 18px; font-weight: 600; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #eee; }}
        .test-item {{ padding: 12px 16px; border-radius: 6px; margin-bottom: 8px; border-left: 4px solid; }}
        .test-item.passed {{ border-left-color: #4CAF50; background: #f1f8e9; }}
        .test-item.failed {{ border-left-color: #F44336; background: #fdecea; }}
        .test-item.error {{ border-left-color: #FF9800; background: #fff3e0; }}
        .test-item .name {{ font-weight: 500; }}
        .test-item .time {{ float: right; font-size: 12px; color: #666; }}
        .test-item .error-detail {{ margin-top: 8px; padding: 8px; background: rgba(0,0,0,0.05); border-radius: 4px; font-size: 13px; color: #d32f2f; white-space: pre-wrap; }}
        .footer {{ padding: 16px 24px; background: #f8f9fa; text-align: center; font-size: 13px; color: #666; }}
        .status-badge {{ display: inline-block; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 500; }}
        .status-pass {{ background: #e8f5e9; color: #2e7d32; }}
        .status-fail {{ background: #ffebee; color: #c62828; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>自动化测试报告</h1>
            <div class="meta">运行时间: {run_time}</div>
        </div>
        <div class="summary">
            <div class="summary-item total">
                <div class="count">{total}</div>
                <div class="label">总用例</div>
            </div>
            <div class="summary-item passed">
                <div class="count">{passed}</div>
                <div class="label">通过</div>
            </div>
            <div class="summary-item failed">
                <div class="count">{failed + error}</div>
                <div class="label">失败</div>
            </div>
        </div>
        <div class="stats">
            <span>⏱️ 耗时: {duration:.2f}s</span>
            <span>📊 通过率: {((passed / total) * 100) if total > 0 else 0:.1f}%</span>
            <span>状态: <span class="status-badge {'status-pass' if failed == 0 else 'status-fail'}">{('通过' if failed == 0 else '失败')}</span></span>
        </div>
        <div class="results">
            <div class="section-title">测试结果详情</div>
"""

    for test in results.get("tests", []):
        status = test.get("status", "passed")
        status_class = {"passed": "passed", "failed": "failed", "error": "error"}.get(status, "passed")
        html += f"""
            <div class="test-item {status_class}">
                <span class="name">{test.get('name', '')}</span>
                <span class="time">{test.get('duration', 0):.2f}s</span>
                {f"<div class='error-detail'>{test.get('error', '')}</div>" if status != 'passed' else ''}
            </div>
"""

    html += f"""
        </div>
        <div class="footer">
            生成时间: {run_time} | 报告版本: 1.0
        </div>
    </div>
</body>
</html>
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def collect_test_results(terminalreporter):
    """从pytest terminalreporter收集测试结果"""
    results = {
        "passed": 0,
        "failed": 0,
        "error": 0,
        "duration": 0,
        "timestamp": time.time(),
        "tests": [],
    }

    for status in ["passed", "failed", "error"]:
        results[status] = len(terminalreporter.stats.get(status, []))

    for status in ["passed", "failed", "error"]:
        for test in terminalreporter.stats.get(status, []):
            test_info = {
                "name": test.nodeid,
                "status": status,
                "duration": test.duration,
            }
            if status in ["failed", "error"]:
                test_info["error"] = str(test.longrepr)
            results["tests"].append(test_info)

    results["tests"].sort(key=lambda x: x["name"])

    return results


def collect_test_results_from_files(results_dir):
    """从Allure结果目录收集测试结果"""
    import glob
    
    results = {
        "passed": 0,
        "failed": 0,
        "error": 0,
        "duration": 0,
        "timestamp": time.time(),
        "tests": [],
    }

    for result_file in glob.glob(os.path.join(results_dir, "*-result.json")):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            full_name = data.get("fullName", "")
            name_parts = full_name.split("::")
            display_name = name_parts[-1] if name_parts else full_name
            
            status = data.get("status", "").lower()
            duration_ms = data.get("time", 0)
            
            if status == "passed":
                results["passed"] += 1
            elif status == "failed":
                results["failed"] += 1
            else:
                results["error"] += 1
            
            results["duration"] += duration_ms / 1000.0
            
            test_info = {
                "name": display_name,
                "status": status,
                "duration": duration_ms / 1000.0,
            }
            
            if status in ["failed", "broken"]:
                steps = data.get("steps", [])
                error_messages = []
                for step in steps:
                    if step.get("status") == "failed":
                        error_messages.append(step.get("name", ""))
                        attachments = step.get("attachments", [])
                        for att in attachments:
                            if att.get("name") == "stderr" or att.get("name") == "error":
                                error_messages.append(att.get("name", ""))
                
                if not error_messages:
                    status_details = data.get("statusDetails", {})
                    if status_details.get("message"):
                        error_messages.append(status_details["message"])
                    if status_details.get("trace"):
                        trace = status_details["trace"]
                        error_messages.append(trace[:200] if len(trace) > 200 else trace)
                
                test_info["error"] = "\n".join(error_messages)
            
            results["tests"].append(test_info)
        except Exception:
            pass
    
    results["tests"].sort(key=lambda x: x["name"])
    
    return results
