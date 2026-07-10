def test_pytest_ok():
    assert 1 + 1 == 2

def test_yaml_ok():
    import yaml
    data = yaml.safe_load("key: value")
    assert data["key"] == "value"
