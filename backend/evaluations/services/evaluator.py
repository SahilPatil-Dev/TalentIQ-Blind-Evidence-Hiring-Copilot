"""
The evaluation flow (built with LangGraph).

Think of it as a small assembly line. A "state" dictionary travels through it
and each step (called a node) reads it and adds something:

        START
          |
       [extract]  find a quote in the resume for every rubric criterion
          |       (Mistral Codestral if an API key exists, otherwise keywords)
       [validate] check that every quote really appears in the resume text
          |
          +-- all quotes valid ------------------------+
          |                                            |
          +-- some invalid and we haven't retried -> [retry] -> back to [extract]
          |                                            |
          +-- some invalid but already retried --------+
                                                       |
                                                    [score]  Python (not the AI!)
                                                       |     calculates the score
                                                      END    and makes questions

Why it is built this way: AI models sometimes invent facts. So the AI may only
SUGGEST quotes. Python then checks each quote against the real resume, throws
away anything unsupported, and calculates the score with plain maths.
"""
import re
from typing import TypedDict

from django.conf import settings
from langgraph.graph import END, START, StateGraph

from .mistral import extract_evidence as extract_mistral_evidence


class EvaluationState(TypedDict, total=False):
    """Everything the steps pass to each other."""

    resume_text: str           # redacted resume
    criteria: list[dict]       # the role's rubric
    use_ai: bool               # False = force the local keyword matcher
    evidence: list[dict]       # one {criterion, weight, status, quote} per criterion
    valid_citations: bool      # did every quote pass the check?
    citation_errors: list[str] # criteria whose quote failed the check
    attempts: int              # how many times we've run [extract]
    score: int
    questions: list[str]
    trace: list[str]           # human-readable log of what happened


# --------------------------------------------------------------------------
# Local keyword matcher (used when there is no Mistral key)
# --------------------------------------------------------------------------
def _sentences(text):
    """Split a resume into sentences / lines."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _normalize(value):
    """Lowercase and strip punctuation so 'Python.' matches 'python'."""
    cleaned = re.sub(r"[^a-z0-9+#.]+", " ", value.lower())
    return " ".join(word.strip(".") for word in cleaned.split()).strip()


def _contains_phrase(sentence, keyword):
    """True if `keyword` appears as whole words ("RAG" must not match "storage")."""
    return f" {keyword} " in f" {_normalize(sentence)} "


def extract_evidence(resume_text, criteria):
    """Find, for each criterion, the first sentence that mentions its keywords."""
    # A line like "Skills: Python, Django" is just a keyword dump, not proof.
    sentences = [
        sentence
        for sentence in _sentences(resume_text)
        if not re.match(r"^\s*(?:keywords?|skills?)\s*:", sentence, re.I)
    ]

    evidence = []
    for criterion in criteria:
        raw_keywords = criterion.get("keywords") or [criterion["name"]]
        keywords = [k for k in (_normalize(word) for word in raw_keywords) if k]

        # 1) "verified": a sentence that contains one of the keywords.
        verified = next(
            (s for s in sentences if any(_contains_phrase(s, k) for k in keywords)),
            None,
        )

        # 2) "partial": no full match, but a sentence shares half of a keyword's
        #    words (e.g. keyword "REST API" and the sentence mentions "API").
        partial = None
        if verified is None:
            for sentence in sentences:
                sentence_words = set(_normalize(sentence).split())
                if any(
                    len(sentence_words & set(k.split())) / len(k.split()) >= 0.5
                    for k in keywords
                ):
                    partial = sentence
                    break

        evidence.append(
            {
                "criterion": criterion["name"],
                "weight": criterion["weight"],
                "status": "verified" if verified else ("partial" if partial else "missing"),
                "quote": verified or partial or "",
            }
        )
    return evidence


def calculate_score(evidence):
    """Weighted score: verified = full weight, partial = half, missing = 0."""
    earned = {"verified": 1, "partial": 0.5}
    points = sum(item["weight"] * earned.get(item["status"], 0) for item in evidence)
    return max(0, min(100, round(points)))


# --------------------------------------------------------------------------
# The LangGraph steps (nodes)
# --------------------------------------------------------------------------
def _extract_node(state):
    """Step 1: collect evidence, using Mistral when possible."""
    use_ai = state.get("use_ai", True) and bool(settings.MISTRAL_API_KEY)

    if use_ai:
        evidence = extract_mistral_evidence(
            state["resume_text"],
            state["criteria"],
            state.get("citation_errors"),  # on a retry, tell the AI what it got wrong
        )
        step = f"Extracting evidence with {settings.MISTRAL_MODEL}"
    else:
        evidence = extract_evidence(state["resume_text"], state["criteria"])
        step = "Extracting evidence with local keyword matching"

    return {
        "evidence": evidence,
        "attempts": state.get("attempts", 0) + 1,
        "trace": state.get("trace", []) + [step],
    }


def _validate_node(state):
    """Step 2: a quote only counts if it is copied EXACTLY from the resume."""
    text = state["resume_text"]
    errors = []
    for item in state["evidence"]:
        status = item["status"]
        if status not in ("missing", "verified", "partial"):
            errors.append(item["criterion"])  # the AI invented a status
        elif status != "missing" and (not item["quote"] or item["quote"] not in text):
            errors.append(item["criterion"])  # the quote is not in the resume

    return {
        "valid_citations": not errors,
        "citation_errors": errors,
        "trace": state.get("trace", []) + ["Verifying citations"],
    }


def _route_citations(state):
    """Decide where to go next: retry once if quotes were bad, else score."""
    if state["valid_citations"]:
        return "score"
    if state.get("attempts", 0) < 2:
        return "retry"
    return "score"  # already retried: the bad claims get dropped in [score]


def _retry_node(state):
    """Step 2b: just logs the retry, then the graph loops back to [extract]."""
    return {"trace": state.get("trace", []) + ["Retrying unsupported citations"]}


def _score_node(state):
    """Step 3: drop unsupported claims, calculate the score, write questions."""
    bad_criteria = set(state.get("citation_errors", []))

    # Any claim that still failed validation gets zero points.
    evidence = [
        {**item, "status": "missing", "quote": ""}
        if item["criterion"] in bad_criteria
        else item
        for item in state["evidence"]
    ]
    score = calculate_score(evidence)

    # Interview questions: ask about the heaviest criteria that were NOT fully
    # verified. If fewer than 3, fill up with general trade-off questions.
    weak_first = sorted(
        (item for item in evidence if item["status"] != "verified"),
        key=lambda item: item["weight"],
        reverse=True,
    )
    questions = [
        f"Can you walk through a specific example demonstrating {item['criterion']}?"
        for item in weak_first[:3]
    ]
    if len(questions) < 3:
        questions += [
            f"Tell me about a technical trade-off you made while working with {item['criterion']}."
            for item in evidence[: 3 - len(questions)]
        ]

    return {
        "evidence": evidence,
        "score": score,
        "questions": questions[:3],
        "trace": state.get("trace", []) + ["Calculating deterministic score"],
    }


def _build_graph():
    """Wire the steps together exactly like the diagram at the top of the file."""
    graph = StateGraph(EvaluationState)
    graph.add_node("extract", _extract_node)
    graph.add_node("validate", _validate_node)
    graph.add_node("retry", _retry_node)
    graph.add_node("score", _score_node)

    graph.add_edge(START, "extract")
    graph.add_edge("extract", "validate")
    graph.add_conditional_edges(
        "validate", _route_citations, {"score": "score", "retry": "retry"}
    )
    graph.add_edge("retry", "extract")
    graph.add_edge("score", END)
    return graph.compile()


evaluation_graph = _build_graph()  # built once when the server starts


def evaluate_candidate(redacted_text, criteria, use_ai=True):
    """Run the whole flow. Returns fields ready to save on CandidateApplication.

    use_ai=False forces the local keyword matcher (the demo seeder uses this so
    starting the server never spends Mistral credits).
    """
    result = evaluation_graph.invoke(
        {
            "resume_text": redacted_text,
            "criteria": criteria,
            "use_ai": use_ai,
            "attempts": 0,
            "trace": ["Redacting identifying details"],
        }
    )
    return {
        "evidence_matrix": result["evidence"],
        "final_score": result["score"],
        "interview_questions": result["questions"],
        "workflow_trace": result["trace"],
    }
