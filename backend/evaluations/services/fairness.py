"""
Fairness testing.

1) Counterfactual test. Take the same resume and change ONLY identity signals: the
   name (different cultural backgrounds / perceived genders), the university
   (well-known vs. lesser-known) and the pronouns. After redaction, every variant
   must (a) contain none of those signals and (b) get exactly the same score.
   The test is deterministic: it uses the local keyword matcher, never the AI.

2) Probes. Harder cases we expect redaction may miss (a name only in a sign-off,
   a club name...). They never fail the run, they are reported as limitations.

3) Adverse impact (four-fifths rule). You supply real selection counts per group;
   we compute each group's selection rate vs. the highest group.

This tests our pipeline. It is NOT an independent bias audit.
"""
import re

from .evaluator import evaluate_candidate
from .privacy import redact_resume

# Name sets differ in perceived gender and cultural background (sample names only).
NAME_SETS = {
    "set_a": ["James Walker", "Emily Carter"],
    "set_b": ["Wei Zhang", "Mei Lin"],
    "set_c": ["Mohammed Hassan", "Fatima Khan"],
    "set_d": ["Oluwaseun Adeyemi", "Chiamaka Okafor"],
    "set_e": ["Rahul Sharma", "Priya Nair"],
    "set_f": ["Carlos Mendoza", "Sofia Ramirez"],
}
UNIVERSITIES = ["Harvard University", "Stanford University", "Northfield State College", "Ridgeway Community College"]
PRONOUN_LINES = ["He led the migration.", "She led the migration.", "They led the migration."]

BASE_BODY = (
    "Built a Python REST API with Django for an internal tool. "
    "Designed LangGraph agents with retrieval for support tickets. "
    "Used PostgreSQL and Docker to deploy the service."
)
DEFAULT_CRITERIA = [
    {"name": "Python backend", "weight": 40, "keywords": ["Python", "Django", "REST API"]},
    {"name": "AI agents", "weight": 35, "keywords": ["LangGraph", "agents", "retrieval"]},
    {"name": "System design", "weight": 25, "keywords": ["PostgreSQL", "Docker"]},
]


def _resume(name, university, pronoun_line):
    slug = name.lower().replace(" ", ".")
    return (
        f"Name: {name}\nEmail: {slug}@example.test\nPhone: +1 555 010 0199\n"
        f"{university}\n\n{BASE_BODY} {pronoun_line}"
    )


def _leaks(redacted, name, university):
    """Which identity signals are still visible after redaction?"""
    found = []
    lowered = redacted.lower()
    for part in name.split():
        if re.search(rf"\b{re.escape(part.lower())}\b", lowered):
            found.append("name")
            break
    if university.lower() in lowered:
        found.append("university")
    if "@example.test" in lowered:
        found.append("email")
    if "555 010" in lowered:
        found.append("phone")
    for pronoun in (" he ", " she ", " they "):
        if pronoun in f" {lowered} ":
            found.append("pronoun")
            break
    return found


def run_counterfactual_suite(criteria=None):
    criteria = criteria or DEFAULT_CRITERIA
    variants = []
    baseline = None

    for set_name, names in NAME_SETS.items():
        for name in names:
            for university in UNIVERSITIES:
                for pronoun_line in PRONOUN_LINES:
                    redacted, _ = redact_resume(_resume(name, university, pronoun_line))
                    score = evaluate_candidate(redacted, criteria, use_ai=False)["final_score"]
                    if baseline is None:
                        baseline = score
                    variants.append({
                        "name_set": set_name,
                        "university": university,
                        "pronouns": pronoun_line.split()[0],
                        "score": score,
                        "leaks": _leaks(redacted, name, university),
                    })

    leaking = [v for v in variants if v["leaks"]]
    scores = {v["score"] for v in variants}
    max_delta = max(scores) - min(scores)
    by_set = {}
    for v in variants:
        by_set.setdefault(v["name_set"], []).append(v["score"])

    probes = run_probes(criteria)
    passed = not leaking and max_delta == 0
    summary = {
        "variants_tested": len(variants),
        "variants_leaking": len(leaking),
        "max_score_difference": max_delta,
        "mean_score_by_name_set": {k: round(sum(v) / len(v), 2) for k, v in by_set.items()},
        "probe_leaks": sum(1 for p in probes if p["leaked"]),
        "probes_run": len(probes),
    }
    return passed, summary, {"leaking_examples": leaking[:10], "probes": probes}


def run_probes(criteria):
    cases = [
        ("Name only in the sign-off", "Built a Python API.\nKind regards,\nPriya Nair", "Priya"),
        ("Name in a sentence", "Priya Nair built a Python API.", "Priya"),
        ("Club or society name", "Captain of the Harvard Women's Chess Club. Built a Python API.", "Women"),
        ("Graduation year", "Graduated 1998. Built a Python API.", "1998"),
        ("Home address", "Lives at 14 Elm Street. Built a Python API.", "Elm Street"),
        ("Honorific", "Mrs. Nair built a Python API.", "Mrs"),
    ]
    results = []
    for label, text, marker in cases:
        redacted, _ = redact_resume(text)
        results.append({"case": label, "leaked": marker in redacted})
    return results


def four_fifths(groups):
    """groups: [{"name", "applicants", "selected"}] -> impact ratios vs. the top group."""
    rows = []
    for group in groups:
        applicants = int(group["applicants"])
        selected = int(group["selected"])
        if applicants <= 0 or selected < 0 or selected > applicants:
            raise ValueError(f"Check the numbers for '{group.get('name', '?')}'.")
        rows.append({"name": str(group["name"]), "applicants": applicants, "selected": selected,
                     "rate": selected / applicants})
    if len(rows) < 2:
        raise ValueError("Provide at least two groups.")
    top = max(row["rate"] for row in rows)
    for row in rows:
        row["impact_ratio"] = round(row["rate"] / top, 3) if top else 0
        row["rate"] = round(row["rate"], 4)
        row["flag"] = row["impact_ratio"] < 0.8
        row["small_sample"] = row["applicants"] < 30
    return {"groups": rows, "any_flag": any(r["flag"] for r in rows)}
