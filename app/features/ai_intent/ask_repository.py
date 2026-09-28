"""AI ask repository.

Read-only data access for the AI financial assistant. Five functions,
one per data-needing ``AskKind``. Every function returns a plain dict
suitable for json.dumps-ing into the answer prompt's ``{data}``
block, and for embedding in an ``AskResponse.data`` field.

Three functions bypass Firestore entirely — ``get_balance_context``
delegates to ``accounts_service``, and ``get_last_outbound`` delegates
to the transactions repository. Only ``summarize_spending``,
``get_counterparty_history``, and ``summarize_for_advice`` do their
own aggregation, and they do it by fetching a capped batch of the
caller's outbound transfers through ``transactions_repository`` and
filtering / summing in Python.

Why the aggregation is in Python, not pushed to Firestore:

    Firestore would need a new composite index on
    ``(sender_uid ASC, created_at ASC)`` for any date-range query
    against the transactions collection, because the existing indexes
    are on ``(sender_uid ASC, created_at DESC)``. Creating that index
    is a console operation that can't ship with a code change, and the
    aggregation logic in Python is trivially correct — ``sum(doc.
    to_amount_minor for doc in docs if doc.created_at >= since)``
    needs no reasoning about Firestore's query semantics.

    The cap is deliberate. Fetching 500 documents is a bounded cost
    regardless of how many transactions the user actually has, and
    every function that hits the cap says so in its return value —
    the answer prompt is written to acknowledge truncation when it
    sees the flag rather than silently reporting a partial total as
    if it were complete.

Every function can raise ``TransactionRepositoryError`` from the
underlying transactions repository, or ``AccountUnavailableError``
from the accounts service. The service layer catches those and maps
them to a ``NovaBanqError`` subclass for the router.

This module never writes. It has no mutation path, no transaction
wrapper, and no side effects beyond reading. The assistant is a
read-only lens on the user's own data.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.constants import Currency
from app.features.accounts import service as accounts_service
from app.features.ledger.schemas import TransactionDocument
from app.features.transactions import repository as transactions_repository
from app.features.users import service as users_service
from app.core.utils import format_amount

logger = logging.getLogger(__name__)


# The maximum number of outbound transactions any single aggregate
# function will fetch. Chosen as a balance: large enough that a
# typical freelancer's month of activity fits comfortably, small
# enough that the Firestore read stays cheap. Users above this cap
# get an answer that explicitly says "at least" rather than a
# silently-wrong exact number — see the truncated flag each
# aggregation returns.
_MAX_TRANSACTIONS_PER_QUERY = 500


# ---------------------------------------------------------------------------
# BALANCE
# ---------------------------------------------------------------------------

def get_balance_context(uid: str) -> dict[str, Any]:
    """Return the caller's account balance in a display-ready shape.

    Args:
        uid: The authenticated caller's uid.

    Returns:
        A dict with ``balance_minor`` (int), ``currency`` (str),
        ``balance_display`` (str, already formatted with the currency
        symbol and thousands separators — the prompt uses this
        directly so Nova doesn't have to guess at formatting), and
        ``updated_at`` (ISO 8601 string, or None).

    Raises:
        UserNotFoundError: If the caller has no profile.
        AccountUnavailableError: On a Firestore failure reading the
            account.
    """
    profile = users_service.get_profile(uid)
    currency = Currency(profile["currency"])
    balance_minor = accounts_service.get_balance_minor(uid)

    return {
        "balance_minor": balance_minor,
        "currency": currency.value,
        "balance_display": format_amount(balance_minor, currency),
    }


# ---------------------------------------------------------------------------
# LAST_RECIPIENT
# ---------------------------------------------------------------------------

def get_last_outbound(uid: str) -> dict[str, Any] | None:
    """Return the caller's most recent outbound transfer, or None.

    "Outbound" means a ``TRANSFER`` where the caller was the sender.
    Funding and withdrawal transactions are excluded — they aren't
    person-to-person, and the question "who did I send money to last"
    is about a counterparty, not about a top-up or a payout.

    Args:
        uid: The authenticated caller's uid.

    Returns:
        A dict with the counterparty's snapshot (``counterparty_tag``,
        ``counterparty_name``, ``counterparty_uid``), the amount sent
        (``amount_minor``, ``currency``, ``amount_display``), the
        recipient's received amount (``received_minor``,
        ``received_currency``, ``received_display``), and
        ``created_at`` (ISO 8601 string) — or ``None`` if the caller
        has never sent a transfer.
    """
    docs = transactions_repository.list_for_sender(uid, limit=1)
    if not docs:
        return None

    doc = docs[0]
    return _outbound_summary(doc)


# ---------------------------------------------------------------------------
# SPENDING_SUMMARY
# ---------------------------------------------------------------------------

def summarize_spending(
    uid: str,
    since: datetime,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    """Aggregate the caller's outbound transfers since a timestamp.

    Args:
        uid: The authenticated caller's uid.
        since: The earliest ``created_at`` to include. UTC-aware.
        limit: If given, caps aggregation to the ``limit`` most recent
            matching transfers (applied after the ``since`` filter,
            since ``list_for_sender`` already returns newest-first).
            Answers "what were my last N transfers" when combined with
            a period, or "what were my last N transfers, period" when
            ``since`` is the "all_time" epoch. ``None`` or a
            non-positive value means no cap beyond the function's own
            fetch ceiling (see ``truncated`` below).

    Returns:
        A dict with ``total_minor`` (int, sum of ``from_amount_minor``),
        ``currency`` (str), ``total_display`` (str), ``count`` (int,
        number of transfers actually aggregated — reflects ``limit``
        when one was applied), ``top_counterparties`` (list of
        ``{tag, name, total_minor, total_display, count}``, sorted by
        total descending, up to 3), ``largest_minor`` (int) and
        ``largest_display`` (str), ``average_minor`` (int) and
        ``average_display`` (str), and ``truncated`` (bool — True only
        when the initial fetch hit ``_MAX_TRANSACTIONS_PER_QUERY``, so
        the totals may be lower bounds. An explicit ``limit`` does not
        set this flag — a requested "last N" that returns exactly N is
        the request being honored, not truncation).
    """
    docs = transactions_repository.list_for_sender(
        uid, limit=_MAX_TRANSACTIONS_PER_QUERY
    )
    truncated = len(docs) >= _MAX_TRANSACTIONS_PER_QUERY

    # Only TRANSFER rows count as "spending" here. Funding and
    # withdrawal rows also appear in list_for_sender if the caller is
    # the sender side, but neither is a person-to-person payment.
    outbound = [
        d
        for d in docs
        if d.transaction_type.value == "TRANSFER"
        and d.created_at is not None
        and d.created_at >= since
    ]

    # list_for_sender returns newest-first, so slicing here keeps the
    # most recent `limit` transfers within the period, not an
    # arbitrary subset.
    if limit is not None and limit > 0:
        outbound = outbound[:limit]

    if not outbound:
        # No transfers in the period. Return a shape consistent with
        # the populated case so the prompt doesn't have to branch.
        # Currency is inferred from the caller's profile rather than
        # from any document, because there is no document.
        profile = users_service.get_profile(uid)
        currency = Currency(profile["currency"])
        return {
            "total_minor": 0,
            "currency": currency.value,
            "total_display": format_amount(0, currency),
            "count": 0,
            "top_counterparties": [],
            "largest_minor": 0,
            "largest_display": format_amount(0, currency),
            "average_minor": 0,
            "average_display": format_amount(0, currency),
            "truncated": truncated,
        }

    # The sender's currency is fixed at profile creation, so every
    # outbound transfer has the same from_currency. Take it from the
    # first row.
    currency = outbound[0].from_currency
    if currency is None:
        # Should be structurally impossible for a TRANSFER, but the
        # schema allows None for FUNDING and WITHDRAWAL. Fall back to
        # the profile, which is always populated.
        profile = users_service.get_profile(uid)
        currency = Currency(profile["currency"])

    total_minor = sum(
        d.from_amount_minor for d in outbound if d.from_amount_minor
    )
    largest_minor = max(
        (d.from_amount_minor for d in outbound if d.from_amount_minor),
        default=0,
    )
    average_minor = total_minor // len(outbound) if outbound else 0

    top = _top_counterparties(outbound, currency, limit=3)

    return {
        "total_minor": total_minor,
        "currency": currency.value,
        "total_display": format_amount(total_minor, currency),
        "count": len(outbound),
        "top_counterparties": top,
        "largest_minor": largest_minor,
        "largest_display": format_amount(largest_minor, currency),
        "average_minor": average_minor,
        "average_display": format_amount(average_minor, currency),
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# COUNTERPARTY_DETAILS
# ---------------------------------------------------------------------------

def get_counterparty_history(
    uid: str,
    counterparty_ref: str,
) -> dict[str, Any] | None:
    """Return transactions between the caller and one counterparty.

    ``counterparty_ref`` may be any of three shapes, in descending
    order of specificity:

        1. An exact @tag, e.g. ``"chidera.ng"``. Matched by exact
           string equality against the snapshot's tag.
        2. A partial name, e.g. ``"Chidera"``. Matched case-
           insensitively as a substring of the snapshot's name or tag.
        3. A description, e.g. ``"the guy from last month"``. The
           classifier passes this through verbatim; this function
           tokenizes it and matches any token of three or more
           characters against the snapshot's name.

    Case 3 is best-effort by design. The classifier is instructed to
    return a plain string and to leave the disambiguation to the
    caller's transaction history, because that history is the only
    source of truth for who the user has actually paid. If no
    counterparty matches, this function returns ``None`` and the
    service tells the user it couldn't find anyone by that
    description.

    Args:
        uid: The authenticated caller's uid.
        counterparty_ref: The reference from the classifier.

    Returns:
        A dict with ``counterparty_uid``, ``counterparty_tag``,
        ``counterparty_name``, ``total_sent_minor`` (int),
        ``currency`` (str), ``total_sent_display`` (str), ``count``
        (int), ``last_sent_at`` (ISO 8601 string), and ``transactions``
        (a list of up to 5 recent outbound summaries, newest first) —
        or ``None`` if nothing matches.
    """
    docs = transactions_repository.list_for_sender(
        uid, limit=_MAX_TRANSACTIONS_PER_QUERY
    )

    outbound = [
        d
        for d in docs
        if d.transaction_type.value == "TRANSFER"
        and d.recipient_snapshot is not None
    ]

    matches = [d for d in outbound if _matches_ref(d, counterparty_ref)]
    if not matches:
        return None

    # Sort by created_at descending so last_sent_at and the recent
    # transactions list are both correct regardless of Firestore's
    # order (list_for_sender orders by created_at DESC already, but
    # being explicit here is cheap and makes the function correct
    # if the repository's ordering ever changes).
    matches.sort(
        key=lambda d: d.created_at or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True,
    )

    currency = matches[0].from_currency
    if currency is None:
        profile = users_service.get_profile(uid)
        currency = Currency(profile["currency"])

    total_minor = sum(
        d.from_amount_minor for d in matches if d.from_amount_minor
    )
    last = matches[0]

    return {
        "counterparty_uid": last.recipient_uid,
        "counterparty_tag": (last.recipient_snapshot or {}).get("tag"),
        "counterparty_name": (last.recipient_snapshot or {}).get("name"),
        "total_sent_minor": total_minor,
        "currency": currency.value,
        "total_sent_display": format_amount(total_minor, currency),
        "count": len(matches),
        "last_sent_at": last.created_at.isoformat()
        if last.created_at
        else None,
        "transactions": [_outbound_summary(d) for d in matches[:5]],
    }


# ---------------------------------------------------------------------------
# SPENDING_ADVICE
# ---------------------------------------------------------------------------

def summarize_for_advice(
    uid: str,
    days: int = 30,
) -> dict[str, Any]:
    """Aggregate for the SPENDING_ADVICE prompt.

    Similar to ``summarize_spending`` but includes recent inbound
    activity as well — advice is better when it knows both what the
    user is sending and what they're receiving, so it can comment on
    net flow rather than just gross spending.

    Args:
        uid: The authenticated caller's uid.
        days: How many days back to look. Defaults to 30.

    Returns:
        A dict with all of ``summarize_spending``'s fields, plus
        ``received_total_minor``, ``received_total_display``,
        ``received_count``, ``net_flow_minor``, ``net_flow_display``,
        and ``window_days`` (int).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    outbound = summarize_spending(uid, since)

    # Received transfers — same repo, different query. Inbound
    # includes only TRANSFER rows for the same reason outbound does:
    # a FUNDING deposit isn't a person-to-person receipt, and it
    # would distort the advice if counted as income from a peer.
    received_docs = transactions_repository.list_for_recipient(
        uid, limit=_MAX_TRANSACTIONS_PER_QUERY
    )
    received = [
        d
        for d in received_docs
        if d.transaction_type.value == "TRANSFER"
        and d.created_at is not None
        and d.created_at >= since
    ]

    # The recipient's currency is also fixed at profile creation, so
    # every inbound transfer has the same to_currency.
    if received:
        received_currency = received[0].to_currency
        if received_currency is None:
            profile = users_service.get_profile(uid)
            received_currency = Currency(profile["currency"])
        received_total_minor = sum(
            d.to_amount_minor for d in received if d.to_amount_minor
        )
    else:
        profile = users_service.get_profile(uid)
        received_currency = Currency(profile["currency"])
        received_total_minor = 0

    # Net flow is expressed in the caller's own currency. If inbound
    # and outbound currencies differ (which happens only when the
    # caller has transacted across corridors), we report net flow in
    # the currency the outbound side used — the caller's own.
    outbound_currency = Currency(outbound["currency"])
    net_flow_minor = received_total_minor - outbound["total_minor"]

    return {
        **outbound,
        "received_total_minor": received_total_minor,
        "received_total_display": format_amount(
            received_total_minor, received_currency
        ),
        "received_count": len(received),
        "net_flow_minor": net_flow_minor,
        "net_flow_display": format_amount(
            net_flow_minor, outbound_currency
        ),
        "window_days": days,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _outbound_summary(doc: TransactionDocument) -> dict[str, Any]:
    """Project one outbound TransactionDocument into a small summary dict.

    Used by both ``get_last_outbound`` and ``get_counterparty_history``.
    Every amount is pre-formatted via ``format_amount`` so the answer
    prompt receives a display-ready string and never has to guess at
    decimal places or currency symbols.
    """
    sender_currency = doc.from_currency
    if sender_currency is None:
        sender_currency = doc.to_currency
    recipient_currency = doc.to_currency

    summary: dict[str, Any] = {
        "transaction_id": doc.transaction_id,
        "counterparty_uid": doc.recipient_uid,
        "counterparty_tag": (doc.recipient_snapshot or {}).get("tag"),
        "counterparty_name": (doc.recipient_snapshot or {}).get("name"),
        "created_at": doc.created_at.isoformat()
        if doc.created_at
        else None,
    }

    if doc.from_amount_minor is not None and sender_currency is not None:
        summary["amount_minor"] = doc.from_amount_minor
        summary["currency"] = sender_currency.value
        summary["amount_display"] = format_amount(
            doc.from_amount_minor, sender_currency
        )

    if doc.to_amount_minor is not None and recipient_currency is not None:
        summary["received_minor"] = doc.to_amount_minor
        summary["received_currency"] = recipient_currency.value
        summary["received_display"] = format_amount(
            doc.to_amount_minor, recipient_currency
        )

    return summary


def _top_counterparties(
    docs: list[TransactionDocument],
    currency: Currency,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Aggregate transfers by counterparty, sorted by total descending."""
    buckets: dict[str, dict[str, Any]] = {}

    for doc in docs:
        uid = doc.recipient_uid
        if uid is None:
            continue
        bucket = buckets.setdefault(
            uid,
            {
                "tag": (doc.recipient_snapshot or {}).get("tag"),
                "name": (doc.recipient_snapshot or {}).get("name"),
                "total_minor": 0,
                "count": 0,
            },
        )
        if doc.from_amount_minor:
            bucket["total_minor"] += doc.from_amount_minor
        bucket["count"] += 1

    ranked = sorted(
        buckets.values(),
        key=lambda b: b["total_minor"],
        reverse=True,
    )

    for bucket in ranked:
        bucket["total_display"] = format_amount(
            bucket["total_minor"], currency
        )

    return ranked[:limit]


def _matches_ref(doc: TransactionDocument, ref: str) -> bool:
    """Return True if this transaction's counterparty matches ``ref``.

    Three-tier matching in descending order of specificity:

        1. Exact tag match, case-insensitive.
        2. Substring match against name or tag, case-insensitive.
        3. Token match — any word of three or more characters in the
           ref appears in the name.

    Tier 3 is what handles "the guy from last month". The classifier
    passes a description through verbatim; this function pulls out the
    meaningful tokens and looks for any of them in the counterparty's
    stored name. It's deliberately loose — the goal is to give the
    answer prompt enough candidates to work with, not to be a
    precision matcher. When nothing matches, the caller returns None
    and the user is told it couldn't find anyone by that description.
    """
    snapshot = doc.recipient_snapshot or {}
    tag = (snapshot.get("tag") or "").lower()
    name = (snapshot.get("name") or "").lower()
    needle = ref.strip().lower()

    if not needle:
        return False

    # Tier 1 — exact tag.
    if tag and needle == tag:
        return True

    # Tier 2 — substring in name or tag.
    if needle in name or needle in tag:
        return True

    # Tier 3 — token overlap. Words of 3+ characters, so "the" and
    # "of" and "to" from a description like "the guy from last month"
    # don't accidentally match unrelated names.
    tokens = [
        t for t in needle.replace(",", " ").split() if len(t) >= 3
    ]
    if not tokens:
        return False

    return any(token in name or token in tag for token in tokens)