---
name: "project-generator"
description: "Generates complete executable test projects from user requirements. Invoke when user wants to create a new project with specific test cases, APIs, or UI flows."
---

# Project Generator

This skill creates complete, executable test projects based on user requirements. It automatically generates:

- Project metadata (name, description, base_url)
- Environment configurations (test/staging/prod)
- API test cases (YAML)
- UI test cases (YAML)
- Test scripts (Python)
- Page objects (Python)

## When to Invoke

- User wants to create a new test project
- User provides requirements for testing a specific API or system
- User asks to "generate project", "create project", "setup project"
- User describes a system they want to test

## Workflow

### Step 1: Gather Requirements

Ask user for:
1. **Project name** - Name of the project
2. **Description** - Brief description
3. **Base URL** - API endpoint (if API testing)
4. **Test type** - API only, UI only, or both
5. **Specific test requirements** - What APIs or UI flows to test

### Step 2: Create Project

Call the backend API to create the project:
```
POST /api/projects
{
  "name": "<project_name>",
  "description": "<description>",
  "base_url": "<base_url>"
}
```

### Step 3: Generate Environment Config

Create `config/{pid}/test.yaml` with:
- base_url (from user)
- timeout
- headers
- access_key (if provided)

### Step 4: Generate Test Cases and Scripts

Based on user requirements, generate:

#### API Testing
- Create YAML cases in `cases/{pid}/api/test_*.yaml`
- Create Python scripts in `tests/{pid}/api/test_*.py`
- Include comprehensive assertions (status_code, response body, data validation)

#### UI Testing
- Create YAML cases in `cases/{pid}/ui/test_*.yaml`
- Create Python scripts in `tests/{pid}/ui/test_*.py`
- Create page objects in `pages/{pid}/`

### Step 5: Generate Sample Content

If user doesn't provide specific requirements, generate sample content:

**API Sample:**
- test_health.yaml - Health check API
- test_users.yaml - User CRUD APIs
- test_health.py - Corresponding test script
- test_users.py - Corresponding test script

**UI Sample:**
- test_login.yaml - Login flow
- test_dashboard.yaml - Dashboard page
- test_login.py - Login test script
- test_dashboard.py - Dashboard test script
- login_page.py - Login page object
- dashboard_page.py - Dashboard page object

## Test Script Standards

### API Tests

```python
import pytest
import allure

@allure.feature("Feature Name")
@pytest.mark.api
def test_api_endpoint(client):
    resp = client.get("/api/endpoint")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    # Add more specific assertions
```

### UI Tests

```python
import pytest
import allure

@allure.feature("Feature Name")
@pytest.mark.ui
def test_ui_flow(page):
    page.goto("/path")
    # Interact with elements
    # Assert expected outcomes
```

### Page Objects

```python
from pages.base_page import BasePage

class SomePage(BasePage):
    def action_name(self, param):
        # Page actions
        pass
```

### YAML Cases

**API:**
```yaml
- name: Test Case Name
  path: /api/endpoint
  method: GET
  expect_code: 200
  expect_body:
    success: true
```

**UI:**
```yaml
- name: Test Case Name
  steps:
    - open: /path
    - input:
        selector: "#element"
        value: "text"
    - click: "#button"
```

## Validation

After generation, verify:
1. All files are created
2. Project is visible in the system
3. Test scripts follow naming conventions
4. Page objects inherit from BasePage

## Example Usage

**User:** "Create a project for testing my e-commerce API"

**Agent:**
1. Ask for base_url and specific APIs to test
2. Create project "e-commerce-api"
3. Generate config with provided base_url
4. Generate test cases for:
   - /api/products (GET/POST)
   - /api/orders (GET/POST)
   - /api/cart (GET/POST/DELETE)
5. Generate corresponding Python scripts with comprehensive assertions

**User:** "Create a UI test project for my login page"

**Agent:**
1. Ask for base_url
2. Create project "login-ui-test"
3. Generate config
4. Generate login_page.py with page objects
5. Generate test_login.yaml with login flow
6. Generate test_login.py with pytest script

## Key Notes

- Always use `pytest.mark.api` or `pytest.mark.ui` markers
- Include `allure.feature()` for proper report categorization
- API tests must use `client` fixture from conftest
- UI tests must use `page` fixture from conftest
- Page objects must import and extend BasePage
- YAML files must follow the defined structure
- Assertions should be comprehensive (not just status_code)
