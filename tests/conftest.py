import os
import tempfile
from pathlib import Path

TEST_ROOT = Path(tempfile.mkdtemp(prefix="arc-unit-"))
TEST_DATABASE = TEST_ROOT / "review.sqlite3"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE}"
os.environ["DEMO_MODE"] = "true"
os.environ["DOCUMENTS_ROOT"] = str(TEST_ROOT / "documents")
os.environ["REPORTS_ROOT"] = str(TEST_ROOT / "reports")
# Unit tests bind fake flow configuration only; real builds are separate integration evidence.
os.environ["LANGFLOW_INTAKE_FLOW_ID"] = "unit-intake-flow"
os.environ["LANGFLOW_INTAKE_FLOW_HASH"] = "a" * 64
os.environ["LANGFLOW_INTAKE_CONFIG_HASH"] = "b" * 64
os.environ["LANGFLOW_DECISION_FLOW_ID"] = "unit-report-flow"
os.environ["LANGFLOW_DECISION_FLOW_HASH"] = "c" * 64
os.environ["LANGFLOW_DECISION_CONFIG_HASH"] = "d" * 64

from api.app.database import engine  # noqa: E402
from api.app.migrations import migrate  # noqa: E402

migrate(engine)
