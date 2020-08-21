import json

from datetime import datetime

from sentry_sdk.envelope import Envelope, PayloadRef, Item
from sentry_sdk.utils import format_timestamp


def test_envelope(mini_sentry, relay_chain):
    relay = relay_chain()
    mini_sentry.project_configs[42] = relay.basic_project_config()

    envelope = Envelope()
    envelope.add_event({"message": "Hello, World!"})
    relay.send_envelope(42, envelope)

    event = mini_sentry.captured_events.get(timeout=1).get_event()

    assert event["logentry"] == {"formatted": "Hello, World!"}


def test_measure_items_envelope(mini_sentry, relay_chain):
    relay = relay_chain()
    mini_sentry.project_configs[42] = relay.basic_project_config()

    measure_item = {"measurements": {"foo": 420.69, "BAR": 2020}}

    transaction_item = {
        "event_id": "d2132d31b39445f1938d7e21b6bf0ec4",
        "type": "transaction",
        "transaction": "/organizations/:orgId/performance/:eventSlug/",
        "start_timestamp": 1597976392.6542819,
        "timestamp": 1597976400.6189718,
        "contexts": {
            "trace": {
                "trace_id": "4C79F60C11214EB38604F4AE0781BFB2",
                "span_id": "FA90FDEAD5F74052",
                "type": "trace",
            }
        },
        "spans": [
            {
                "description": "<OrganizationContext>",
                "op": "react.mount",
                "parent_span_id": "8f5a2b8768cafb4e",
                "span_id": "bd429c44b67a3eb4",
                "start_timestamp": 1597976393.4619668,
                "timestamp": 1597976393.4718769,
                "trace_id": "ff62a8b040f340bda5d830223def1d81",
            }
        ],
    }

    envelope = Envelope(
        headers={
            "event_id": transaction_item["event_id"],
            "sent_at": format_timestamp(datetime.utcnow()),
        }
    )
    envelope.add_item(
        Item(payload=PayloadRef(json=transaction_item), type="transaction")
    )
    envelope.add_item(Item(payload=PayloadRef(json=measure_item), type="measures"))

    relay.send_envelope(42, envelope)

    envelope = mini_sentry.captured_events.get(timeout=1)

    def get_transaction_item(item):
        if item.headers.get("type") == "transaction" and item.payload is not None:
            return json.loads(item.payload.get_bytes())
        return None

    def get_transaction(envelope):
        for item in envelope.items:
            event = get_transaction_item(item)
            if event is not None:
                return event
        return None

    event = get_transaction(envelope)

    assert event["transaction"] == "/organizations/:orgId/performance/:eventSlug/"
    assert "trace" in event["contexts"]
    assert "measures" in event["contexts"]
    assert event["contexts"]["measures"]["measurements"]["foo"] == 420.69
    # expect the key "BAR" to be lowercased as part of the normalization
    assert event["contexts"]["measures"]["measurements"]["bar"] == 2020


def test_measure_strip_envelope(mini_sentry, relay_chain):
    relay = relay_chain()
    mini_sentry.project_configs[42] = relay.basic_project_config()

    envelope = Envelope()
    envelope.add_event(
        {
            "message": "Hello, World!",
            "contexts": {"measures": {"measurements": {"lcp": 420.90}}},
        }
    )
    relay.send_envelope(42, envelope)

    event = mini_sentry.captured_events.get(timeout=1).get_event()

    assert event["logentry"] == {"formatted": "Hello, World!"}

    # expect measures context object to be stripped out since it's attached to a non-transaction event
    assert "measures" not in event["contexts"], event
