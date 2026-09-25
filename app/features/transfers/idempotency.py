"""Transfer idempotency.

Guards against a transfer being executed twice when the client retries
— a network blip, a user double-tapping the confirm button, a mobile
app reconnecting. The client generates one idempotency key per transfer
attempt and reuses it on every retry of that same attempt. The ledger
enforces this at the write layer (step 0 of the Firestore transaction),
so this module's role is narrower: validate the shape of the key the
client sends, and give the service a way to look up the result of a
previously-committed transfer by its key.

Why the ledger is the authoritative enforcement point and this module
isn't:

    The ledger's transaction body already reads
    ``idempotency_keys/{key}`` inside the atomic commit. Two concurrent
    requests with the same key cannot both succeed — the second sees
    the first's write and returns the cached transaction. That is the
    only place where a genuine race can be resolved correctly, because
    it is the only place with a lock on the key.

    This module exists for two other reasons:

        1. To validate the key's format before any Firestore read
           happens. A malformed key is a caller bug, not a lookup miss.
        2. To provide a read-only lookup for the service to call when
           it wants to short-circuit a retry without going through the
           full ledger transaction (an optimization, not a correctness
           requirement).

This module contains no business logic. The decision of what to do
with a duplicate — return the original result, reject the request,
something else — belongs to the service layer.
"""

import logging
import re
from typing import Any

from app.core.constants import ErrorCode, FirestoreCollection
from app.core.exceptions import NovaBanqError
from app.infra.firestore import document

logger = logging.getLogger(__name__)


# Client-generated keys. ULID-style (26 chars, Crockford base32) and
# UUIDv4 are the two formats clients will most commonly produce. Rather
# than pick one, we accept a broad but safe shape: alphanumeric plus
# hyphen and underscore, 8 to 128 characters. That rejects obvious
# garbage (whitespace, slashes, control characters, oversized strings)
# while accepting anything a reasonable client would generate.
_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,128}$")


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class InvalidIdempotencyKeyError(NovaBanqError):
    """Raised when the client's idempotency key has a malformed shape.

    Distinct from ``DUPLICATE_TRANSFER``: this means the key itself is
    not something we would ever accept, not that a valid key was
    already used. The frontend should reject this before sending,
    since it can validate the same pattern.
    """

    status_code = 422
    code = ErrorCode.VALIDATION_ERROR
    message = "The idempotency key is malformed."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_key(idempotency_key: str) -> None:
    """Validate an idempotency key's shape.

    Called by the service before any Firestore read or write. A
    malformed key fails here, not at the ledger boundary — the error
    is clearer and no Firestore call is wasted on input that could
    never match anything.

    Args:
        idempotency_key: The key the client sent in the request body.

    Raises:
        InvalidIdempotencyKeyError: If the key does not match the
            accepted pattern (8–128 characters, alphanumeric plus
            ``-`` and ``_``).
    """
    if not isinstance(idempotency_key, str):
        raise InvalidIdempotencyKeyError()

    if not _KEY_PATTERN.fullmatch(idempotency_key):
        # idempotency_key is guaranteed str here — the isinstance
        # check above already returned on anything else.
        logger.warning(
            "Client sent a malformed idempotency key (length=%d).",
            len(idempotency_key),
        )
        raise InvalidIdempotencyKeyError()


def lookup_transaction_id(
    idempotency_key: str,
) -> str | None:
    """Return the transaction id previously written for this key.

    Read-only. Used by the service to short-circuit a retry: if the
    key already maps to a transaction, the service can return that
    transaction's result directly instead of paying for a full ledger
    round trip.

    This is not the enforcement point. The ledger's transaction body
    reads the same collection inside its atomic commit — that read is
    what actually prevents a race. This function can race harmlessly:
    two concurrent calls can both see None, both proceed to the ledger,
    and the ledger will still reject the second one correctly.

    Args:
        idempotency_key: A validated key (see ``validate_key``).

    Returns:
        The transaction id the key maps to, or ``None`` if the key has
        never been used.

    Raises:
        InvalidIdempotencyKeyError: If the key is malformed. Callers
            should call ``validate_key`` first so this never fires
            from well-behaved code, but the check is repeated here so
            the function is safe to call in isolation.
    """
    validate_key(idempotency_key)

    try:
        snapshot = document(
            FirestoreCollection.IDEMPOTENCY_KEYS,
            idempotency_key,
        ).get()
    except Exception:  # noqa: BLE001 — translate any client error
        # Deliberately not raising here. A failed read is not a failure
        # of the transfer — the ledger will do the authoritative read
        # inside its transaction and fail correctly if the key is
        # actually in use. Returning None means "proceed to the ledger
        # and let it decide".
        logger.exception(
            "Failed to read idempotency record; proceeding to ledger."
        )
        return None

    if not snapshot.exists:
        return None

    data: dict[str, Any] = snapshot.to_dict() or {}
    transaction_id = data.get("transaction_id")

    if not isinstance(transaction_id, str) or not transaction_id:
        # A record exists but is corrupt — a transaction id was never
        # written, or the wrong type got in. Log loudly and treat as
        # "not found" so the ledger gets a chance to resolve it.
        logger.error(
            "Idempotency record for key exists but holds no valid "
            "transaction_id; proceeding to ledger."
        )
        return None

    return transaction_id