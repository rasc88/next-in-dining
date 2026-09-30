from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.db import engine
from app.telemetry import setup_telemetry


def test_setup_telemetry_is_a_noop_without_an_otlp_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    app = FastAPI()
    setup_telemetry(app, engine)
    assert not isinstance(trace.get_tracer_provider(), TracerProvider)
    assert app.user_middleware == []
