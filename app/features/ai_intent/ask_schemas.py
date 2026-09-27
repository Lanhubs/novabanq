"""AI ask schemas.

HTTP boundary models for the AI financial assistant endpoint,
``POST /ai/ask``. The user asks a question in plain language, Nova
classifies it, fetches whatever data the question needs, and answers
in warm natural-language prose.

Two models:

    * ``AskRequest`` — the raw question the user typed.
    * ``AskResponse`` — the classification, the answer, and the
      structured data behind the answer.

The ``AskKind`` enum lives here rather than in ``app/core/constants``
because it isn't cross-feature. Every enum in ``constants`` is
something the ledger persists or that multiple features read —
``Currency``, ``AccountType``, ``TransactionType``, and so on.
``AskKind`` is a response-shape tag for one endpoint. It isn't
persisted, isn't read by any other feature, and if the kind list
grows or shrinks, the change should stay contained to the ``ask_``
files. Putting it in ``constants`` would put feature-private
vocabulary in the module every other feature imports from, for no
benefit.

Adding or removing a member of ``AskKind`` is a breaking change for
the service layer — the classification prompt, the answer prompt,
and the per-kind data-fetch branches all enumerate the same list.
Update them in the same commit. ``NO_DATA_ASK_KINDS`` (below) is the
single source of truth for which kinds never fetch data; branch on
membership in it rather than re-listing ``GREETING`` /
``GENERAL_FINANCE`` / ``UNKNOWN`` by hand elsewhere, so a future kind
added to that group can't update the enum without also updating every
place that cared.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AskKind(StrEnum):
    """The nine question types Nova can classify a user's question into.

    ``StrEnum`` so the value serializes to its string form
    (``"BALANCE"``) in JSON, and comparisons against the value work
    naturally. The service branches on these members by identity
    (``kind is AskKind.BALANCE``), never on the raw string.

    The kinds and their data-fetch requirements:

    ===================== ==========================================
    Kind                  Data needed to answer
    ===================== ==========================================
    GREETING              none — deterministic reply, no data lookup
    BALANCE               the user's account balance
    LAST_RECIPIENT        the user's most recent outbound transfer
    SPENDING_SUMMARY      aggregated totals over a time period
    COUNTERPARTY_DETAILS  transaction history with one counterparty
    SPENDING_ADVICE       recent transaction patterns, aggregated
    GENERAL_FINANCE       none — general knowledge, no data lookup
    TRANSFER_INTENT       none — redirect reply, no data lookup
    UNKNOWN               none — fallback reply, no data lookup
    ===================== ==========================================

    See ``NO_DATA_ASK_KINDS`` for the "none" rows that are answered
    from a template without any data fetch at all. ``TRANSFER_INTENT``
    is also answerless, but it's short-circuited in ``answer_question``
    before ``_fetch_data`` is ever reached, so it isn't a member of
    that set — the set means "kinds that *reach* the fetch step but
    need no data," and ``TRANSFER_INTENT`` never reaches it.
    """

    GREETING = "GREETING"
    BALANCE = "BALANCE"
    LAST_RECIPIENT = "LAST_RECIPIENT"
    SPENDING_SUMMARY = "SPENDING_SUMMARY"
    COUNTERPARTY_DETAILS = "COUNTERPARTY_DETAILS"
    SPENDING_ADVICE = "SPENDING_ADVICE"
    GENERAL_FINANCE = "GENERAL_FINANCE"
    TRANSFER_INTENT = "TRANSFER_INTENT"
    UNKNOWN = "UNKNOWN"


# Deliberately defined outside the class body, not as a class
# attribute of AskKind: an Enum's metaclass treats any plain
# class-body assignment as a candidate new member unless it's a
# descriptor, and a frozenset isn't a string, so declaring this
# inside the class would raise TypeError at import time for a
# StrEnum. Defining it here, right after the class, keeps it next to
# what it describes without that trap.
#
# Note the membership: this set is specifically "kinds that pass
# through the data-fetch step but do not need any data." Kinds whose
# answer is produced by a short-circuit template in
# ``answer_question`` never reach the fetch step at all, so they're
# not members. If a future kind is added that reaches the fetch step
# and needs nothing, add it here; if it short-circuits earlier, leave
# it out.
NO_DATA_ASK_KINDS: frozenset[AskKind] = frozenset(
    {AskKind.GREETING, AskKind.GENERAL_FINANCE, AskKind.UNKNOWN}
)


class AskRequest(BaseModel):
    """The user's question to the assistant.

    Unconstrained beyond a length cap — the whole point of Nova is
    that the user can ask in their own words. The service is what
    routes the question; the schema just carries the raw text.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description=(
            "The user's question, verbatim. Any of: a greeting, a "
            "balance check, a question about past transactions, a "
            "spending summary, a request for advice based on the "
            "user's own spending, a general money question, a "
            "send-money instruction, or something unrelated that "
            "will fall through to UNKNOWN."
        ),
        examples=["who did I send money to last?", "what's my balance?"],
    )


class AskResponse(BaseModel):
    """Nova's answer to the user's question.

    Three fields: the classification, the answer itself, and the
    structured data behind the answer. ``kind`` is the discriminator
    the frontend switches on to decide how to render the accompanying
    data — a plain text card for a GREETING, a balance card for a
    BALANCE, a small table for a SPENDING_SUMMARY, and so on.

    The ``data`` field is typed ``dict[str, Any] | None`` deliberately,
    rather than a discriminated union of nine per-kind models. The
    shapes are small and varied (a balance is two fields, a summary is
    four, a counterparty detail is a handful), the frontend mostly
    renders them optionally, and nine near-identical response
    containers would be real overhead for little safety gained. The
    service layer defines a ``TypedDict`` per kind for internal
    type-checking on the *construction* side — those aren't exposed
    here.

    Because ``data`` is ``Any``-typed, nothing here enforces that its
    values are already JSON-safe. Whoever builds this field for a
    money-carrying kind (``BALANCE``, ``SPENDING_SUMMARY``, and so on)
    is responsible for putting in a plain, already-serialized amount
    (an ``int`` in minor units, or a pre-formatted string) rather than
    a raw ``Decimal`` — a static field type can't catch that for an
    ``Any``-typed value the way it could for a properly typed field.
    ``ask_service._json_safe`` is the boundary sanitizer that enforces
    this guarantee structurally.

    Frozen — a response is a read-only projection.
    """

    model_config = ConfigDict(frozen=True)

    kind: AskKind = Field(
        ...,
        description=(
            "The classification of the user's question. Determines "
            "the shape of ``data``. Always one of the nine "
            "``AskKind`` members."
        ),
        examples=["BALANCE"],
    )
    answer: str = Field(
        ...,
        min_length=1,
        description=(
            "Nova's natural-language reply. Ready to display as-is."
        ),
        examples=["You've got GH₵2,340.50 in your account, David."],
    )
    data: dict[str, Any] | None = Field(
        None,
        description=(
            "Structured data behind the answer, if any was needed. "
            "Null for the kinds in ``NO_DATA_ASK_KINDS`` (``GREETING``, "
            "``GENERAL_FINANCE``, ``UNKNOWN``) and for "
            "``TRANSFER_INTENT`` — none of those fetch from the "
            "user's account. For other kinds, the shape depends on "
            "``kind``; see ``AskKind``'s docstring for the per-kind "
            "shape table."
        ),
        examples=[{"balance_minor": 234050, "currency": "GHS"}],
    )