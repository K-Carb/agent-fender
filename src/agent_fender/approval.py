from dataclasses import dataclass, field


@dataclass
class ApprovalCheck:
    requires_approval: bool
    dangerous_tools_found: list[str]
    message: str | None = None


@dataclass
class DedupCheck:
    is_duplicate: bool
    key: str
    first_seen_at: float | None = None


@dataclass
class InjectionCheck:
    is_suspicious: bool
    patterns_matched: list[str] = field(default_factory=list)
    risk: str = "low"  # "low" | "medium" | "high"


def check_dangerous(
    tool_names: list[str],
    dangerous_tools: frozenset[str],
    *,
    message_template: str = "The following operations require approval: {tools}",
) -> ApprovalCheck:
    matched = [t for t in tool_names if t in dangerous_tools]
    if matched:
        return ApprovalCheck(
            requires_approval=True,
            dangerous_tools_found=matched,
            message=message_template.format(tools=", ".join(matched)),
        )
    return ApprovalCheck(requires_approval=False, dangerous_tools_found=[])


_INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", "high"),
    (r"you\s+are\s+(now\s+)?(a\s+)?different", "medium"),
    (r"pretend\s+(you\s+are|to\s+be)", "medium"),
    (r"forget\s+(everything|all|your\s+training)", "high"),
    (r"system\s*(prompt|message|instruction)\s*(is|:)", "high"),
    (r"\[system\]|<<system>>|\{system\}", "high"),
    (r"new\s+instructions?\s*(:|=)", "medium"),
    (r"disregard\s+(all\s+)?(previous|prior)", "high"),
    (r"from\s+now\s+on\s+you\s+(are|will\s+be)", "low"),
]


def check_injection(
    text: str,
    *,
    custom_patterns: list[tuple[str, str]] | None = None,
) -> InjectionCheck:
    """Detect prompt injection patterns in user input. Pure function, regex-based."""
    import re
    patterns = custom_patterns or _INJECTION_PATTERNS
    matched: list[str] = []
    highest_risk = "low"
    risk_order = {"low": 0, "medium": 1, "high": 2}
    for pattern, risk in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            matched.append(pattern)
            if risk_order.get(risk, 0) > risk_order.get(highest_risk, 0):
                highest_risk = risk
    return InjectionCheck(
        is_suspicious=len(matched) > 0,
        patterns_matched=matched,
        risk=highest_risk,
    )


def check_dedup(
    key: str,
    seen_keys: set[str],
    *,
    now: float | None = None,
) -> DedupCheck:
    """Check if a request key has been seen before. For idempotency."""
    import time
    if key in seen_keys:
        return DedupCheck(is_duplicate=True, key=key)
    seen_keys.add(key)
    return DedupCheck(is_duplicate=False, key=key, first_seen_at=now or time.time())
