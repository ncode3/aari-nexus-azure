import os
import subprocess
import tempfile
import uuid
from decimal import Decimal

import httpx
import pytest
from minio import Minio
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.ingestion.adapters import CsvAdapter, JsonAdapter, PdfAdapter, XlsxAdapter
from app.ingestion.pipeline import IngestionPipeline, IngestionRequest
from app.ingestion.specialized import import_financial_rows
from app.models.entities import (
    AuditEvents,
    FinancialAccounts,
    Transactions,
)
from app.services.object_store import MinioObjectStore

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION") != "1", reason="requires the disposable Compose stack"
)


def test_database_migration_and_pgvector() -> None:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT 1")) == 1
        assert connection.scalar(
            text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
        ) == 1
        assert connection.scalar(
            text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        ) >= 27


def test_api_health_validation_and_pagination() -> None:
    base_url = os.environ["API_INTERNAL_URL"]
    health = httpx.get(f"{base_url}/health", timeout=10)
    assert health.status_code == 200
    assert health.headers["X-Request-ID"]
    invalid = httpx.get(f"{base_url}/api/v1/students", params={"limit": 0}, timeout=10)
    assert invalid.status_code == 422
    page = httpx.get(
        f"{base_url}/api/v1/students", params={"offset": 0, "limit": 10}, timeout=10
    )
    assert page.status_code == 200
    assert page.json()["limit"] == 10


def test_minio_is_private_and_writable() -> None:
    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    buckets = {bucket.name for bucket in client.list_buckets()}
    assert settings.minio_documents_bucket in buckets
    assert settings.minio_rejected_bucket in buckets
    MinioObjectStore().put(
        settings.minio_documents_bucket,
        "integration/health.txt",
        b"ok",
        "text/plain",
    )
    assert MinioObjectStore().exists(
        settings.minio_documents_bucket, "integration/health.txt"
    )


def test_document_ingestion_is_idempotent_and_audited() -> None:
    content = f"name,hours\nstudent-{uuid.uuid4()},8\n".encode()
    with SessionLocal() as session:
        pipeline = IngestionPipeline(
            session,
            MinioObjectStore(),
            [CsvAdapter(), XlsxAdapter(), JsonAdapter(), PdfAdapter()],
        )
        request = IngestionRequest(
            filename="student-progress.csv",
            content_type="text/csv",
            content=content,
            source_system="integration_test",
            source_identifier=str(uuid.uuid4()),
        )
        first = pipeline.ingest(request)
        second = pipeline.ingest(request)
        assert not first.duplicate
        assert second.duplicate
        assert first.document_id == second.document_id
        assert session.scalar(
            select(AuditEvents).where(
                AuditEvents.entity_id == first.document_id,
                AuditEvents.action == "document.create",
            )
        )


def test_financial_import_deduplicates_and_uses_decimal() -> None:
    with SessionLocal.begin() as session:
        account = FinancialAccounts(
            name=f"Integration {uuid.uuid4()}",
            account_type="checking",
            masked_identifier=f"TEST-{uuid.uuid4()}",
        )
        session.add(account)
        session.flush()
        rows = [{"date": "2026-07-31", "amount": "125.25", "description": "Equipment"}]
        assert import_financial_rows(
            session, rows, account=account, import_batch_id=str(uuid.uuid4())
        ) == (1, 0)
        assert import_financial_rows(
            session, rows, account=account, import_batch_id=str(uuid.uuid4())
        ) == (0, 1)
        transaction = session.scalar(
            select(Transactions).where(Transactions.financial_account_id == account.id)
        )
        assert transaction and transaction.amount == Decimal("125.25")


def test_readonly_role_cannot_mutate() -> None:
    readonly = create_engine(get_settings().readonly_database_url)
    with readonly.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM cohorts")) >= 0
        with pytest.raises(SQLAlchemyError):
            connection.execute(
                text(
                    "INSERT INTO cohorts(id, slug, name, created_at, updated_at, metadata) "
                    "VALUES (gen_random_uuid(), 'forbidden', 'Forbidden', now(), now(), '{}')"
                )
            )


def test_postgresql_backup_and_restore_round_trip() -> None:
    settings = get_settings()
    assert settings.database_admin_url
    admin_url = make_url(settings.database_admin_url)
    maintenance_url = admin_url.set(database="postgres")
    restore_database = f"aari_restore_{uuid.uuid4().hex[:10]}"
    native_source = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    native_target = str(admin_url.set(database=restore_database)).replace(
        "postgresql+psycopg://", "postgresql://"
    )
    admin_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        with tempfile.TemporaryDirectory() as directory:
            dump = f"{directory}/aari.dump"
            subprocess.run(  # noqa: S603
                [
                    "/usr/bin/pg_dump",
                    "--format=custom",
                    "--no-owner",
                    f"--file={dump}",
                    native_source,
                ],
                check=True,
            )
            with admin_engine.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{restore_database}"'))
            subprocess.run(  # noqa: S603
                ["/usr/bin/pg_restore", "--no-owner", f"--dbname={native_target}", dump],
                check=True,
            )
            restored_engine = create_engine(admin_url.set(database=restore_database))
            with restored_engine.connect() as connection:
                assert connection.scalar(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = 'public'"
                    )
                ) >= 27
            restored_engine.dispose()
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name"
                ),
                {"name": restore_database},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{restore_database}"'))
        admin_engine.dispose()
