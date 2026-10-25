def build_report(final_findings):
    compliant = sum(1 for f in final_findings if f["verdict"] == "Compliant")
    gap = sum(1 for f in final_findings if f["verdict"] == "Gap")
    total = len(final_findings)
    score = round((compliant / total * 100), 1) if total else 0.0
    return {
        "total": total,
        "compliant": compliant,
        "gap": gap,
        "score_percent": score,
        "findings": final_findings,
    }


def build_report_html(report):
    rows = ""
    for f in report["findings"]:
        rows += (
            f"<tr><td>{f['tool_name']}</td><td>{f['framework']}</td>"
            f"<td>{f['clause']}</td><td>{f['verdict']}</td>"
            f"<td>{f['reason']}</td><td>{f['evidence_required']}</td></tr>"
        )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>AI Governance Audit Report</title></head>
<body>
<h1>AI Governance Audit Report</h1>
<p>Total findings in report: {report['total']} | Compliant: {report['compliant']} | Gap: {report['gap']} | Score: {report['score_percent']}%</p>
<p>Only decided findings appear here. Pending and rejected findings are excluded.</p>
<table border="1" cellpadding="6">
<tr><th>Tool</th><th>Framework</th><th>Clause</th><th>Verdict</th><th>Reason</th><th>Evidence required</th></tr>
{rows}
</table>
</body></html>"""
