"""Firestore access layer.

This module exposes the singleton Firestore client and a small set of
atomic-operation helpers. Feature repositories are the only consumers
of these utilities — routers and services never touch Firestore directly.
"""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore import Transaction
from google.cloud.firestore_v1.base_query import FieldFilter

from app.infra.firebase.client import get_firestore_client

logger = logging.getLogger(__name__)

T = TypeVar("T")


def get_db() -> FirestoreClient:
    """Return the singleton Firestore client.

    This is a thin wrapper over the Firebase Admin client accessor so
    that all Firestore access in the codebase flows through one function.
    """
    return get_firestore_client()


def run_atomic(operation: Callable[[Transaction], T]) -> T:
    """Execute a callable inside a Firestore transaction.

    Firestore transactions guarantee that all reads and writes inside
    the callable are serialized against concurrent transactions on the
    same documents. If the callable raises, all writes roll back.

    Note:
        ``run_transaction`` exists on the Firestore client at runtime but
        is not declared in the library's published type stubs. The scoped
        type ignore below is intentional and reflects that known gap.

    Args:
        operation: A callable that receives an active ``Transaction``
            object and returns a result. All reads and writes must use
            the provided transaction instance, not the raw client.

    Returns:
        Whatever the callable returns.
    """
    client = get_db()
    return client.run_transaction(operation)  # type: ignore[attr-defined]


def collection(name: str):
    """Return a top-level Firestore collection reference.

    Centralizing this call makes it trivial to add instrumentation
    (query timing, error tracking) later without touching repositories.
    """
    return get_db().collection(name)


def document(collection_name: str, document_id: str):
    """Return a Firestore document reference."""
    return get_db().collection(collection_name).document(document_id)


def where(field: str, operator: str, value: Any) -> FieldFilter:
    """Build a typed ``FieldFilter`` for queries.

    Firestore deprecated positional ``where(field, op, value)`` calls in
    favor of ``FieldFilter``. Wrapping it here keeps repositories free of
    the imported Firestore types.
    """
    return FieldFilter(field, operator, value)