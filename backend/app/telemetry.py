from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.engine import Engine

SERVICE_NAME = "next-in-dining"
APP_ENV = os.environ.get("APP_ENV", "local")
# The image tag CI bakes into the Docker image (see Dockerfile).
APP_VERSION = os.environ.get("APP_VERSION", "dev")

# Every app metric carries these, so dashboards and alerts can split by
# environment and deployed version regardless of how the backend maps
# resource attributes to labels.
METRIC_ATTRIBUTES = {"environment": APP_ENV, "version": APP_VERSION}


def _observe_waiting_parties(options: CallbackOptions) -> list[Observation]:
    # Imported here: app.store pulls in the DB layer, and this callback only
    # runs on export, long after startup.
    from app.store import store

    return [Observation(len(store.waiting_parties_ordered()), METRIC_ATTRIBUTES)]


# Created through the global (proxy) meter, so they're no-ops until
# setup_telemetry() installs a real MeterProvider.
_meter = metrics.get_meter(SERVICE_NAME)
parties_created = _meter.create_counter("waitlist.parties.created", description="Parties that joined the waitlist")
party_creation_failures = _meter.create_counter(
    "waitlist.party.creation.failures", description="Join requests that failed with a server error"
)
party_transitions = _meter.create_counter(
    "waitlist.party.transitions", description="Party state changes, by resulting state (to_state)"
)
_meter.create_observable_gauge(
    "waitlist.parties.waiting", callbacks=[_observe_waiting_parties], description="Parties currently waiting"
)


def setup_telemetry(app: FastAPI, engine: Engine) -> None:
    # Telemetry is opt-in: tests, `make run` and docker-compose leave the
    # endpoint unset, so nothing is exported and nothing is instrumented.
    # The OTLP exporters read the endpoint and auth headers themselves from
    # OTEL_EXPORTER_OTLP_ENDPOINT / OTEL_EXPORTER_OTLP_HEADERS.
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return

    resource = Resource.create(
        {
            "service.name": SERVICE_NAME,
            "deployment.environment": APP_ENV,
            "service.version": APP_VERSION,
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    set_logger_provider(logger_provider)
    log_handler = LoggingHandler(logger_provider=logger_provider)
    logging.getLogger().setLevel(logging.INFO)
    # uvicorn's loggers (unhandled exceptions, access log) don't propagate
    # to the root logger, so they need the handler attached directly.
    for name in ("", "uvicorn", "uvicorn.access"):
        logging.getLogger(name).addHandler(log_handler)

    FastAPIInstrumentor.instrument_app(app, excluded_urls="health")
    SQLAlchemyInstrumentor().instrument(engine=engine)
