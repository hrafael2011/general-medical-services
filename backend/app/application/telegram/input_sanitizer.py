"""Input sanitization for Telegram user messages before LLM processing.

Protects against prompt injection, jailbreak attempts, and prompt
leak attacks by blocking known attack patterns before user text
reaches the LLM.
"""

import re

# ── Regex patterns that indicate a prompt injection / jailbreak attempt ──────
_FORBIDDEN_PATTERNS: list[re.Pattern] = [
    # "Ignore all instructions" / "Forget previous" patterns (en + es)
    re.compile(
        r"(ignor[aeá]\s+(tod[oa]s?\s+)?(las?\s+)?instrucciones?|"
        r"olvida\s+(tod[oa]s?\s+)?(las?\s+)?instrucciones?|"
        r"desobedece\s+(tod[oa]s?\s+)?(las?\s+)?instrucciones?|"
        r"ignore\s+(all\s+|the\s+|previous\s+)*(instructions?|prompts?|context)|"
        r"forget\s+(all\s+|the\s+|previous\s+)*(instructions?|prompts?|context)|"
        r"disregard\s+(all\s+|the\s+|previous\s+)*(instructions?|prompts?|context))",
        re.IGNORECASE,
    ),
    # Role-switching: "you are now..." / "act as..."
    re.compile(
        r"(eres\s+(ahora\s+)?|act[uú]as?\s+como\s+|"
        r"you\s+are\s+now\s+|"
        r"from\s+now\s+on\s+you\s+are\s+(an?\s+)?|"
        r"pretend\s+you\s+are\s+|"
        r"act\s+as\s+(an?\s+|if\s+you\s+were\s+))"
        r"(un\s+)?(nuevo\s+)?(asistente|sistema|rol|assistant|system|role|"
        r"malvado|evil|hacker|sin\s+restricciones|unrestricted|DAN)",
        re.IGNORECASE,
    ),
    # System prompt markers: "system:", "<system>", "[system]"
    re.compile(
        r"(system\s*:|<system>|\[system\]|<<system>>|"
        r"<\|system\|>|\[INST\]|<<SYS>>)",
        re.IGNORECASE,
    ),
    # Prompt leak: "show me your prompt", "reveal your instructions"
    re.compile(
        r"(mu[eé]strame|dime|revela|ense[nñ]a|"
        r"show\s+me|tell\s+me|reveal|display|print|"
        r"dump|leak|extract|output)\s+"
        r"(tu|el|your|the)\s+"
        r"(prompt|system\s+prompt|instrucciones?|instructions?|"
        r"config|configuration|directivas?|directives?)",
        re.IGNORECASE,
    ),
    # Credential / secret fishing — catch api_key, token, password anywhere
    re.compile(
        r"\b(api[_\s]?key|api[_\s]?secret|contrase[nñ]a|password|"
        r"secret[_\s]?key|token\s+de\s+acceso)\b",
        re.IGNORECASE,
    ),
    # "You are a [new] assistant" role injection
    re.compile(
        r"(ahora\s+)?eres\s+un\s+nuevo\s+",
        re.IGNORECASE,
    ),
    # DAN / jailbreak keywords
    re.compile(
        r"\b(DAN|jailbreak|do\s+anything\s+now|"
        r"developer\s+mode|modo\s+desarrollador|"
        r"sin\s+censura|uncensored)\b",
        re.IGNORECASE,
    ),
]

MAX_INPUT_LENGTH = 2000


class InputSanitizer:
    """Sanitizes user input before it reaches the LLM.

    Usage::

        sanitizer = InputSanitizer()
        is_safe, cleaned = sanitizer.sanitize(user_text)
        if not is_safe:
            return "⚠️ No puedo procesar esa solicitud."
    """

    def sanitize(self, user_input: str) -> tuple[bool, str]:
        """Check and clean user input.

        Returns:
            ``(is_safe, sanitized_text)`` where *is_safe* is ``False``
            if the input should be blocked.
        """
        if not user_input or not user_input.strip():
            return False, ""

        # Length check — unusually long messages are suspicious
        if len(user_input) > MAX_INPUT_LENGTH:
            return False, ""

        # Check against forbidden patterns
        for pattern in _FORBIDDEN_PATTERNS:
            if pattern.search(user_input):
                return False, ""

        return True, user_input.strip()
