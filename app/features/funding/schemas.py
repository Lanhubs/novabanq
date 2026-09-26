"""Funding schemas.

HTTP boundary models for the funding feature. Three things cross the
wire:

    * ``VirtualAccountResponse`` — the created or retrieved virtual
      account the user sees in the app. This is a response only; the
      creation endpoint takes no body.

    * ``WebhookPayload`` — the shape Flutterwave posts to the webhook
      endpoint. Modelled loosely because Flutterwave's payload is
      large and we only read a handful of fields. The provider is
      responsible for sending this shape; validation is minimal.

    * ``WebhookAck`` — the response the webhook returns. Flutterwave
      expects a 200 with a body; the content is not examined.

Money handling note:
    ``WebhookData.amount`` is typed ``Decimal``, not ``float``. A
    JSON number parsed as a float loses precision for common currency
    values (``19.99 * 100`` is ``1998.9999999999998`` on CPython),
    and the resulting one-kobo loss is silent. ``Decimal`` keeps the
    value exact, and the service converts to minor units with an
    explicit rounding mode rather than relying on float behaviour.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import Country, Currency


class VirtualAccountResponse(BaseModel):
    """A virtual account the user can fund from a bank transfer.

    Frozen — this is a read-only projection of a stored record, and
    the frontend never edits it.
    """

    model_config = ConfigDict(frozen=True)

    account_number: str = Field(
        ...,
        description="The account number the user enters in their bank app.",
        examples=["1546629060"],
    )
    bank_name: str = Field(
        ...,
        description="Bank name shown alongside the account number.",
        examples=["NovaBanq GH"],
    )
    account_name: str = Field(
        ...,
        description="Name on the account — the user's display name.",
        examples=["David Chashama Mensah"],
    )
    currency: Currency = Field(
        ...,
        description="The currency the account accepts.",
        examples=["GHS"],
    )
    country: Country = Field(
        ...,
        description="The country the account is issued in.",
        examples=["GH"],
    )
    provider_ref: str = Field(
        ...,
        description=(
            "The provider's reference for this account. Opaque; do "
            "not parse it. Present so the frontend can pass it back "
            "during deposit confirmation flows if needed."
        ),
        examples=["mock_abe0d933ac8d43adb75e9cc5905d1f01"],
    )
    created_at: datetime = Field(
        ...,
        description="When the virtual account was first created.",
    )


class WebhookCustomer(BaseModel):
    """The customer block of a Flutterwave webhook payload.

    Only the fields we read are modelled. Extra keys in the incoming
    JSON are ignored — see ``WebhookPayload`` for why.
    """

    model_config = ConfigDict(extra="ignore")

    email: str | None = Field(
        None,
        description="Customer email, if present in the payload.",
    )


class WebhookData(BaseModel):
    """The ``data`` block of a Flutterwave webhook payload.

    Only the fields the funding service reads are modelled.
    """

    model_config = ConfigDict(extra="ignore")

    id: str = Field(
        ...,
        description=(
            "Flutterwave's unique event identifier, normalized to a "
            "string. Used as the idempotency key so a replayed "
            "webhook does not credit the user twice. The validator "
            "below coerces numeric ids to ``str`` so that ``12345`` "
            "and ``\"12345\"`` — which Flutterwave has been observed "
            "to send interchangeably — hash to the same idempotency "
            "key rather than being treated as distinct events."
        ),
    )
    tx_ref: str = Field(
        ...,
        description=(
            "The transaction reference. In this integration it is the "
            "``provider_ref`` of the virtual account the money was "
            "sent to, which the funding service uses to look up the "
            "owning user."
        ),
    )
    amount: Decimal = Field(
        ...,
        description=(
            "The amount, in major units (e.g. 500.00 for GHS 500). "
            "Typed as ``Decimal`` so the service can convert to minor "
            "units exactly, without the silent precision loss a "
            "``float`` produces for values like ``19.99``."
        ),
    )
    currency: Currency = Field(
        ...,
        description="Currency the payment was made in.",
    )
    status: str = Field(
        ...,
        description=(
            "Flutterwave's event status. Only ``\"successful\"`` "
            "credits the ledger; other values are acknowledged and "
            "ignored."
        ),
    )
    customer: WebhookCustomer | None = Field(
        None,
        description="The paying customer, if present.",
    )

    @field_validator("id", mode="before")
    @classmethod
    def _coerce_id_to_str(cls, value: object) -> str:
        """Normalize the event id to a string.

        Flutterwave sends the event id as either an integer or a
        string depending on the event source. Both represent the same
        event, so both must produce the same idempotency key. Coercing
        here — at parse time, before any downstream code sees the
        value — guarantees that every consumer gets a ``str`` and no
        caller has to remember to call ``str()`` before using it as a
        dedup key.
        """
        return str(value)


class WebhookPayload(BaseModel):
    """The outer envelope of a Flutterwave webhook.

    ``extra="ignore"`` is deliberate: Flutterwave's payloads carry
    many additional fields we do not read, and being strict here would
    break every time they add one. The fields we care about are
    declared; everything else is discarded at parse time.
    """

    model_config = ConfigDict(extra="ignore")

    event: str = Field(
        ...,
        description=(
            "The event type. Only ``\"charge.completed\"`` is acted "
            "on; other event types are acknowledged and ignored."
        ),
        examples=["charge.completed"],
    )
    data: WebhookData = Field(
        ...,
        description="The event's data block.",
    )


class WebhookAck(BaseModel):
    """The response the webhook returns to Flutterwave.

    Flutterwave expects a 200 with a JSON body; the content is not
    examined. This model exists so the response shape is explicit and
    documented, rather than an unexplained inline dict in the router.
    """

    model_config = ConfigDict(frozen=True)

    status: str = Field(
        "ok",
        description="Always ``\"ok\"``. Any 200 stops Flutterwave retrying.",
    )
    credited: bool = Field(
        ...,
        description=(
            "True if the ledger was credited as a result of this "
            "call. False if the event was a duplicate, or was ignored "
            "because the status wasn't ``successful`` or the event "
            "type wasn't ``charge.completed``. Informational — the "
            "frontend never sees this field, only Flutterwave's "
            "retry logic cares, and it only cares that the status is "
            "200."
        ),
    )