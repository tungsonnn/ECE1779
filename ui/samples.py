"""Curated fake-data sample prompts for the Demo Playground.

OWNER: Daniel (Security + UI).

All data here is synthetic and covers the PII entity types in scope:
EMAIL_ADDRESS, PHONE_NUMBER, CREDIT_CARD, IP_ADDRESS, PERSON, LOCATION,
and custom API keys / secrets pasted alongside code.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SamplePrompt:
    """A pre-built fake prompt for quick testing and live demos."""

    label: str
    description: str
    expected_entities: tuple[str, ...]
    prompt: str


SAMPLE_PROMPTS: tuple[SamplePrompt, ...] = (
    SamplePrompt(
        label="Customer Support Email",
        description="Name, email address, phone number, and city.",
        expected_entities=("PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION"),
        prompt=(
            "Draft a polite reply to Jordan Rivera (jordan.rivera@example.com, "
            "416-555-0192) letting them know their replacement order to Toronto "
            "has shipped and will arrive by Friday."
        ),
    ),
    SamplePrompt(
        label="Billing & Card Inquiry",
        description="Person, credit card number, and email address.",
        expected_entities=("PERSON", "CREDIT_CARD", "EMAIL_ADDRESS"),
        prompt=(
            "Summarize this support ticket: Customer Priya Patel reported a duplicate "
            "charge on card 4532-0151-1283-0366. Please send the refund receipt to "
            "priya.patel@example.org."
        ),
    ),
    SamplePrompt(
        label="Incident Log & API Key",
        description="IP address, person, and a leaked secret/API key in code.",
        expected_entities=("PERSON", "IP_ADDRESS", "API_KEY"),
        prompt=(
            "Help debug this Python snippet from Alex Chen running on host 192.168.42.17:\n\n"
            "client = OpenAI(api_key=\"sk-proj-fakeDemoKey9876543210abcdef\")\n"
            "resp = client.responses.create(model=\"gpt-4.1\", input=\"ping\")\n"
            "Why am I getting a connection timeout?"
        ),
    ),
    SamplePrompt(
        label="Clean Prompt (No PII)",
        description="Control prompt with no personal data or secrets.",
        expected_entities=(),
        prompt=(
            "Explain the difference between symmetric and asymmetric encryption "
            "in three concise bullet points."
        ),
    ),
)

# Dev/demo API key presets matching app/services/auth.py stubs.
DEMO_KEY_PRESETS: dict[str, str | None] = {
    "Demo Team A (demo-key-a)": "demo-key-a",
    "Demo Team B (demo-key-b)": "demo-key-b",
    "Invalid Key (test 401)": "not-a-valid-key",
    "No Key (test 401)": None,
    "Custom API Key": "__custom__",
}
