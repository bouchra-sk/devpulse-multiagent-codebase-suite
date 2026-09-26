from backend.Agent1.security_quality_agent import SecurityQualityAgent


def test_review_detects_sql_injection_and_hardcoded_secret():
    code = '''
password = "secret"
cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
'''

    report = SecurityQualityAgent().review(code)

    assert report["summary"]["risk_level"] == "high"
    assert {finding["rule_id"] for finding in report["findings"]} == {"SEC001", "SEC002"}


def test_review_reports_bare_except_with_line_number():
    report = SecurityQualityAgent().review("try:\n    work()\nexcept:\n    pass\n")

    finding = next(item for item in report["findings"] if item["rule_id"] == "QUAL003")
    assert finding["line"] == 3


def test_review_rejects_empty_code():
    try:
        SecurityQualityAgent().review("   ")
    except ValueError as error:
        assert str(error) == "Code cannot be empty"
    else:
        raise AssertionError("Expected empty code to be rejected")