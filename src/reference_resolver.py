import re


def extract_option_number(message: str) -> int | None:
    match = re.search(r"\b(?:option|number|#)\s*(\d+)\b", message.lower())
    if match:
        return int(match.group(1))
    number_words = {"first": 1, "second": 2, "third": 3}
    match = re.search(r"\bthe\s+(first|second|third)\s+one\b", message.lower())
    return number_words.get(match.group(1)) if match else None