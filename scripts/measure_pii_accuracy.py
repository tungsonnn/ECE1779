"""Measure how well PII detection works, on fake data.

OWNER: Hira (LLM + PII).

Builds prompts from templates and made-up values, so we know exactly where the
PII is. Each prompt goes through the same code the proxy uses (the Presidio
Analyzer container, our API-key patterns, the overlap rule), and we count:

  hidden       PII that was replaced. This is the number that matters for privacy.
  missed       PII that was NOT replaced. A leak.
  false alarm  ordinary text that was replaced. No leak, but it can confuse the model.

Run it with the stack up (docker compose up), from the repo root:

  docker run --rm --network ece1779_default -e PRESIDIO_URL=http://presidio-analyzer:3000 \\
    -v "${PWD}:/w" -w /w python:3.12-slim \\
    sh -c "pip install -q -r requirements.txt && python -m scripts.measure_pii_accuracy"

Add --no-allow-list to see the numbers without the label-word allow list.
All values are fake: 555 phone numbers, test card numbers, documentation IPs.
"""

import argparse
import random
import re
from collections import Counter

from app.services import pii

VALUES = {
    "PERSON": [
        "Sara Khan", "David Lee", "Maria Garcia", "John Smith", "Aisha Ahmed", "Wei Chen",
        "Priya Patel", "Michael Brown", "Fatima Hassan", "James Wilson", "Olivia Martin", "Daniel Kim",
    ],
    "LOCATION": [
        "Toronto", "Vancouver", "Montreal", "London", "Karachi", "New York", "Paris", "Tokyo",
        "Chicago", "Lahore",
    ],
    "EMAIL_ADDRESS": [
        "sara.khan@example.com", "d.lee@example.org", "maria_garcia@example.net",
        "jsmith42@example.com", "aisha@mail.example.com", "wei.chen@example.co.uk",
    ],
    "PHONE_NUMBER": ["416-555-0199", "(647) 555-0142", "+1 604 555 0188", "905-555-0123", "212-555-0147"],
    "CREDIT_CARD": [
        "4111 1111 1111 1111", "5555 5555 5555 4444", "4012888888881881", "3782 822463 10005",
        "6011 1111 1111 1117",
    ],
    "IP_ADDRESS": ["192.168.1.10", "10.0.0.25", "172.16.254.1", "203.0.113.42", "198.51.100.7"],
    "API_KEY": [
        "sk-live-9f8a7b6c5d4e3f2a1b0c", "sk-proj-A1b2C3d4E5f6G7h8I9j0K1l2",
        "ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8", "AKIAIOSFODNN7EXAMPLE",
    ],
}

# {TYPE} marks where a fake value goes. {TYPE|lower} writes it in lowercase,
# {TYPE|upper} in capitals, {TYPE|digits} keeps only the digits. The first
# block is everyday prompts, the second is harder on purpose (no capitals,
# no separators), and the last four have no PII at all.
TEMPLATES = [
    "Hi, I'm {PERSON} from {LOCATION}.",
    "Please email {PERSON} at {EMAIL_ADDRESS} about the {LOCATION} office.",
    "Call {PERSON} on {PHONE_NUMBER} tomorrow.",
    "My card number is {CREDIT_CARD}, can you check the format?",
    "The server at {IP_ADDRESS} is down and {PERSON} is looking into it.",
    "Here is my config: API_KEY={API_KEY}",
    "Put this into a table with columns Name, City, Email: {PERSON}, {LOCATION}, {EMAIL_ADDRESS}",
    "Name: {PERSON}\nEmail: {EMAIL_ADDRESS}\nPhone: {PHONE_NUMBER}",
    "{PERSON} and {PERSON} are meeting in {LOCATION} on Friday.",
    "Rewrite this politely: hey its {PERSON}, call me back at {PHONE_NUMBER}.",
    "Customer {PERSON} ({EMAIL_ADDRESS}) paid with card {CREDIT_CARD}.",
    "ssh admin@{IP_ADDRESS} fails with a timeout.",
    "Summarize: {PERSON} moved from {LOCATION} to {LOCATION} last year.",
    "export OPENAI_API_KEY={API_KEY}  # why does this not work?",
    "Translate to French: My name is {PERSON} and I live in {LOCATION}.",
    "Order 1042 for {PERSON}, ship to {LOCATION}, contact {PHONE_NUMBER}.",
    "Email {EMAIL_ADDRESS} please.",
    "Write a thank-you note to {PERSON} for the visit to {LOCATION}.",
    "Token: {API_KEY}\nAddress: {IP_ADDRESS}",
    "Patient {PERSON}, phone {PHONE_NUMBER}, card on file {CREDIT_CARD}.",
    # Harder on purpose.
    "hey its {PERSON|lower} from {LOCATION|lower}, can u call me",
    "{PERSON|lower}'s number is {PHONE_NUMBER|digits}",
    "Dear {PERSON},\n\nThanks for visiting {LOCATION}.\n\nRegards,\n{PERSON}",
    "Subject: Meeting with {PERSON}\nCc: {EMAIL_ADDRESS}",
    "Thanks {PERSON}! See you in {LOCATION}.",
    "user={PERSON|lower} ip={IP_ADDRESS} card={CREDIT_CARD|digits}",
    "Contact: {PERSON|upper}, {EMAIL_ADDRESS|upper}",
    "my friend {PERSON} said the best pizza is in {LOCATION}",
    "Password reset for {EMAIL_ADDRESS} from {IP_ADDRESS} by {PERSON|lower}.",
    "Send the invoice to {PERSON|lower} at {EMAIL_ADDRESS|upper}, phone {PHONE_NUMBER|digits}.",
    # No PII at all.
    "Explain how a hash table works.",
    "Write a Python function that reverses a list.",
    "Fix the grammar: me and him goes to school yesterday.",
    "What is the difference between a process and a thread?",
]

_SLOT = re.compile(r"\{([A-Z_]+)(?:\|(lower|upper|digits))?\}")
_STYLE = {
    None: lambda v: v,
    "lower": str.lower,
    "upper": str.upper,
    "digits": lambda v: re.sub(r"\D", "", v),
}


def build_prompt(template: str, rng: random.Random) -> tuple[str, list[tuple[int, int, str]]]:
    """Fill a template. Returns the text and where each fake value sits: (start, end, type)."""
    text, expected, last = "", [], 0
    used: set[str] = set()
    for slot in _SLOT.finditer(template):
        text += template[last:slot.start()]
        entity = slot.group(1)
        value = rng.choice([v for v in VALUES[entity] if v not in used])
        used.add(value)
        value = _STYLE[slot.group(2)](value)
        expected.append((len(text), len(text) + len(value), entity))
        text += value
        last = slot.end()
    return text + template[last:], expected


def overlaps(a: tuple[int, int, str], b: tuple[int, int, str]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prompts", type=int, default=340, help="how many prompts to test (default 340)")
    parser.add_argument("--seed", type=int, default=1779, help="same seed = same prompts")
    parser.add_argument("--no-allow-list", action="store_true", help="measure without the label-word allow list")
    args = parser.parse_args()
    if args.no_allow_list:
        pii.ALLOW_LIST = []

    rng = random.Random(args.seed)
    expected_n, hidden_n, right_type_n, false_alarm_n = Counter(), Counter(), Counter(), Counter()
    false_alarm_words, missed_examples = Counter(), []

    for i in range(args.prompts):
        text, expected = build_prompt(TEMPLATES[i % len(TEMPLATES)], rng)
        # Same two steps scrub() runs: ask Presidio, then keep one finding per stretch of text.
        found = pii._resolve_overlaps(pii._analyze(text))

        for exp in expected:
            expected_n[exp[2]] += 1
            hits = [f for f in found if overlaps(f, exp)]
            if hits:
                hidden_n[exp[2]] += 1
                right_type_n[exp[2]] += any(f[2] == exp[2] for f in hits)
            elif len(missed_examples) < 10:
                missed_examples.append(f"{exp[2]}: {text[exp[0]:exp[1]]!r} in {text!r}")
        for f in found:
            if not any(overlaps(f, exp) for exp in expected):
                false_alarm_n[f[2]] += 1
                false_alarm_words[f"{text[f[0]:f[1]]} ({f[2]})"] += 1

    print(f"\nPII detection on {args.prompts} fake prompts"
          f" (seed {args.seed}, threshold {pii.SCORE_THRESHOLD},"
          f" allow list {'off' if args.no_allow_list else 'on'})\n")
    print(f"{'Type':<15}{'Expected':>9}{'Hidden':>8}{'Missed':>8}{'Hidden %':>10}{'Right type %':>14}{'False alarms':>14}")
    for entity in pii.ENTITIES:
        n, h = expected_n[entity], hidden_n[entity]
        pct = f"{100 * h / n:.1f}" if n else "-"
        typ = f"{100 * right_type_n[entity] / n:.1f}" if n else "-"
        print(f"{entity:<15}{n:>9}{h:>8}{n - h:>8}{pct:>10}{typ:>14}{false_alarm_n[entity]:>14}")
    n, h = sum(expected_n.values()), sum(hidden_n.values())
    print(f"{'ALL':<15}{n:>9}{h:>8}{n - h:>8}{100 * h / n:>10.1f}"
          f"{100 * sum(right_type_n.values()) / n:>14.1f}{sum(false_alarm_n.values()):>14}")

    print("\nMost common false alarms (ordinary text that was replaced):")
    for word, count in false_alarm_words.most_common(10):
        print(f"  {count:>3}  {word}")
    if not false_alarm_words:
        print("  none")
    print("\nMissed PII (first 10):")
    for line in missed_examples or ["  none"]:
        print(f"  {line}" if missed_examples else line)


if __name__ == "__main__":
    main()
