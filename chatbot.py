"""Rule-based interactive terminal chatbot with multi-intent recognition."""
import json
import re
from pathlib import Path

FAQ_FILE = Path(__file__).with_name("faq.json")
CONFIDENCE_THRESHOLD = 0.35

STOPWORDS = {
    "the", "a", "an", "is", "are", "do", "does", "you", "your", "i", "my", "me",
    "to", "of", "for", "on", "in", "it", "can", "what", "how", "and", "or", "we",
}

# ---------- Intent rules (regex patterns -> response) ----------
INTENTS = {
    "greeting": {
        "patterns": [r"\b(hi|hello|hey|good (morning|afternoon|evening))\b"],
        "response": "Hello! I'm your support assistant. Ask me about our hours, "
                    "products, shipping, returns or payments.",
    },
    "hours": {
        "patterns": [r"\b(hours?|open|opening|close|closing|timings?|schedule)\b"],
        "response": "We're open Monday-Friday 9:00 AM - 6:00 PM and "
                    "Saturday 10:00 AM - 4:00 PM. Closed on Sunday.",
    },
    "shipping": {
        "patterns": [r"\b(ship(ping)?|deliver(y)?|track(ing)?)\b"],
        "response": "Standard delivery takes 3-5 business days. You get a "
                    "tracking link by email once your order ships.",
    },
    "returns": {
        "patterns": [r"\b(return|refund|exchange|money back)\b"],
        "response": "You can return items within 30 days for a full refund, "
                    "as long as they are unused and in original packaging.",
    },
    "payment": {
        "patterns": [r"\b(pay(ment)?|card|visa|mastercard|cash|price|cost)\b"],
        "response": "We accept credit/debit cards, bank transfer and "
                    "cash on delivery.",
    },
    "contact": {
        "patterns": [r"\b(contact|phone|email|reach|support|agent|human)\b"],
        "response": "Reach us at support@example.com or +1-555-0100.",
    },
    "thanks": {
        "patterns": [r"\b(thanks?|thank you|thx)\b"],
        "response": "You're welcome! Anything else I can help with?",
    },
}

EXIT_PATTERN = re.compile(r"\b(bye|exit|quit|goodbye)\b")


# ---------- Helpers ----------
def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s']", " ", text)
    return re.sub(r"\s+", " ", text)


def keywords(text: str) -> set:
    return {w for w in normalize(text).split() if w not in STOPWORDS}


def load_faq(path: Path) -> list:
    """Load FAQ entries from JSON. Accepts a list of {question, answer}
    objects, or a dict with a 'faqs'/'questions' list, or {question: answer}."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warning] Could not read {path.name}: {e}")
        return []

    if isinstance(data, dict):
        for key in ("faqs", "faq", "questions", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [{"question": q, "answer": a} for q, a in data.items()]

    entries = []
    for item in data:
        if isinstance(item, dict):
            q = item.get("question") or item.get("q")
            a = item.get("answer") or item.get("a")
            if q and a:
                entries.append({"question": q, "answer": a, "kw": keywords(q)})
    return entries


# ---------- Matching ----------
def match_intents(text: str) -> list:
    """Return ALL intents whose patterns match (multi-intent recognition)."""
    found = []
    for name, rule in INTENTS.items():
        if any(re.search(p, text) for p in rule["patterns"]):
            found.append(name)
    return found


def match_faq(text: str, faq: list):
    """Return (best_entry, confidence) using keyword overlap (Jaccard-like)."""
    user_kw = keywords(text)
    best, best_score = None, 0.0
    if not user_kw:
        return None, 0.0
    for entry in faq:
        if not entry["kw"]:
            continue
        overlap = len(user_kw & entry["kw"])
        score = overlap / min(len(user_kw), len(entry["kw"]))
        if score > best_score:
            best, best_score = entry, score
    return best, best_score


# ---------- Chat loop with state management ----------
def main():
    faq = load_faq(FAQ_FILE)
    state = "greeting"
    fallback_count = 0

    print("=" * 50)
    print(" Support Assistant  (type 'bye', 'exit' or 'quit' to leave)")
    print("=" * 50)
    if faq:
        print(f"[loaded {len(faq)} FAQ entries]")

    while True:
        try:
            raw = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nBot: Goodbye!")
            break

        text = normalize(raw)
        if not text:
            print("Bot: Please type a question.")
            continue

        # Exit
        if EXIT_PATTERN.search(text):
            print("Bot: Thanks for chatting. Goodbye!")
            break

        # Intent identification
        intents = match_intents(text)
        replies = []

        # A greeting alone, or first message, moves state forward
        if state == "greeting" and "greeting" not in intents and not intents:
            state = "intent_identification"

        for name in intents:
            # Don't repeat "hello" when the user also asked a real question
            if name == "greeting" and len(intents) > 1:
                continue
            replies.append(INTENTS[name]["response"])

        # FAQ dataset lookup if no rule matched or to enrich the answer
        if not replies:
            entry, conf = match_faq(text, faq)
            if entry and conf >= CONFIDENCE_THRESHOLD:
                replies.append(entry["answer"])

        # Resolution or fallback
        if replies:
            fallback_count = 0
            state = "resolution"
            print("Bot: " + "\nBot: ".join(replies))
            if state == "resolution" and "thanks" not in intents:
                print("Bot: Is there anything else I can help with?")
            state = "intent_identification"
        else:
            fallback_count += 1
            if fallback_count >= 2:
                print("Bot: I'm still not sure I understand. You can ask about "
                      "hours, shipping, returns, payment, or contact details, "
                      "or email support@example.com for a human agent.")
            else:
                print("Bot: Sorry, I didn't get that. Could you rephrase?")


if __name__ == "__main__":
    main()