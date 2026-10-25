from app.rules import audit_summary, evaluate_requirement, run_audit


def make_requirement(control_type):
    return {
        "id": "TEST-01",
        "framework": "Test Framework",
        "clause": "Cl. 1",
        "obligation": "Test system shall do X.",
        "risk_tier": "high",
        "control_type": control_type,
        "evidence_required": "procedure",
    }


def make_tool(value):
    return {
        "id": "TOOL-TEST",
        "name": "Test Tool",
        "vendor": "Test Vendor",
        "category": "hiring",
        "controls": {"human_oversight": value},
    }


def test_true_is_compliant():
    finding = evaluate_requirement(make_requirement("human_oversight"), make_tool(True))
    assert finding.verdict == "Compliant"
    assert finding.confidence == 0.95
    assert finding.needs_review is False


def test_false_is_gap():
    finding = evaluate_requirement(make_requirement("human_oversight"), make_tool(False))
    assert finding.verdict == "Gap"
    assert finding.confidence == 0.90
    assert finding.needs_review is False


def test_none_is_gap_pending():
    finding = evaluate_requirement(make_requirement("human_oversight"), make_tool(None))
    assert finding.verdict == "Gap"
    assert finding.confidence == 0.40
    assert finding.needs_review is True


def test_run_audit_counts():
    requirement = make_requirement("human_oversight")
    findings = run_audit([requirement], [make_tool(True), make_tool(False)])
    assert len(findings) == 2
    summary = audit_summary(findings)
    assert summary["compliant"] == 1
    assert summary["gap"] == 1
    assert summary["pending_review"] == 0
    assert summary["report_total"] == 2
    assert summary["report_score_percent"] == 50.0
