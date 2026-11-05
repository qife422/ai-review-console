"""CI-only rehearsal of a pre-upgrade checkpoint into two fresh namespaces.

No original database is selected. Rollback means restoring the pre-upgrade
checkpoint into a third empty stack, never downgrading an upgraded database.
Dumps and unselected files remain ephemeral; this producer performs no cleanup.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap_langflow import require_langflow_version  # noqa: E402

from api.app.langflow_client import LangflowClient, canonical_hash, graph_hash  # noqa: E402

MAX_DUMP = 8 * 1024 * 1024
MAX_FILES = 32 * 1024 * 1024
MAX_JSON = 256 * 1024
DBS = ("langflow", "review_console")
VOLUMES = {"source-documents", "report-artifacts", "flow-config", "postgres-data"}
BASES = {"documents": "/app/documents", "reports": "/app/artifacts", "config": "/app/config"}


def safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError("Unsafe checkpoint file path")
    return value


def require_ci(project: str) -> str:
    run_id, attempt = os.getenv("GITHUB_RUN_ID", ""), os.getenv("GITHUB_RUN_ATTEMPT", "")
    if os.getenv("GITHUB_ACTIONS") != "true" or not re.fullmatch(r"[1-9][0-9]{0,19}", run_id):
        raise ValueError("Migration data operations are restricted to GitHub Actions")
    if not re.fullmatch(r"[1-9][0-9]{0,5}", attempt):
        raise ValueError("Invalid GitHub run attempt")
    prefix = f"arc-migration-{run_id}-{attempt}-"
    if project not in {prefix + phase for phase in ("baseline", "upgrade", "rollback")}:
        raise ValueError("Project is outside this run's isolated namespaces")
    return project.removeprefix(prefix)


def bounded_json(value: object, limit: int = MAX_JSON) -> bytes:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode()
    if len(payload) > limit:
        raise ValueError("Evidence JSON exceeds its size bound")
    return payload


def write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def schema_fingerprints(columns: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    """Hash live relative column order, independently recording physical attnum gaps.

    pg_dump emits only live columns, so restoring a table with dropped columns
    compacts its physical ordinal positions without changing its logical schema.
    """
    logical, counts, maximum = [], {}, {}
    for column in sorted(columns, key=lambda item: (item["table_name"], item["ordinal_position"])):
        table = column["table_name"]
        counts[table] = counts.get(table, 0) + 1
        maximum[table] = column["ordinal_position"]
        logical.append({**column, "ordinal_position": counts[table]})
    gaps = {
        table: {"live_columns": count, "max_physical_ordinal": maximum[table]}
        for table, count in counts.items()
        if maximum[table] != count
    }
    return canonical_hash(logical), {
        "raw_schema_sha256": canonical_hash(columns),
        "ordinal_gaps": gaps,
    }


def semantic_fingerprint(fingerprint: dict[str, Any]) -> dict[str, Any]:
    return {
        database: {field: value for field, value in fields.items() if field != "physical_schema"}
        for database, fields in fingerprint.items()
    }


def fingerprint_differences(
    expected: dict[str, Any], actual: dict[str, Any]
) -> list[dict[str, Any]]:
    """Emit only database/field names and hashes/counts, never row values."""
    differences = []
    for database in DBS:
        old = semantic_fingerprint(expected).get(database, {})
        new = semantic_fingerprint(actual).get(database, {})
        for field in sorted(set(old) | set(new)):
            if old.get(field) != new.get(field):
                differences.append(
                    {
                        "database": database,
                        "field": field,
                        "expected_sha256": canonical_hash(old.get(field)),
                        "observed_sha256": canonical_hash(new.get(field)),
                    }
                )
    return differences[:8]


class Stack:
    def __init__(self, project: str, compose_file: Path):
        self.project, self.phase = project, require_ci(project)
        self.compose = ["docker", "compose", "-p", project, "-f", str(compose_file.resolve())]
        self.commands: list[list[str]] = []
        self.pg = ""
        self.running: dict[str, dict[str, Any]] = {}

    def run(
        self,
        args: list[str],
        *,
        data: bytes | None = None,
        limit: int = MAX_DUMP,
        timeout: int = 180,
    ) -> bytes:
        # All arguments contain only service/database identities and fixed scripts;
        # credentials are inherited inside the container and never logged.
        self.commands.append(args)
        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE if data is not None else None,
                stdout=output,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit)),
            )
            try:
                process.communicate(input=data, timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise RuntimeError("Migration command timed out") from None
            size = output.tell()
            if size > limit:
                raise ValueError("Command output exceeded its bound")
            if process.returncode:
                raise RuntimeError(
                    "Migration command failed (details suppressed to protect secrets)"
                )
            output.seek(0)
            return output.read(limit + 1)

    def inspect(self, kind: str, name: str) -> dict[str, Any]:
        return json.loads(self.run(["docker", kind, "inspect", name]))[0]

    def check(self) -> None:
        if shutil.disk_usage("/tmp").free < 5 * 1024**3:
            raise ValueError("Less than 5 GiB runner free space")
        config = json.loads(self.run(self.compose + ["config", "--format", "json"]))
        # Reject external/reused volumes and every data bind. Only the fixed SQL
        # initializer in the source checkout may be mounted from the host.
        if set(config.get("volumes", {})) != VOLUMES:
            raise ValueError("Unexpected migration volume set")
        for key, volume in config["volumes"].items():
            if volume.get("external") or volume.get("name") != f"{self.project}_{key}":
                raise ValueError("Volume is not owned by this fresh namespace")
            actual = self.inspect("volume", volume["name"])
            if actual.get("Driver") != "local" or actual.get("Options"):
                raise ValueError("Only plain local volumes without host bindings are allowed")
            labels = actual.get("Labels") or {}
            if (
                labels.get("com.docker.compose.project") != self.project
                or labels.get("com.docker.compose.volume") != key
            ):
                raise ValueError("Docker volume labels do not match")
        for service in config["services"].values():
            for mount in service.get("volumes", []):
                if mount["type"] == "volume":
                    if mount["source"] not in VOLUMES:
                        raise ValueError("Foreign data volume")
                elif not (
                    mount["type"] == "bind"
                    and mount.get("read_only")
                    and Path(mount["source"]).resolve() == ROOT / "docker/postgres-init.sql"
                ):
                    raise ValueError("Host data mounts are forbidden")
        ids = self.run(self.compose + ["ps", "-a", "-q"]).decode().split()
        for container_id in ids:
            item = self.inspect("container", container_id)
            labels = item["Config"].get("Labels") or {}
            if labels.get("com.docker.compose.project") != self.project:
                raise ValueError("Container project label mismatch")
            for mount in item.get("Mounts", []):
                if mount.get("Type") == "volume":
                    allowed = {f"{self.project}_{key}" for key in VOLUMES}
                    if mount.get("Name") not in allowed:
                        raise ValueError("Actual container mounts a foreign data volume")
                elif not (
                    mount.get("Type") == "bind"
                    and not mount.get("RW")
                    and Path(mount["Source"]).resolve() == ROOT / "docker/postgres-init.sql"
                ):
                    raise ValueError("Actual container mounts host data")
            service = labels.get("com.docker.compose.service")
            if item["State"]["Running"] and labels.get("com.docker.compose.oneoff") != "True":
                if service in self.running:
                    raise ValueError("Ambiguous running service identity")
                self.running[service] = item
            if service == "postgres":
                if not item["State"]["Running"]:
                    raise ValueError("Postgres is not running")
                self.pg = container_id
        if not self.pg:
            raise ValueError("Missing isolated Postgres container")

    def bind_runtime(self, api_url: str | None = None) -> None:
        required = ("postgres", "langflow", "api", "worker")
        if any(name not in self.running for name in required):
            raise ValueError("Target runtime services are not all running")
        shared = set.intersection(
            *(set(self.running[name]["NetworkSettings"]["Networks"]) for name in required)
        )
        if len(shared) != 1:
            raise ValueError("Runtime services do not share one target network")
        network = self.inspect("network", next(iter(shared)))
        if (network.get("Labels") or {}).get("com.docker.compose.project") != self.project:
            raise ValueError("Runtime network is not owned by target project")
        for name, alias in (("postgres", "postgres"), ("langflow", "langflow")):
            aliases = self.running[name]["NetworkSettings"]["Networks"][next(iter(shared))]
            if alias not in (aliases.get("Aliases") or []):
                raise ValueError("Target service DNS alias missing")
        for service, variable, host, port, database in (
            ("langflow", "LANGFLOW_DATABASE_URL", "postgres", 5432, "/langflow"),
            ("api", "DATABASE_URL", "postgres", 5432, "/review_console"),
            ("worker", "DATABASE_URL", "postgres", 5432, "/review_console"),
            ("api", "LANGFLOW_URL", "langflow", 7860, ""),
            ("worker", "LANGFLOW_URL", "langflow", 7860, ""),
        ):
            env = dict(
                item.split("=", 1)
                for item in self.running[service]["Config"].get("Env", [])
                if "=" in item
            )
            address = urlsplit(env.get(variable, ""))
            if (address.hostname, address.port, address.path.rstrip("/")) != (host, port, database):
                raise ValueError("Runtime service points outside target database/Flow namespace")
        require_published_url(
            os.getenv("LANGFLOW_URL", "http://localhost:7860"), self.running["langflow"], "7860/tcp"
        )
        if api_url is not None:
            candidates = [("api", "8000/tcp"), ("web", "8080/tcp")]
            if not any(
                published_url_matches(api_url, self.running[name], port)
                for name, port in candidates
                if name in self.running
            ):
                raise ValueError("API URL is not a published target project service")

    def sql(self, database: str, query: str) -> Any:
        raw = self.run(
            [
                "docker",
                "exec",
                "-i",
                self.pg,
                "psql",
                "-X",
                "-q",
                "-A",
                "-t",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "review",
                "-d",
                database,
            ],
            data=("SET TIME ZONE 'UTC';\n" + query).encode(),
        )
        return json.loads(raw) if raw.strip() else None

    def tables(self, database: str) -> list[str]:
        return self.sql(
            database,
            "SELECT coalesce(json_agg(tablename ORDER BY tablename),'[]') "
            "FROM pg_tables WHERE schemaname='public';",
        )

    def fingerprint(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for db in DBS:
            tables = self.tables(db)
            columns = self.sql(
                db,
                "SELECT coalesce(json_agg(x ORDER BY table_name,ordinal_position),"
                "'[]') FROM (SELECT table_name,column_name,data_type,is_nullable,"
                "ordinal_position FROM information_schema.columns "
                "WHERE table_schema='public') x;",
            )
            logical_schema, physical_schema = schema_fingerprints(columns)
            entry: dict[str, Any] = {
                "schema_sha256": logical_schema,
                "physical_schema": physical_schema,
                "tables": {},
            }
            if "alembic_version" in tables:
                entry["alembic"] = self.sql(
                    db, "SELECT json_agg(version_num) FROM alembic_version;"
                )
            if db == "review_console":
                for table in tables:
                    if table == "worker_heartbeats":
                        continue
                    if not re.fullmatch(r"[a-z_]+", table):
                        raise ValueError("Unexpected table identifier")
                    rows = self.sql(db, f"SELECT coalesce(json_agg(t),'[]') FROM \"{table}\" t;")
                    # Sort by canonical row serialization to remove SQL row order.
                    row_hashes = sorted(canonical_hash(row) for row in rows)
                    entry["tables"][table] = {
                        "count": len(rows),
                        "sha256": canonical_hash(row_hashes),
                        "row_hashes": row_hashes,
                    }
            else:
                entry["users"] = self.sql(
                    db, 'SELECT json_agg(x ORDER BY id) FROM (SELECT id,username FROM "user") x;'
                )
            result[db] = entry
        return result

    def files(self, *, restore: dict[str, str] | None = None) -> dict[str, str]:
        # Every helper is a new, exited container in this run's project. No --rm
        # or volume removal is performed. Check symlinks before reading/writing.
        script = """import base64,json,sys
from pathlib import Path
roots={"documents":Path("/app/documents"),"reports":Path("/app/artifacts"),"config":Path("/app/config")}
request=json.load(sys.stdin)
result={}
for group,root in roots.items():
 if root.is_symlink(): raise ValueError("symlink root")
 paths=list(root.rglob("*"))
 if any(p.is_symlink() for p in paths): raise ValueError("symlink")
 files=[p for p in paths if p.is_file()]
 if request["mode"]=="restore" and files: raise ValueError("target volume not empty")
 for p in files:
  if len(result)>=100: raise ValueError("file count bound")
  total=sum(len(base64.b64decode(v)) for v in result.values())+p.stat().st_size
  if total>33554432: raise ValueError("file bytes bound")
  result[group+"/"+str(p.relative_to(root))]=base64.b64encode(p.read_bytes()).decode()
if request["mode"]=="restore":
 for key,value in request["files"].items():
  group,rel=key.split("/",1)
  p=roots[group]/rel
  p.parent.mkdir(parents=True,exist_ok=True)
  with p.open("xb") as f: f.write(base64.b64decode(value,validate=True))
  result[key]=value
print(json.dumps(result))
"""
        payload = {"mode": "restore" if restore is not None else "read", "files": restore or {}}
        raw = self.run(
            self.compose
            + ["run", "-T", "--no-deps", "--user", "0:0", "storage-init", "python", "-c", script],
            data=json.dumps(payload).encode(),
            limit=48 * 1024 * 1024,
        )
        files = json.loads(raw)
        if len(files) > 100:
            raise ValueError("More than 100 checkpoint files")
        size = 0
        for name, value in files.items():
            group, relative = name.split("/", 1)
            if group not in BASES:
                raise ValueError("Unknown storage group")
            safe_relative(relative)
            size += len(base64.b64decode(value, validate=True))
        if size > MAX_FILES:
            raise ValueError("Checkpoint files exceed 32 MiB")
        return files

    def quiesce(self) -> None:
        # Stop exact services only after actual label validation in check().
        self.run(self.compose + ["stop", "worker", "api", "langflow"], timeout=180)
        active = self.sql(
            "review_console",
            "SELECT count(*) FROM workflow_jobs "
            "WHERE state NOT IN ('succeeded','failed','cancelled');",
        )
        if active:
            raise ValueError("Checkpoint contains active business jobs")
        connections = self.sql(
            "langflow",
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname IN ('langflow','review_console') AND pid<>pg_backend_pid();",
        )
        if connections:
            raise ValueError("Database still has application sessions")


def published_url_matches(url: str, container: dict[str, Any], port: str) -> bool:
    address = urlsplit(url)
    if (
        address.scheme != "http"
        or address.hostname not in {"localhost", "127.0.0.1"}
        or address.username
        or address.password
        or address.path not in {"", "/"}
        or address.query
        or address.fragment
    ):
        return False
    bindings = container.get("NetworkSettings", {}).get("Ports", {}).get(port) or []
    return any(
        binding.get("HostIp") == "127.0.0.1" and str(address.port or 80) == binding.get("HostPort")
        for binding in bindings
    )


def require_published_url(url: str, container: dict[str, Any], port: str) -> None:
    if not published_url_matches(url, container, port):
        raise ValueError("Langflow URL is not a published target project service")


def live_flows(expected: str) -> dict[str, Any]:
    client = LangflowClient()
    try:
        require_langflow_version(client.request("GET", "/openapi.json").json(), expected)
        payload = client.request("GET", "/api/v1/flows/").json()
        from validate_langflow import _items

        selected = [
            item
            for item in _items(payload)
            if item.get("name") in ("Document Review Intake", "Document Review Decision")
        ]
        if len(selected) != 2:
            raise ValueError("Expected exactly two baseline Flows")
        return {
            item["name"]: {
                "id": item["id"],
                "user_id": item.get("user_id"),
                "graph_sha256": graph_hash(item["data"]),
            }
            for item in selected
        }
    finally:
        client.close()


def file_manifest(files: dict[str, str]) -> dict[str, Any]:
    return {
        key: {
            "sha256": hashlib.sha256(base64.b64decode(value)).hexdigest(),
            "bytes": len(base64.b64decode(value)),
        }
        for key, value in sorted(files.items())
    }


def checkpoint(stack: Stack, directory: Path) -> dict[str, Any]:
    if stack.phase != "baseline" or directory.exists():
        raise ValueError("Checkpoint requires a new directory and the baseline namespace")
    stack.bind_runtime()
    flows = live_flows("1.11.6")
    stack.quiesce()
    fingerprint = stack.fingerprint()
    files = stack.files()
    expected_counts = {"documents": 5, "reports": 9, "config": 1}
    if any(
        sum(key.startswith(group + "/") for key in files) != count
        for group, count in expected_counts.items()
    ):
        raise ValueError("Baseline must contain five documents, nine reports and Flow config")
    synthetic_cases = stack.sql(
        "review_console", "SELECT count(*) FROM review_cases WHERE source_kind='uploaded_demo';"
    )
    if synthetic_cases != 5 or "config/langflow-flows.json" not in files:
        raise ValueError("Baseline synthetic cases or trusted Flow config are missing")
    directory.mkdir(mode=0o700)
    for db in DBS:
        dump = stack.run(
            [
                "docker",
                "exec",
                stack.pg,
                "pg_dump",
                "-U",
                "review",
                "-d",
                db,
                "--format=plain",
                "--no-owner",
                "--no-privileges",
            ],
            limit=MAX_DUMP,
        )
        write_new(directory / f"{db}.sql", dump)
    for key, value in files.items():
        destination = directory / "files" / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_new(destination, base64.b64decode(value))
    result = {
        "source_project": stack.project,
        "flows": flows,
        "fingerprint": fingerprint,
        "files": file_manifest(files),
        "dumps": {
            db: {
                "sha256": hashlib.sha256((directory / f"{db}.sql").read_bytes()).hexdigest(),
                "bytes": (directory / f"{db}.sql").stat().st_size,
            }
            for db in DBS
        },
    }
    write_new(directory / "checkpoint.json", bounded_json(result))
    return result


def load_checkpoint(directory: Path) -> tuple[dict[str, Any], dict[str, str]]:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Invalid checkpoint directory")
    manifest = directory / "checkpoint.json"
    if manifest.is_symlink() or manifest.stat().st_size > MAX_JSON:
        raise ValueError("Invalid checkpoint manifest")
    checkpoint_data = json.loads(manifest.read_bytes())
    if require_ci(checkpoint_data["source_project"]) != "baseline":
        raise ValueError("Checkpoint source is not this run's baseline")
    files = {}
    total = 0
    for key, expected in checkpoint_data["files"].items():
        safe_relative(key)
        if key.split("/", 1)[0] not in BASES or "/" not in key:
            raise ValueError("Unknown checkpoint storage group")
        path = directory / "files" / key
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("Symlink in checkpoint")
        size = path.stat().st_size
        total += size
        if total > MAX_FILES or len(files) >= 100:
            raise ValueError("Checkpoint file bounds exceeded")
        data = path.read_bytes()
        if size != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            raise ValueError("Checkpoint file integrity mismatch")
        files[key] = base64.b64encode(data).decode()
    for db in DBS:
        path = directory / f"{db}.sql"
        expected = checkpoint_data["dumps"][db]
        if path.is_symlink() or path.stat().st_size > MAX_DUMP:
            raise ValueError("Invalid dump")
        data = path.read_bytes()
        if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
            raise ValueError("Dump integrity mismatch")
    return checkpoint_data, files


def restore(stack: Stack, directory: Path) -> dict[str, Any]:
    if stack.phase not in {"upgrade", "rollback"}:
        raise ValueError("Restore requires an upgrade or rollback namespace")
    source, files = load_checkpoint(directory)
    # No target application may have started schema initialization.
    for db in DBS:
        if stack.tables(db):
            raise ValueError("Restore target database is not empty")
        sessions = stack.sql(
            db,
            "SELECT count(*) FROM pg_stat_activity WHERE "
            "datname=current_database() AND pid<>pg_backend_pid();",
        )
        if sessions:
            raise ValueError("Restore target has application sessions")
    if stack.files():
        raise ValueError("Restore target storage is not empty")
    for db in DBS:
        stack.run(
            [
                "docker",
                "exec",
                "-i",
                stack.pg,
                "psql",
                "-X",
                "-q",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "review",
                "-d",
                db,
            ],
            data=(directory / f"{db}.sql").read_bytes(),
        )
    stack.files(restore=files)
    restored = stack.fingerprint()
    if semantic_fingerprint(restored) != semantic_fingerprint(source["fingerprint"]):
        details = fingerprint_differences(source["fingerprint"], restored)
        raise ValueError("Restored database fingerprint mismatch: " + json.dumps(details))
    if file_manifest(stack.files()) != source["files"]:
        raise ValueError("Restored file fingerprint mismatch")
    return {
        "restored_pre_upgrade_checkpoint": True,
        "target_project": stack.project,
        "semantic_fingerprint_sha256": canonical_hash(semantic_fingerprint(restored)),
        "physical_schema_before": {db: source["fingerprint"][db]["physical_schema"] for db in DBS},
        "physical_schema_restored": {db: restored[db]["physical_schema"] for db in DBS},
    }


def reconcile_validation(
    stack: Stack,
    validation: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
    files: dict[str, Any],
    old_case_ids: set[str] | None = None,
) -> dict[str, int]:
    deltas = {
        "review_cases": 5,
        "document_versions": 5,
        "decisions": 3,
        "report_artifacts": 9,
        "workflow_jobs": 9,
    }
    for table, count in deltas.items():
        if (
            after["review_console"]["tables"][table]["count"]
            - before["review_console"]["tables"][table]["count"]
            != count
        ):
            raise ValueError("Target database lacks exact expected validation increments")
    columns = {
        "review_cases": "id,current_document_version_id,document_hash",
        "document_versions": "id,case_id,source_sha256,storage_key,bytes",
        "decisions": "id,case_id,document_version_id,decision",
        "workflow_jobs": "id,case_id,document_version_id,kind,state,langflow_job_id,decision_id",
        "report_artifacts": (
            "id,case_id,document_version_id,decision_id,format,sha256,bytes,storage_key"
        ),
    }
    rows = {
        table: stack.sql(
            "review_console",
            f"SELECT coalesce(json_agg(t),'[]') FROM (SELECT {fields} FROM {table}) t;",
        )
        for table, fields in columns.items()
    }
    cases = validation.get("cases", [])
    markdown, negative = validation["markdown_intake"], validation["failure_retry"]
    expected_cases = [*cases, markdown, negative]
    ids = [case["case_id"] for case in expected_cases]
    if len(cases) != 3 or len(set(ids)) != 5 or set(ids) & (old_case_ids or set()):
        raise ValueError("Validator did not return five distinct target cases")
    for case in expected_cases:
        current = next((row for row in rows["review_cases"] if row["id"] == case["case_id"]), None)
        if not current or current["document_hash"] != case["source_sha256"]:
            raise ValueError("Validator case/source bytes absent from target SQL")
        version_id = current["current_document_version_id"]
        if case.get("document_version_id", version_id) != version_id:
            raise ValueError("Validator document identity differs from target SQL")
        version = next(
            (
                row
                for row in rows["document_versions"]
                if row["id"] == version_id and row["case_id"] == case["case_id"]
            ),
            None,
        )
        if not version or version["source_sha256"] != case["source_sha256"]:
            raise ValueError("Validator document/source bytes absent from target SQL")
        file = files.get("documents/" + version["storage_key"])
        if not file or (file["sha256"], file["bytes"]) != (
            version["source_sha256"],
            version["bytes"],
        ):
            raise ValueError("Target document file differs from validator/SQL")
        jobs = [
            row
            for row in rows["workflow_jobs"]
            if row["case_id"] == case["case_id"] and row["document_version_id"] == version_id
        ]
        if case in cases:
            expected_jobs = [
                (case["intake_job_id"], case["intake_langflow_job_id"], "intake", "succeeded"),
                (None, case["report_langflow_job_id"], "report", "succeeded"),
            ]
        elif case is markdown:
            job = case["intake_job"]
            expected_jobs = [(job["job_id"], job["langflow_job_id"], "intake", "succeeded")]
        else:
            expected_jobs = [
                (case[key]["job_id"], case[key]["langflow_job_id"], "intake", "failed")
                for key in ("first_job", "retry_job")
            ]
        if len(jobs) != len(expected_jobs) or any(
            not any(
                (identity is None or row["id"] == identity)
                and row["langflow_job_id"] == upstream
                and row["kind"] == kind
                and row["state"] == state
                for row in jobs
            )
            for identity, upstream, kind, state in expected_jobs
        ):
            raise ValueError("Validator jobs absent or changed in target SQL")
        decisions = [row for row in rows["decisions"] if row["case_id"] == case["case_id"]]
        reports = [row for row in rows["report_artifacts"] if row["case_id"] == case["case_id"]]
        if case not in cases:
            if decisions or reports:
                raise ValueError("Unexpected target decision/report for intake-only case")
            continue
        if len(decisions) != 1 or (
            decisions[0]["id"],
            decisions[0]["document_version_id"],
            decisions[0]["decision"],
        ) != (case["decision_id"], version_id, case["decision"]):
            raise ValueError("Validator decision absent or changed in target SQL")
        if len(reports) != 3 or len(case["reports"]) != 3:
            raise ValueError("Target reports do not match validator")
        for report in case["reports"]:
            matches = [
                row
                for row in reports
                if row["format"] == report["format"]
                and row["document_version_id"] == version_id
                and row["decision_id"] == case["decision_id"]
                and row["sha256"] == report["sha256"]
                and row["bytes"] == report["bytes"]
            ]
            if len(matches) != 1 or files.get("reports/" + matches[0]["storage_key"]) != {
                "sha256": report["sha256"],
                "bytes": report["bytes"],
            }:
                raise ValueError("Validator report differs from target SQL/volume bytes")
    return deltas


def verify(stack: Stack, directory: Path, api_url: str) -> dict[str, Any]:
    if stack.phase not in {"upgrade", "rollback"}:
        raise ValueError("Verify requires upgrade or rollback namespace")
    source, _ = load_checkpoint(directory)
    expected = "1.13.1" if stack.phase == "upgrade" else "1.11.6"
    stack.bind_runtime(api_url)
    before = stack.fingerprint()
    if (
        semantic_fingerprint(before)["review_console"]
        != semantic_fingerprint(source["fingerprint"])["review_console"]
    ):
        raise ValueError("Pre-existing business records changed during startup")
    if before["langflow"]["users"] != source["fingerprint"]["langflow"]["users"]:
        raise ValueError("Langflow user identities changed")
    if live_flows(expected) != source["flows"]:
        raise ValueError("Stored Flow identity/graph changed; no bootstrap repair is allowed")
    if file_manifest(stack.files()) != source["files"]:
        raise ValueError("Pre-existing file bytes changed")
    old_case_ids = set(
        stack.sql("review_console", "SELECT coalesce(json_agg(id),'[]') FROM review_cases;")
    )
    # Existing validator performs real per-execution inputs without PATCHing Flow.
    raw = stack.run(
        [
            sys.executable,
            str(ROOT / "scripts/validate_langflow.py"),
            "--expected-langflow-version",
            expected,
            "--api-url",
            api_url,
        ],
        limit=MAX_JSON,
        timeout=900,
    )
    validation = json.loads(raw)
    if validation.get("result") != "passed":
        raise ValueError("Real business validation did not pass")
    after = stack.fingerprint()
    old_tables = source["fingerprint"]["review_console"]["tables"]
    for table, old in old_tables.items():
        new = after["review_console"]["tables"][table]
        if Counter(old["row_hashes"]) - Counter(new["row_hashes"]):
            raise ValueError("Business validation changed a pre-existing record")
    after_files = file_manifest(stack.files())
    if len(set(after_files) - set(source["files"])) != 14:
        raise ValueError("Target volume lacks exact five new documents and nine reports")
    increments = reconcile_validation(stack, validation, before, after, after_files, old_case_ids)
    if any(after_files.get(key) != value for key, value in source["files"].items()):
        raise ValueError("Business validation changed a pre-existing file")
    if live_flows(expected) != source["flows"]:
        raise ValueError("Business validation changed a pre-existing Flow")
    return {
        "preexisting_semantics_and_files_preserved": True,
        "before_schema": source["fingerprint"],
        "after_schema": before,
        "flow_identity_and_graph": source["flows"],
        "business_validation": validation,
        "target_sql_increments": increments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("checkpoint", "restore", "verify"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--compose-file", type=Path, required=True)
    parser.add_argument("--checkpoint-dir", type=Path, required=True)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    stack = Stack(args.project, args.compose_file)
    # Do not allow writes into a repository, original-data tree, or home.
    directory = args.checkpoint_dir.resolve()
    if not directory.is_relative_to(Path("/tmp").resolve()) or directory == Path("/tmp").resolve():
        raise ValueError("Checkpoint must be in a dedicated ephemeral /tmp subdirectory")
    if args.evidence.exists():
        raise ValueError("Evidence target already exists")
    stack.check()
    if args.action == "checkpoint":
        result = checkpoint(stack, directory)
    elif args.action == "restore":
        result = restore(stack, directory)
    else:
        result = verify(stack, directory, args.api_url)
    evidence = {
        "producer": "scripts/verify_langflow_migration.py",
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "checked_at": datetime.now(UTC).isoformat(),
        "action": args.action,
        "project": args.project,
        "checkpoint_manifest_sha256": hashlib.sha256(
            (directory / "checkpoint.json").read_bytes()
        ).hexdigest(),
        "result": "passed",
        "details": result,
        "commands": stack.commands,
        "method": "plain dumps; stopped baseline writers; empty isolated restores; UTC SQL",
        "retention": "dumps/files ephemeral unless separately selected by evidence manifest",
        "not_tested": [
            "original SQLite or historical volumes",
            "in-place downgrade",
            "zero loss of writes after pre-upgrade checkpoint",
            "production data",
        ],
    }
    write_new(args.evidence, bounded_json(evidence))
    print(json.dumps({"action": args.action, "result": "passed", "project": args.project}))


if __name__ == "__main__":
    main()
