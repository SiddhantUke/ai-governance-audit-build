import re


def _normalise(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def noul(quote, document_text):
    if not quote or not document_text:
        return 0.0
    return 1.0 if _normalise(quote) in _normalise(document_text) else 0.0


def choice(finding):
    verdict = finding["verdict"]
    is_unknown = "Unknown" in finding["reason"]
    if verdict == "Compliant":
        dist = {"Compliant": 0.80, "Partial": 0.10, "Gap": 0.10}
    elif is_unknown:
        dist = {"Compliant": 0.10, "Partial": 0.30, "Gap": 0.60}
    else:
        dist = {"Compliant": 0.05, "Partial": 0.10, "Gap": 0.85}
    return dist


def score(finding):
    if finding["verdict"] == "Compliant":
        return 5
    if "Unknown" in finding["reason"]:
        return 2
    return 4


def judge_finding(finding):
    is_unknown = "Unknown" in finding["reason"]
    noul_value = 0.0 if is_unknown else 1.0
    dist = choice(finding)
    choice_agreement = dist[finding["verdict"]]
    score_value = score(finding)
    judge_confidence = round(
        0.5 * noul_value + 0.3 * choice_agreement + 0.2 * (score_value / 5), 4
    )
    return {
        "judge_confidence": judge_confidence,
        "judge_needs_review": judge_confidence < 0.65,
        "noul": noul_value,
        "choice_distribution": dist,
        "score": score_value,
    }
