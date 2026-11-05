"""Guard regressions without starting Docker or touching original data."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from scripts import verify_langflow_migration as migration


@pytest.fixture(autouse=True)
def ci(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")


@pytest.mark.parametrize(
    "name",
    [
        "ai-review-console",
        "arc-migration-12344-2-baseline",
        "arc-migration-12345-1-baseline",
        "arc-migration-12345-2-original",
    ],
)
def test_reject_foreign_namespace(name):
    with pytest.raises(ValueError):
        migration.require_ci(name)


def test_refuse_local_operations(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS")
    with pytest.raises(ValueError, match="GitHub Actions"):
        migration.require_ci("arc-migration-12345-2-baseline")


@pytest.mark.parametrize("name", ["../original.sqlite", "/app/documents/a", "a/../b", "a//b", ""])
def test_reject_traversal(name):
    with pytest.raises(ValueError):
        migration.safe_relative(name)


def test_checkpoint_integrity_and_tamper(tmp_path):
    data = b"synthetic bytes"
    source = {
        "source_project": "arc-migration-12345-2-baseline",
        "files": migration.file_manifest({"documents/a.txt": base64.b64encode(data).decode()}),
        "dumps": {
            db: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
            for db in migration.DBS
        },
    }
    (tmp_path / "checkpoint.json").write_bytes(migration.bounded_json(source))
    (tmp_path / "files/documents").mkdir(parents=True)
    (tmp_path / "files/documents/a.txt").write_bytes(data)
    for db in migration.DBS:
        (tmp_path / f"{db}.sql").write_bytes(data)
    assert migration.load_checkpoint(tmp_path)[0] == source
    (tmp_path / "review_console.sql").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        migration.load_checkpoint(tmp_path)


def test_no_overwrite(tmp_path):
    target = tmp_path / "existing"
    target.write_bytes(b"preserve")
    with pytest.raises(FileExistsError):
        migration.write_new(target, b"replacement")
    assert target.read_bytes() == b"preserve"


def test_json_budget():
    with pytest.raises(ValueError, match="size bound"):
        migration.bounded_json({"large": "x" * migration.MAX_JSON})


def test_restore_refuses_nonempty_db_before_files_or_sql_write(monkeypatch, tmp_path):
    stack = migration.Stack("arc-migration-12345-2-upgrade", Path("unused"))
    monkeypatch.setattr(migration, "load_checkpoint", lambda _: ({}, {}))
    monkeypatch.setattr(stack, "tables", lambda db: ["existing_business_table"])
    monkeypatch.setattr(stack, "run", lambda *a, **k: pytest.fail("No data command allowed"))
    with pytest.raises(ValueError, match="database is not empty"):
        migration.restore(stack, tmp_path)


def test_restore_refuses_baseline():
    stack = migration.Stack("arc-migration-12345-2-baseline", Path("unused"))
    with pytest.raises(ValueError, match="upgrade or rollback"):
        migration.restore(stack, Path("unused"))


def test_verify_rejects_changed_records_before_business_calls(monkeypatch, tmp_path):
    stack = migration.Stack("arc-migration-12345-2-upgrade", Path("unused"))
    monkeypatch.setattr(
        migration,
        "load_checkpoint",
        lambda _: ({"fingerprint": {"review_console": "original"}}, {}),
    )
    monkeypatch.setattr(stack, "fingerprint", lambda: {"review_console": "changed"})
    monkeypatch.setattr(stack, "bind_runtime", lambda _: None)
    monkeypatch.setattr(stack, "run", lambda *a, **k: pytest.fail("No repair/validation allowed"))
    with pytest.raises(ValueError, match="records changed"):
        migration.verify(stack, tmp_path, "http://unused")


def test_output_limit_enforced_by_child_file_limit():
    stack = migration.Stack("arc-migration-12345-2-baseline", Path("unused"))
    import sys

    with pytest.raises(RuntimeError, match="command failed"):
        stack.run([sys.executable, "-c", "import sys;sys.stdout.write('x'*10000)"], limit=100)


def test_fingerprint_utc_query_and_no_password_in_identity(monkeypatch):
    stack = migration.Stack("arc-migration-12345-2-baseline", Path("unused"))
    stack.pg = "fake"
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs["data"]))
        return b"[]"

    monkeypatch.setattr(stack, "run", run)
    stack.sql("langflow", 'SELECT id,username FROM "user";')
    assert calls[0][1].startswith(b"SET TIME ZONE 'UTC';")
    assert not any("password" in str(part).lower() for part in calls[0][0])


@pytest.mark.parametrize("attack", ["foreign-label", "host-driver", "actual-bind", "actual-volume"])
def test_actual_docker_ownership_checked_before_any_data_operation(monkeypatch, attack):
    from types import SimpleNamespace

    project = "arc-migration-12345-2-upgrade"
    stack = migration.Stack(project, Path("unused"))
    config = {
        "volumes": {key: {"name": f"{project}_{key}"} for key in migration.VOLUMES},
        "services": {"postgres": {"volumes": []}},
    }
    monkeypatch.setattr(migration.shutil, "disk_usage", lambda _: SimpleNamespace(free=6 * 1024**3))

    def run(args, **kwargs):
        if args[-3:] == ["config", "--format", "json"]:
            return json.dumps(config).encode()
        if args[-3:] == ["ps", "-a", "-q"]:
            return b"container-id"
        pytest.fail("No data operations before ownership checks")

    def inspect(kind, name):
        if kind == "volume":
            key = name.removeprefix(project + "_")
            return {
                "Driver": "local",
                "Options": {"device": "/original-data"} if attack == "host-driver" else {},
                "Labels": {
                    "com.docker.compose.project": "original"
                    if attack == "foreign-label"
                    else project,
                    "com.docker.compose.volume": key,
                },
            }
        mount = {"Type": "bind", "Source": "/original-data", "RW": False}
        if attack == "actual-volume":
            mount = {"Type": "volume", "Name": "original_postgres-data"}
        return {
            "Config": {
                "Labels": {
                    "com.docker.compose.project": project,
                    "com.docker.compose.service": "postgres",
                }
            },
            "State": {"Running": True},
            "Mounts": [mount],
        }

    monkeypatch.setattr(stack, "run", run)
    monkeypatch.setattr(stack, "inspect", inspect)
    with pytest.raises(ValueError):
        stack.check()


def test_runtime_urls_and_database_are_bound_to_actual_target(monkeypatch):
    import copy

    stack = migration.Stack("arc-migration-12345-2-upgrade", Path("unused"))
    network = "arc-migration-12345-2-upgrade_backend"
    template = {
        "NetworkSettings": {
            "Networks": {network: {"Aliases": ["postgres", "langflow"]}},
            "Ports": {},
        },
        "Config": {"Env": []},
    }
    stack.running = {
        name: copy.deepcopy(template) for name in ("postgres", "langflow", "api", "worker")
    }
    stack.running["langflow"]["Config"]["Env"] = [
        "LANGFLOW_DATABASE_URL=postgresql://review:secret@postgres:5432/langflow"
    ]
    for name in ("api", "worker"):
        stack.running[name]["Config"]["Env"] = [
            "DATABASE_URL=postgresql+psycopg://review:secret@postgres:5432/review_console",
            "LANGFLOW_URL=http://langflow:7860",
        ]
    stack.running["langflow"]["NetworkSettings"]["Ports"] = {
        "7860/tcp": [{"HostIp": "127.0.0.1", "HostPort": "17860"}]
    }
    stack.running["api"]["NetworkSettings"]["Ports"] = {
        "8000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18000"}]
    }
    monkeypatch.setenv("LANGFLOW_URL", "http://localhost:17860")
    monkeypatch.setattr(
        stack, "inspect", lambda *args: {"Labels": {"com.docker.compose.project": stack.project}}
    )
    stack.bind_runtime("http://127.0.0.1:18000")
    with pytest.raises(ValueError, match="API URL"):
        stack.bind_runtime("http://127.0.0.1:28000")
    monkeypatch.setenv("LANGFLOW_URL", "http://localhost:27860")
    with pytest.raises(ValueError, match="Langflow URL"):
        stack.bind_runtime("http://127.0.0.1:18000")
    monkeypatch.setenv("LANGFLOW_URL", "http://localhost:17860")
    stack.running["worker"]["Config"]["Env"][0] = (
        "DATABASE_URL=postgresql://review:secret@original:5432/review_console"
    )
    with pytest.raises(ValueError, match="outside target"):
        stack.bind_runtime("http://127.0.0.1:18000")


def validation_fixture():
    cases, rows, files = (
        [],
        {
            table: []
            for table in (
                "review_cases",
                "document_versions",
                "decisions",
                "workflow_jobs",
                "report_artifacts",
            )
        },
        {},
    )
    for index in range(5):
        case_id, version = f"case-{index}", f"doc-{index}"
        item = {
            "case_id": case_id,
            "document_version_id": version,
            "source_sha256": f"hash-{index}",
        }
        rows["review_cases"].append(
            {
                "id": case_id,
                "current_document_version_id": version,
                "document_hash": item["source_sha256"],
            }
        )
        rows["document_versions"].append(
            {
                "id": version,
                "case_id": case_id,
                "source_sha256": item["source_sha256"],
                "storage_key": version,
                "bytes": 1,
            }
        )
        files["documents/" + version] = {"sha256": item["source_sha256"], "bytes": 1}

        def add_job(
            suffix,
            kind="intake",
            state="succeeded",
            *,
            index=index,
            case_id=case_id,
            version=version,
        ):
            job = {
                "id": f"job-{index}-{suffix}",
                "case_id": case_id,
                "document_version_id": version,
                "kind": kind,
                "state": state,
                "langflow_job_id": f"lf-{index}-{suffix}",
                "decision_id": f"decision-{index}" if kind == "report" else None,
            }
            rows["workflow_jobs"].append(job)
            return {"job_id": job["id"], "langflow_job_id": job["langflow_job_id"]}

        intake = add_job("intake", state="failed" if index == 4 else "succeeded")
        if index < 3:
            report_job = add_job("report", "report")
            item.update(
                {
                    "intake_job_id": intake["job_id"],
                    "intake_langflow_job_id": intake["langflow_job_id"],
                    "report_langflow_job_id": report_job["langflow_job_id"],
                    "decision_id": f"decision-{index}",
                    "decision": "approved",
                    "reports": [],
                }
            )
            rows["decisions"].append(
                {
                    "id": item["decision_id"],
                    "case_id": case_id,
                    "document_version_id": version,
                    "decision": "approved",
                }
            )
            for fmt in ("pdf", "docx", "json"):
                report = {"format": fmt, "sha256": f"report-{index}-{fmt}", "bytes": 2}
                item["reports"].append(report)
                key = f"report-{index}-{fmt}"
                rows["report_artifacts"].append(
                    {
                        "id": key,
                        "case_id": case_id,
                        "document_version_id": version,
                        "decision_id": item["decision_id"],
                        "storage_key": key,
                        **report,
                    }
                )
                files["reports/" + key] = {"sha256": report["sha256"], "bytes": 2}
        elif index == 3:
            item.pop("document_version_id")
            item["intake_job"] = intake
        else:
            item["first_job"], item["retry_job"] = intake, add_job("retry", state="failed")
        cases.append(item)
    before = {"review_console": {"tables": {table: {"count": 0} for table in rows}}}
    after = {
        "review_console": {
            "tables": {table: {"count": len(items)} for table, items in rows.items()}
        }
    }
    return (
        {"cases": cases[:3], "markdown_intake": cases[3], "failure_retry": cases[4]},
        rows,
        files,
        before,
        after,
    )


@pytest.mark.parametrize(
    "attack", [None, "zero-increment", "foreign-case", "wrong-job", "wrong-report", "wrong-file"]
)
def test_validation_results_must_exist_in_target_sql_and_files(monkeypatch, attack):
    validation, rows, files, before, after = validation_fixture()
    stack = migration.Stack("arc-migration-12345-2-upgrade", Path("unused"))

    def sql(db, query):
        return next(items for table, items in rows.items() if f"FROM {table})" in query)

    monkeypatch.setattr(stack, "sql", sql)
    if attack == "zero-increment":
        after = before
    elif attack == "foreign-case":
        validation["cases"][0]["case_id"] = "other-project-case"
    elif attack == "wrong-job":
        rows["workflow_jobs"][0]["langflow_job_id"] = "other-project-lf-job"
    elif attack == "wrong-report":
        rows["report_artifacts"][0]["sha256"] = "other-report"
    elif attack == "wrong-file":
        files["documents/doc-0"]["sha256"] = "other-document"
    if attack:
        with pytest.raises(ValueError):
            migration.reconcile_validation(stack, validation, before, after, files)
    else:
        assert (
            migration.reconcile_validation(stack, validation, before, after, files)["review_cases"]
            == 5
        )
