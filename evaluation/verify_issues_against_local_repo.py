import json
import re
from pathlib import Path
from collections import Counter, defaultdict

AUDIT_REPORT = Path("universal_audit_report.json")
REPO = Path(r"D:\GSOC\musicblocks")
INDEX = REPO / "index.html"


def load_issues():
    data = json.loads(AUDIT_REPORT.read_text(encoding="utf-8", errors="ignore"))
    all_issues = []
    for _, payload in data.items():
        all_issues.extend(payload.get("issues", []))
    return all_issues


def normalize_selector(element: str):
    element = (element or "").strip()
    if not element:
        return None, None

    if element.startswith("<") and element.endswith(">"):
        tag = element[1:-1].strip().lower().split()[0]
        return "tag", tag

    if "#" in element and not element.startswith("#"):
        tag, ident = element.split("#", 1)
        return "tag_id", (tag.strip().lower(), ident.strip())

    if element.startswith("#"):
        return "id", element[1:].strip()

    if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", element):
        return "tag", element.lower()

    return "raw", element


def selector_exists_in_html(html: str, element: str) -> bool:
    kind, parsed = normalize_selector(element)
    if not kind:
        return False

    if kind == "tag":
        tag = re.escape(parsed)
        return re.search(rf"<{tag}(\s|>)", html, flags=re.IGNORECASE) is not None

    if kind == "id":
        ident = re.escape(parsed)
        return re.search(rf"id\s*=\s*['\"]{ident}['\"]", html, flags=re.IGNORECASE) is not None

    if kind == "tag_id":
        tag, ident = parsed
        t = re.escape(tag)
        i = re.escape(ident)
        return re.search(rf"<{t}[^>]*\bid\s*=\s*['\"]{i}['\"][^>]*>", html, flags=re.IGNORECASE) is not None

    if kind == "raw":
        needle = parsed.lower()
        return needle in html.lower()

    return False


def appears_in_repo_text(repo_files: list[Path], element: str) -> bool:
    kind, parsed = normalize_selector(element)
    if not kind:
        return False

    needles = []
    if kind == "tag":
        needles = [f"<{parsed}"]
    elif kind == "id":
        needles = [f'id="{parsed}"', f"id='{parsed}'", parsed]
    elif kind == "tag_id":
        tag, ident = parsed
        needles = [f"<{tag}", ident]
    else:
        needles = [str(parsed)]

    lowered_needles = [n.lower() for n in needles]

    for p in repo_files:
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if all(n in txt for n in lowered_needles):
            return True
        # fallback: any needle present means likely runtime template
        if any(n in txt for n in lowered_needles):
            return True
    return False


def main():
    if not AUDIT_REPORT.exists():
        raise FileNotFoundError(f"Missing {AUDIT_REPORT}")
    if not REPO.exists():
        raise FileNotFoundError(f"Missing repo {REPO}")

    issues = load_issues()
    html = INDEX.read_text(encoding="utf-8", errors="ignore") if INDEX.exists() else ""

    repo_files = list(REPO.rglob("*.html")) + list(REPO.rglob("*.js")) + list(REPO.rglob("*.ts"))

    status_counter = Counter()
    rule_status = defaultdict(Counter)
    details = []

    for issue in issues:
        rule = issue.get("rule_id", "unknown")
        element = issue.get("element", "")
        source = "+".join(issue.get("confidence_sources", [])) or "unknown"

        in_html = selector_exists_in_html(html, element)
        in_repo = appears_in_repo_text(repo_files, element)

        if in_html:
            status = "confirmed_in_index_html"
        elif in_repo:
            status = "found_in_repo_code"
        else:
            # For dynamic/browser findings, treat as potentially runtime.
            if "browser-probe" in source or "axe-core" in source:
                status = "not_found_static_maybe_runtime"
            else:
                status = "not_found_in_repo"

        status_counter[status] += 1
        rule_status[rule][status] += 1

        details.append({
            "rule_id": rule,
            "element": element,
            "status": status,
            "severity": issue.get("severity", "unknown"),
            "source": source,
        })

    out = {
        "repo": str(REPO),
        "audit_report": str(AUDIT_REPORT),
        "total_issues": len(issues),
        "status_summary": dict(status_counter),
        "by_rule": {k: dict(v) for k, v in sorted(rule_status.items())},
        "details": details,
    }

    Path("evaluation/repo_validation_results.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )

    print("=== Repo Validation Summary ===")
    print(f"Total issues: {len(issues)}")
    for k, v in status_counter.items():
        print(f"{k}: {v}")

    print("\nTop rules with not found counts:")
    for rule, counts in sorted(rule_status.items(), key=lambda x: x[1].get("not_found_in_repo", 0), reverse=True)[:10]:
        nf = counts.get("not_found_in_repo", 0)
        nfr = counts.get("not_found_static_maybe_runtime", 0)
        if nf or nfr:
            print(f"{rule}: not_found_in_repo={nf}, maybe_runtime={nfr}")

    print("\nSaved: evaluation/repo_validation_results.json")


if __name__ == "__main__":
    main()
