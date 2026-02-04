"""
Condition Evaluator
-------------------
Evaluates whether an edge's conditions are satisfied by a user message.

All conditions on a single edge are ANDed together.
If the edge has no conditions, it's a fallback (always True).
"""

import re
from typing import Any


def evaluate_conditions(
    edge_conditions: list[dict[str, Any]],
    user_message: dict[str, Any],
    session_context: dict[str, Any],
) -> bool:
    """
    Returns True if ALL conditions on the edge are satisfied.

    Args:
        edge_conditions: List of condition dicts from the edge.
                         Each has: { "condition_type": "...", "params": {...} }
        user_message:    The incoming user message.
                         Examples:
                           { "text": "да" }
                           { "button": "Продукт" }
        session_context: Current session context (JSONB from chain_sessions.context).
                         Can contain timestamps, previous answers, etc.

    Returns:
        bool: True if all conditions match, False otherwise.
    """
    # No conditions = fallback / unconditional edge
    if not edge_conditions:
        return True

    for cond in edge_conditions:
        cond_type = cond.get("condition_type")
        params    = cond.get("params", {})

        if not _evaluate_single_condition(cond_type, params, user_message, session_context):
            return False  # AND logic: any failure → whole edge fails

    return True


def _evaluate_single_condition(
    cond_type: str,
    params: dict[str, Any],
    user_message: dict[str, Any],
    session_context: dict[str, Any],
) -> bool:
    """
    Evaluates a single condition.
    """
    if cond_type == "button_press":
        return _eval_button_press(params, user_message)

    elif cond_type == "text_contains":
        return _eval_text_contains(params, user_message)

    elif cond_type == "text_regex":
        return _eval_text_regex(params, user_message)

    elif cond_type == "timeout":
        # Timeout is evaluated separately by the scheduler, not here.
        # When a timeout task fires, it advances the session without a user message.
        # So this function should never see a timeout condition in normal message flow.
        # Return False to be safe.
        return False

    elif cond_type == "any_reply":
        return _eval_any_reply(user_message)

    else:
        # Unknown condition type → fail safe
        return False


# ===========================================================================
# INDIVIDUAL CONDITION EVALUATORS
# ===========================================================================

def _eval_button_press(params: dict, user_message: dict) -> bool:
    """
    Checks if the user pressed a specific button.

    params:       { "button_label": "Продукт" }
    user_message: { "button": "Продукт" }
    """
    expected_button = params.get("button_label", "")
    pressed_button  = user_message.get("button", "")

    return pressed_button == expected_button


def _eval_text_contains(params: dict, user_message: dict) -> bool:
    """
    Checks if the user's text message contains a substring.

    params:       { "substring": "да", "case_sensitive": False }
    user_message: { "text": "Да, конечно" }
    """
    substring      = params.get("substring", "")
    case_sensitive = params.get("case_sensitive", False)
    user_text      = user_message.get("text", "")

    if not case_sensitive:
        substring = substring.lower()
        user_text = user_text.lower()

    return substring in user_text


def _eval_text_regex(params: dict, user_message: dict) -> bool:
    """
    Checks if the user's text matches a regex pattern.

    params:       { "pattern": "^да$", "flags": "i" }
    user_message: { "text": "да" }
    """
    pattern   = params.get("pattern", "")
    flags_str = params.get("flags", "")
    user_text = user_message.get("text", "")

    # Parse regex flags (e.g., "i" → re.IGNORECASE)
    flags = 0
    if "i" in flags_str.lower():
        flags |= re.IGNORECASE
    if "m" in flags_str.lower():
        flags |= re.MULTILINE
    if "s" in flags_str.lower():
        flags |= re.DOTALL

    try:
        return re.search(pattern, user_text, flags) is not None
    except re.error:
        # Invalid regex → fail safe
        return False


def _eval_any_reply(user_message: dict) -> bool:
    """
    Matches any user message (catch-all).

    user_message: { "text": "..." } or { "button": "..." } or { "photo": ... }
    """
    # If the message has any content, it's a reply
    return bool(user_message.get("text") or user_message.get("button") or user_message.get("photo"))


# ===========================================================================
# HELPER: Prepare user message dict from Telegram update
# ===========================================================================

def telegram_message_to_dict(telegram_update: dict) -> dict[str, Any]:
    """
    Converts a Telegram update/message into a normalized dict for condition evaluation.

    Example Telegram updates:
        Text message:   { "message": { "text": "Hello" } }
        Button press:   { "callback_query": { "data": "button_label" } }
        Photo:          { "message": { "photo": [...], "caption": "..." } }

    Returns:
        dict with keys: "text", "button", "photo", etc.
    """
    result = {}

    # Text message
    if "message" in telegram_update:
        msg = telegram_update["message"]
        if "text" in msg:
            result["text"] = msg["text"]
        if "photo" in msg:
            result["photo"] = msg["photo"]
            if "caption" in msg:
                result["caption"] = msg["caption"]

    # Callback query (button press)
    if "callback_query" in telegram_update:
        callback = telegram_update["callback_query"]
        if "data" in callback:
            result["button"] = callback["data"]

    return result
