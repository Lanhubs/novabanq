import logging
from functools import lru_cache

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _initialize_firebase() -> firebase_admin.App:
    """Initialize the Firebase Admin SDK exactly once."""
    if firebase_admin._apps:
        return firebase_admin.get_app()

    service_account = settings.load_firebase_credentials()
    cred = credentials.Certificate(service_account)
    app = firebase_admin.initialize_app(cred)

    logger.info(
        "Firebase Admin SDK initialized for project '%s' (env=%s).",
        app.project_id,
        settings.app_env,
    )
    return app


def get_firebase_app() -> firebase_admin.App:
    """Return the initialized Firebase Admin app."""
    return _initialize_firebase()


@lru_cache(maxsize=1)
def get_firestore_client() -> FirestoreClient:
    """Return a singleton Firestore client bound to the Admin app."""
    _initialize_firebase()
    return firestore.client()