from pydantic import BaseModel

REVIEW_THRESHOLD = 0.65


class Finding(BaseModel):
    tool_id: str
    tool_name: str
    requirement_id: str
    framework: str
    clause: str
    obligation: str
    verdict: str
    confidence: float
    needs_review: bool
    reason: str
    evidence_required: str


def evaluate_requirement(requirement, tool):
    control_type = requirement["control_type"]
    value = tool["controls"].get(control_type)

    if value is True:
        verdict = "Compliant"
        confidence = 0.95
        reason = f"In place: {control_type} is present for this tool."
    elif value is False:
        verdict = "Gap"
        confidence = 0.90
        reason = f"Missing: {control_type} is not present for this tool."
    else:
        verdict = "Gap"
        confidence = 0.40
        reason = (
            f"Unknown: {control_type} has not been disclosed by the vendor, "
            "so compliance cannot be confirmed. This is not a pass."
        )

    return Finding(
        tool_id=tool["id"],
        tool_name=tool["name"],
        requirement_id=requirement["id"],
        framework=requirement["framework"],
        clause=requirement["clause"],
        obligation=requirement["obligation"],
        verdict=verdict,
        confidence=confidence,
        needs_review=confidence < REVIEW_THRESHOLD,
        reason=reason,
        evidence_required=requirement["evidence_required"],
    )


def run_audit(frameworks, tools):
    findings = []
    for tool in tools:
        for requirement in frameworks:
            findings.append(evaluate_requirement(requirement, tool))
    return findings


def audit_summary(findings):
    compliant = sum(1 for f in findings if f.verdict == "Compliant")
    gap = sum(1 for f in findings if f.verdict == "Gap")
    pending = sum(1 for f in findings if f.needs_review)
    report_total = len(findings) - pending
    report_score = round((compliant / report_total * 100), 1) if report_total else 0.0
    return {
        "total": len(findings),
        "compliant": compliant,
        "gap": gap,
        "pending_review": pending,
        "report_total": report_total,
        "report_score_percent": report_score,
    }
