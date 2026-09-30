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

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AskKind(StrEnum):
    """The eleven question types Nova can classify a user's question into.

    ``StrEnum`` so the value serializes to its string form
    (``"BALANCE"``) in JSON, and comparisons against the value work
    naturally. The service branches on these members by identity
    (``kind is AskKind.BALANCE``), never on the raw string.

    The kinds and their data-fetch requirements:

    ====================== ==========================================
    Kind                   Data needed to answer
    ====================== ==========================================
    GREETING               none — deterministic reply, no data lookup
    BALANCE                the user's account balance
    LAST_RECIPIENT         the user's most recent outbound transfer
    SPENDING_SUMMARY       aggregated totals over a time period
    COUNTERPARTY_DETAILS   outgoing transfers with one counterparty
    SPENDING_ADVICE        recent transaction patterns, aggregated
    INBOUND_SENDERS        who has sent money TO the user, grouped
                           by counterparty — the mirror of
                           COUNTERPARTY_DETAILS
    SCHEDULED_TRANSFERS    the user's scheduled transfers — both
                           pending and already-completed schedules,
                           from the scheduled_transfers collection
    GENERAL_FINANCE        none — general knowledge, no data lookup
    TRANSFER_INTENT        none — redirect reply, no data lookup
    UNKNOWN                none — fallback reply, no data lookup
    ====================== ==========================================

    See ``NO_DATA_ASK_KINDS`` for the "none" rows that are answered
    from a template without any data fetch at all. ``TRANSFER_INTENT``
    is also answerless, but it's short-circuited in ``answer_question``
    before ``_fetch_data`` is ever reached, so it isn't a member of
    that set — the set means "kinds that *reach* the fetch step but
    need no data," and ``TRANSFER_INTENT`` never reaches it.

    Why ``SCHEDULED_TRANSFERS`` exists as its own kind: pending
    schedules live in a different Firestore collection from settled
    transactions. A question like "did my scheduled payment to David
    go out?" cannot be answered by looking at ``transactions`` alone
    when the schedule hasn't fired yet, and cannot be answered by
    looking only at ``status == PENDING`` schedules when it has —
    the transfer either hasn't fired (still PENDING) or has already
    produced a transaction (SETTLED or FAILED). The kind therefore
    fetches *all* of the user's scheduled transfers regardless of
    status, and the answer prompt decides what to cite based on what
    the question actually asked.

    Why ``INBOUND_SENDERS`` exists as its own kind: the outbound
    aggregations in ``ask_repository`` — ``summarize_spending`` and
    ``get_counterparty_history`` — only look at transfers the caller
    *sent*. A user asking "who has sent me money?" or "what tags have
    funded me?" is asking about inbound transfers from other users,
    and that data path didn't exist until this kind. The repository
    function ``list_inbound_senders`` groups the caller's inbound
    transfers by sender, and the answer prompt's rule 18 knows how to
    read the data shape and answer the specific question asked.
    """

    GREETING = "GREETING"
    BALANCE = "BALANCE"
    LAST_RECIPIENT = "LAST_RECIPIENT"
    SPENDING_SUMMARY = "SPENDING_SUMMARY"
    COUNTERPARTY_DETAILS = "COUNTERPARTY_DETAILS"
    SPENDING_ADVICE = "SPENDING_ADVICE"
    INBOUND_SENDERS = "INBOUND_SENDERS"
    SCHEDULED_TRANSFERS = "SCHEDULED_TRANSFERS"
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
            "user's own spending, a question about who has sent "
            "money to them, a question about pending or completed "
            "scheduled transfers, a general money question, a "
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
    rather than a discriminated union of eleven per-kind models. The
    shapes are small and varied (a balance is two fields, a summary is
    four, a counterparty detail is a handful), the frontend mostly
    renders them optionally, and eleven near-identical response
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

    The one invariant the schema *does* enforce — via
    ``_verify_data_presence`` — is the negative one: a kind that
    fetches nothing must have ``data=None``. That's cheap to check
    and catches a construction bug (forgetting to null out ``data``
    for a no-data kind) at the boundary rather than only in review.
    The positive case — that a data-bearing kind's ``data`` has the
    right shape for that kind — is not enforced here, because that
    would mean eleven discriminated models, which the paragraph above
    explains is not worth the overhead.

    Frozen — a response is a read-only projection.
    """

    model_config = ConfigDict(frozen=True)

    kind: AskKind = Field(
        ...,
        description=(
            "The classification of the user's question. Determines "
            "the shape of ``data``. Always one of the eleven "
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
            "``GENERAL_FINANCE``, ``UNKNOWN``) and for a "
            "``TRANSFER_INTENT`` whose parse was incomplete (the "
            "help-message branch). For other kinds — including a "
            "successful ``TRANSFER_INTENT`` — the shape depends on "
            "``kind``; see ``AskKind``'s docstring for the per-kind "
            "shape table."
        ),
        examples=[{"balance_minor": 234050, "currency": "GHS"}],
    )

    @model_validator(mode="after")
    def _verify_data_presence(self) -> "AskResponse":
        """Enforce the negative data-presence invariant.

        Kinds in ``NO_DATA_ASK_KINDS`` never fetch anything, so their
        ``data`` must be ``None``. The rule is enforced here rather
        than left to reviewers because a construction bug that puts
        an empty dict in ``data`` for a GREETING is silent otherwise
        — the response still serializes, the frontend still renders
        it, and the bug only shows up as a mysteriously-empty
        structured card for a kind the frontend didn't expect to
        have one.

        Mirrors the equivalent defensive check on
        ``ScheduledTransferResponse`` elsewhere in this codebase.

        Deliberately does NOT enforce the positive case — that a
        data-bearing kind has the right *shape* of ``data``. That
        would require eleven discriminated response models, which
        ``AskResponse``'s docstring explains is a tradeoff not worth
        making for this endpoint.

        ``TRANSFER_INTENT`` is not checked here because it's neither
        purely data-bearing nor purely answerless: a successful parse
        carries the ``confirm_transfer`` payload in ``data``, while
        an incomplete parse carries ``None`` and a help message in
        ``answer``. Both states are valid for the same kind, so a
        presence check would reject one of them. The service is the
        only writer of these responses and it already branches on
        which state to construct.
        """
        if self.kind in NO_DATA_ASK_KINDS and self.data is not None:
            raise ValueError(
                f"data must be None when kind is {self.kind.value}."
            )
        return self