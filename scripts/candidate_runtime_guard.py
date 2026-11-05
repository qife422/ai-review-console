"""Read-only ownership/version binding before synthetic runtime fault injection."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from api.app.langflow_client import LangflowClient
from scripts.bootstrap_langflow import require_langflow_version
from scripts.verify_langflow_migration import Stack, published_url_matches


def require_candidate_namespace(project: str, expected: str) -> None:
    run = os.getenv("GITHUB_RUN_ID", "")
    if (
        os.getenv("GITHUB_ACTIONS") != "true"
        or not re.fullmatch(r"[1-9][0-9]{0,19}", run)
        or project not in {f"arc-ci-{run}-amd64", f"arc-ci-{run}-arm64"}
        or expected != "1.13.1"
    ):
        raise ValueError(
            "Only this GitHub run's candidate namespace with Langflow 1.13.1 is allowed"
        )


class CandidateRuntimeGuard(Stack):
    def __init__(
        self,
        project: str,
        compose_file: Path,
        expected: str,
        api_url: str = "http://127.0.0.1:8000",
        database_port: int | None = None,
    ):
        require_candidate_namespace(project, expected)
        self.project, self.phase = project, "candidate-proof"
        self.compose = ["docker", "compose", "-p", project, "-f", str(compose_file.resolve())]
        self.commands: list[list[str]] = []
        self.pg = ""
        self.running: dict[str, dict[str, Any]] = {}
        self.expected, self.api_url, self.database_port = expected, api_url, database_port

    def validate(self) -> None:
        self.check()
        self.bind_runtime(self.api_url)
        self.verify_effective_worker()
        if self.database_port is not None and not published_url_matches(
            f"http://127.0.0.1:{self.database_port}", self.running["postgres"], "5432/tcp"
        ):
            raise ValueError("Database loopback port is not owned by the target Postgres container")
        client = LangflowClient()
        try:
            require_langflow_version(client.request("GET", "/openapi.json").json(), self.expected)
        finally:
            client.close()

    def verify_effective_worker(self) -> None:
        """Check compose-run inputs before it can start an injected process."""
        config = json.loads(self.run(self.compose + ["config", "--format", "json"]))
        configured = config["services"]["worker"]
        actual = self.running["worker"]
        if any(
            configured.get(key)
            for key in (
                "privileged",
                "devices",
                "cap_add",
                "volumes_from",
                "network_mode",
                "pid",
                "ipc",
                "extra_hosts",
            )
        ):
            raise ValueError("Unsafe effective worker process/network configuration")
        image = self.inspect("image", configured["image"])
        if configured["image"] != actual["Config"]["Image"] or image["Id"] != actual["Image"]:
            raise ValueError("Effective worker image/tag differs from running target")

        def env(values: list[str]) -> dict[str, str]:
            return dict(value.split("=", 1) for value in values if "=" in value)

        expected_env = env(image["Config"].get("Env") or [])
        expected_env.update(
            {key: str(value) for key, value in configured.get("environment", {}).items()}
        )
        if expected_env != env(actual["Config"].get("Env") or []):
            raise ValueError("Effective worker environment differs from running target")
        for key, image_key in (("entrypoint", "Entrypoint"), ("command", "Cmd"), ("user", "User")):
            expected = configured.get(key, image["Config"].get(image_key))
            if expected != actual["Config"].get(image_key):
                raise ValueError("Effective worker command/user differs from running target")
        expected_mounts = sorted(
            (
                "volume",
                config["volumes"][mount["source"]]["name"],
                mount["target"],
                not mount.get("read_only", False),
            )
            for mount in configured.get("volumes", [])
        )
        actual_mounts = sorted(
            (mount["Type"], mount.get("Name"), mount["Destination"], mount["RW"])
            for mount in actual["Mounts"]
        )
        if expected_mounts != actual_mounts:
            raise ValueError("Effective worker volumes differ from running target")
        expected_networks = {
            config["networks"][name]["name"] for name in configured.get("networks", {})
        }
        if expected_networks != set(actual["NetworkSettings"]["Networks"]):
            raise ValueError("Effective worker networks differ from running target")
        for settings in configured.get("networks", {}).values():
            if (settings or {}).get("aliases"):
                raise ValueError("Explicit worker network aliases are not allowed for this proof")

    def assert_container(self, identifier: str, service: str) -> dict[str, Any]:
        item = self.inspect("container", identifier)
        labels = item["Config"].get("Labels") or {}
        if (
            labels.get("com.docker.compose.project") != self.project
            or labels.get("com.docker.compose.service") != service
            or item["Image"] != self.running[service]["Image"]
        ):
            raise ValueError("Refusing fault action on a foreign service/container/image")
        expected = sorted(
            (mount["Type"], mount.get("Name"), mount["Destination"], mount["RW"])
            for mount in self.running[service]["Mounts"]
        )
        actual = sorted(
            (mount["Type"], mount.get("Name"), mount["Destination"], mount["RW"])
            for mount in item["Mounts"]
        )
        if actual != expected:
            raise ValueError("Refusing fault action with changed service volume bindings")
        original_networks = set(
            self.running[service].get("NetworkSettings", {}).get("Networks", {})
        )
        actual_networks = set(item.get("NetworkSettings", {}).get("Networks", {}))
        if original_networks != actual_networks:
            raise ValueError("Refusing fault action with changed service network bindings")
        database_variable = "LANGFLOW_DATABASE_URL" if service == "langflow" else "DATABASE_URL"

        def environment(container: dict[str, Any]) -> dict[str, str]:
            return dict(
                value.split("=", 1) for value in container["Config"].get("Env", []) if "=" in value
            )

        if environment(item).get(database_variable) != environment(self.running[service]).get(
            database_variable
        ):
            raise ValueError("Refusing fault action with changed target database binding")
        return item
