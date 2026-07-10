---
name: "auto-test-generator"
description: "Generates Playwright UI page objects, pytest test cases, and YAML data files from DOM/prototype images. Invoke when user provides page DOM, screenshots, or asks to create UI/API automated tests."
---

# Auto Test Generator

根据用户提供的页面 DOM 结构、原型图或截图，自动生成 Playwright UI 自动化测试代码（Page Object + Test Case + YAML 数据文件），以及接口自动化测试代码（YAML 用例 + pytest 测试文件），保存到当前项目对应的目录下，可直接执行测试。

## 项目结构

当前项目 `/Users/tanzsongsen/auto_test` 的关键目录：

```
pages/          → Page Object 类（继承 BasePage）
cases/api/      → 接口测试 YAML 数据文件
cases/ui/       → UI 测试 YAML 数据文件
tests/api/      → 接口测试 pytest 文件
tests/ui/       → UI 测试 pytest 文件
conftest.py     → pytest fixture（page, client, config）
config/test.yaml → 测试环境配置
```

## 生成规则

### 1. UI Page Object 生成规则

- **继承 BasePage**：`from pages.base_page import BasePage`
- **类名规范**：`XxxPage(BasePage)`，如 `JdyHomePage`、`JdyResultPage`
- **构造函数**：`def __init__(self, page: Page): super().__init__(page); self.base_url = "..."`
- **每个操作方法**：
  - 必须加 `@allure.step("描述")` 装饰器
  - 输入操作：使用 `self.page.locator(css_selector).fill(value)` 或 `.click()`
  - 等待操作：使用 `self.page.wait_for_load_state("networkidle")` + `self.page.wait_for_timeout(n)`
  - 虚拟键盘：使用 `self.wait_for_keyboard_popup()` + `self.click_virtual_key(char)`（BasePage 提供）
  - Picker 选择器：使用 `self.wait_for_picker_popup()` + `self.select_picker_option(text)` + `self.confirm_picker()`（BasePage 提供）
  - 断言方法：返回 `bool` 或 `str`，不加 assert
- **goto 方法**：必须有 `@allure.step("打开xxx页")`，包含 `self.page.goto(url)` + `wait_for_load_state("networkidle")`
- **screenshot 方法**：`return self.page.screenshot()`
- **保存路径**：`pages/<module>_page.py`（如 `pages/jdy_home_page.py`）

### 2. UI 测试用例生成规则

**YAML 数据文件** (`cases/ui/<name>.yaml`)：
```yaml
- name: 场景描述
  channel_id: JDYFWH
  product_id: JDYPRD01
  phone: "17711111111"
  expect_title: 期望标题文本
  expect_apply_btn: true
```

**pytest 测试文件** (`tests/ui/test_<name>.py`)：
```python
import pytest
import allure
from utils.yaml_loader import load_cases
from pages.<module>_page import XxxPage

@allure.feature("功能模块名")
@pytest.mark.ui
@pytest.mark.parametrize("case", load_cases("cases/ui/test_<name>.yaml"))
def test_<name>(case, page):
    xxx = XxxPage(page)
    with allure.step(f"场景: {case['name']}"):
        xxx.goto(...)
        allure.attach(xxx.screenshot(), name="截图", attachment_type=allure.attachment_type.PNG)
        # 验证逻辑
        if "expect_xxx" in case:
            assert ...
```

### 3. API 接口测试生成规则

**YAML 数据文件** (`cases/api/test_<name>.yaml`)：
```yaml
- name: 接口描述
  path: /api/v1/xxx
  method: GET
  params:
    key: value
  expect_code: 200

- name: POST接口描述
  path: /api/v1/xxx
  method: POST
  body:
    key: value
  expect_code: 200
```

**pytest 测试文件** (`tests/api/test_<name>.py`)：
```python
import pytest
import allure
import requests
from utils.yaml_loader import load_cases, load_config
from utils.signer import make_headers

config = load_config()
BASE_URL = config["base_url"]
ACCESS_KEY = config["access_key"]

@allure.feature("模块名-接口")
@pytest.mark.api
@pytest.mark.parametrize("case", load_cases("cases/api/test_<name>.yaml"))
def test_<name>(case):
    with allure.step(case["name"]):
        headers = make_headers(ACCESS_KEY)
        url = BASE_URL + case["path"]
        if case["method"] == "GET":
            resp = requests.get(url, params=case.get("params"), headers=headers, verify=False, timeout=30)
        else:
            resp = requests.post(url, json=case.get("body"), headers=headers, verify=False, timeout=30)
        allure.attach(str(resp.status_code), name="状态码")
        allure.attach(resp.text[:500], name="响应体")
        assert resp.status_code == case["expect_code"]
```

### 4. DOM 解析规则

当用户提供 DOM 结构时：
- 提取所有可交互元素：`input`、`button`、`select`、`a`、`[class*="van-"]`
- 根据元素属性生成 locator：
  - `name` 属性 → `input[name="xxx"]`
  - `class` 含语义 → `.class-name`
  - `placeholder` → 辅助定位
  - 按钮文本 → `button:has-text("xxx")`
- 识别 Vant 组件：
  - `van-field` → 输入框
  - `van-picker` → 选择器（用 BasePage picker 方法）
  - `van-checkbox` → 复选框
  - `van-button` → 按钮
  - `van-popup` → 弹层容器
  - 虚拟键盘 → 用 BasePage keyboard 方法

### 5. 原型图/截图解析规则

当用户提供原型图或截图时：
- 识别页面中的表单字段、按钮、列表等 UI 元素
- 为每个字段生成合理的定位器（优先 CSS selector）
- 生成完整的用户操作流程
- 推断数据类型和验证点

## 执行流程

1. **分析输入**：读取用户提供的 DOM / 原型图 / 截图
2. **确认模块**：询问用户属于哪个功能模块（如"今东车融-首页"）
3. **生成 Page Object**：写入 `pages/<module>_page.py`
4. **生成 YAML 数据**：写入 `cases/ui/test_<module>.yaml` 或 `cases/api/test_<module>.yaml`
5. **生成测试文件**：写入 `tests/ui/test_<module>.py` 或 `tests/api/test_<module>.py`
6. **验证语法**：确保所有生成的文件通过 `python3 -m py_compile`
7. **提示执行**：告知用户可通过前端平台或命令行执行测试

## 注意事项

- 不要覆盖已有文件，除非用户明确要求
- 如果 Page 类已存在，只追加新方法
- YAML 用例追加到已有文件末尾
- 生成的代码必须符合项目现有风格和规范
- 确保 import 路径正确（`from pages.xxx import XxxPage`、`from utils.yaml_loader import load_cases`）
- 测试标记必须包含 `@pytest.mark.ui`（UI测试）或 `@pytest.mark.api`（接口测试）
