"""
Privacy helpers: hide a candidate's identity, and lock it away safely.

  redact_resume()  replaces name, email, phone, university and pronouns with
                   placeholders like [EMAIL_REDACTED] and returns the removed
                   values separately.
  encrypt_pii() /  turn those removed values into an unreadable string for the
  decrypt_pii()    database (Fernet encryption) and back again.

These are simple pattern-based rules - good for a demo, not a legal guarantee.
"""
import json
import re

from cryptography.fernet import Fernet
from django.conf import settings

# Patterns that spot common identity details in resume text.
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
UNIVERSITY_RE = re.compile(
    r"\b(?:[A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,5}\s+"
    r"(?:University|College|Institute)|(?:University|College|Institute)"
    r"\s+of\s+[A-Z][\w&.'-]*(?:\s+[A-Z][\w&.'-]*){0,3})\b"
)
NAME_LABEL_RE = re.compile(r"(?im)^\s*(?:name|candidate)\s*:\s*(.+?)\s*$")  # "Name: Jane Doe"
NAME_LINE_RE = re.compile(r"^[A-Z][a-z]+(?:[ '-][A-Z][a-z]+){1,3}$")        # first line "Jane Doe"
PRONOUN_RE = re.compile(
    r"\b(?:he|him|his|she|her|hers|they|them|their|theirs)\b", re.I
)


def _cipher():
    return Fernet(settings.PII_ENCRYPTION_KEY)


def encrypt_pii(data):
    """dict -> encrypted text that is safe to store."""
    return _cipher().encrypt(json.dumps(data).encode()).decode()


def decrypt_pii(value):
    """Encrypted text -> the original dict ({} if there is nothing stored)."""
    if not value:
        return {}
    return json.loads(_cipher().decrypt(value.encode()))


def redact_resume(text):
    """Return (redacted_text, pii). `pii` holds the values that were removed."""
    pii = {}
    lines = text.splitlines()

    # 1) The candidate's name: either a "Name: ..." line near the top, or a
    #    first line that is just a person's name.
    for index, line in enumerate(lines[:5]):
        match = NAME_LABEL_RE.match(line)
        if match:
            pii["name"] = match.group(1).strip()
            lines[index] = NAME_LABEL_RE.sub("[CANDIDATE_ID_REDACTED]", line)
            break
        if index == 0 and NAME_LINE_RE.fullmatch(line.strip()):
            pii["name"] = line.strip()
            lines[index] = "[CANDIDATE_ID_REDACTED]"
            break

    # 2) Email, phone and university anywhere in the text. We remember the first
    #    match of each so it can be revealed later.
    text = "\n".join(lines)
    for key, pattern, replacement in (
        ("email", EMAIL_RE, "[EMAIL_REDACTED]"),
        ("phone", PHONE_RE, "[PHONE_REDACTED]"),
        ("university", UNIVERSITY_RE, "[UNIVERSITY_REDACTED]"),
    ):
        matches = pattern.findall(text)
        if matches:
            pii[key] = matches[0]
            text = pattern.sub(replacement, text)

    # 3) Gendered pronouns, to reduce bias during screening.
    text = PRONOUN_RE.sub("[PRONOUN_REDACTED]", text)
    return text, pii
