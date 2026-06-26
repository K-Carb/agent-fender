from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

logger = logging.getLogger("agent_fender")


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

    @property
    def needs_deeper_scan(self) -> bool:
        """True when risk is high — caller should consider semantic-level analysis."""
        return self.risk == "high"


def check_dangerous(
    tool_names: list[str],
    dangerous_tools: frozenset[str],
    *,
    message_template: str = "The following operations require approval: {tools}",
) -> ApprovalCheck:
    """Check if any tool in tool_names is in the dangerous set."""
    matched = [t for t in tool_names if t in dangerous_tools]
    if matched:
        return ApprovalCheck(
            requires_approval=True,
            dangerous_tools_found=matched,
            message=message_template.format(tools=", ".join(matched)),
        )
    return ApprovalCheck(requires_approval=False, dangerous_tools_found=[])


_RAW_INJECTION_PATTERNS: list[tuple[str, str]] = [
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

_INJECTION_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pattern, re.IGNORECASE), risk)
    for pattern, risk in _RAW_INJECTION_PATTERNS
]

_MAX_INPUT_LENGTH = 4096


def check_injection(
    text: str,
    *,
    custom_patterns: list[tuple[str, str]] | None = None,
) -> InjectionCheck:
    """Detect prompt injection patterns in user input. Regex-based baseline."""
    if len(text) > _MAX_INPUT_LENGTH:
        logger.warning("Injection check input truncated from %d to %d chars",
                       len(text), _MAX_INPUT_LENGTH)
        text = text[:_MAX_INPUT_LENGTH]

    if custom_patterns:
        rules = [(re.compile(p, re.IGNORECASE), r) for p, r in custom_patterns]
    else:
        rules = _INJECTION_RULES

    matched: list[str] = []
    highest_risk = "low"
    risk_order = {"low": 0, "medium": 1, "high": 2}
    for compiled, risk in rules:
        if compiled.search(text):
            matched.append(compiled.pattern)
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
    """Check if a request key has been seen before. For idempotency.

    Mutates seen_keys — adds the key on first sight. This is the only public
    function in agent-fender with a side effect. Pass a copy if you need the
    original set unchanged.
    """
    if key in seen_keys:
        return DedupCheck(is_duplicate=True, key=key)
    seen_keys.add(key)
    return DedupCheck(is_duplicate=False, key=key, first_seen_at=now or time.time())
