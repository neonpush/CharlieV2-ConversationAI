import logging
from app.core.logging import with_context


def test_with_context_prefixes_message(caplog):
    logger = logging.getLogger("testlogger")
    caplog.set_level(logging.INFO)

    log = with_context(logger, lead_id=123, call_sid="CA123")
    log.info("Hello")

    records = [r.message for r in caplog.records]
    assert any("[lead_id=123 call_sid=CA123] Hello" in msg for msg in records)


def test_with_context_merges_extra(caplog):
    logger = logging.getLogger("testlogger")
    caplog.set_level(logging.INFO)

    log = with_context(logger, lead_id=999)
    log.info("Hi", extra={"phase": "NEW"})

    records = [r.message for r in caplog.records]
    assert any("[lead_id=999 phase=NEW] Hi" in msg for msg in records)


