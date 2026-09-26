from backend.Agent4.security_quality_agent import SecurityQualityAgent


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


def test_review_detects_sql_injection_via_string_concatenation():
    """
    SEC001 doit aussi détecter une requête SQL construite par concaténation
    de chaînes (pas seulement à l'intérieur d'un appel execute()).
    """
    code = 'query = "SELECT * FROM users WHERE id = " + user_id\n'

    report = SecurityQualityAgent().review(code)

    rule_ids = {finding["rule_id"] for finding in report["findings"]}
    assert "SEC001" in rule_ids

    sec001 = next(f for f in report["findings"] if f["rule_id"] == "SEC001")
    assert sec001["line"] == 1


def test_review_detects_all_three_vulnerabilities_in_get_user():
    """
    Cas exact fourni par l'utilisateur : SEC001, SEC002 et SEC003 doivent
    tous les trois être détectés dans la même fonction.
    """
    code = '''
def get_user(user_id):
    password = "admin123"
    query = "SELECT * FROM users WHERE id = " + user_id
    result = eval(user_id)
    return query, password, result
'''

    report = SecurityQualityAgent().review(code)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert "SEC001" in rule_ids
    assert "SEC002" in rule_ids
    assert "SEC003" in rule_ids


def test_review_does_not_regress_on_safe_parameterized_query():
    """
    Garde-fou : une requête paramétrée (sûre) ne doit PAS déclencher SEC001,
    pour éviter les faux positifs après l'élargissement du pattern.
    """
    code = 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))\n'

    report = SecurityQualityAgent().review(code)
    rule_ids = {finding["rule_id"] for finding in report["findings"]}

    assert "SEC001" not in rule_ids