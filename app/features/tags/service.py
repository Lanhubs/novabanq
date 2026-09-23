"""Tag service.

Business logic for tag reservation. Tags are globally unique identifiers
for NovaBanq users — any user in any supported country can pay a tag
from any supported rail. Uniqueness is enforced by the repository using
a Firestore transaction, so concurrent claims of the same tag cannot
both succeed.
"""

import logging

from app.core.exceptions import TagTakenError
from app.features.tags import repository

logger = logging.getLogger(__name__)


def is_available(tag: str) -> bool:
    """Return True if the tag is unclaimed."""
    return not repository.exists(tag)


def reserve(tag: str, uid: str) -> None:
    """Reserve a tag for a uid, raising if it is already taken.

    Delegates the atomic check-and-write to the repository. The
    repository guarantees that only one caller can win the race for a
    given tag.

    Args:
        tag: The normalized tag (lowercase, no leading '@').
        uid: The Firebase uid of the owner.

    Raises:
        TagTakenError: If the tag is already claimed by another uid.
    """
    if not repository.reserve_atomic(tag, uid):
        raise TagTakenError()