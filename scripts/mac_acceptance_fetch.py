"""Meter archive and metadata response bodies for isolated Mac acceptance."""

from __future__ import annotations

import fcntl
import hashlib
import http.client
import os
import stat
from pathlib import Path
from urllib.parse import urljoin, urlsplit

MAX_RECEIVED_BYTES = 1 << 30
REDIRECT_BODY_LIMIT = 16 << 10


class TransferLimitError(RuntimeError):
    """The response or reservation exceeded the approved transfer bounds."""


class TransferJournal:
    """Append reservations durably before sending requests in a shared run."""

    def __init__(self, path: Path, scope_sha256: str) -> None:
        if len(scope_sha256) != 64 or any(c not in "0123456789abcdef" for c in scope_sha256):
            raise ValueError("Invalid transfer scope digest")
        self.path = path
        self.header = b"ARC-TRANSFER-1 " + scope_sha256.encode("ascii")

    def initialize(self, carried_bytes: int) -> None:
        """Create only a new journal and carry forward prior reservations."""
        if not 0 <= carried_bytes <= MAX_RECEIVED_BYTES:
            raise ValueError("Invalid carried byte count")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        with os.fdopen(os.open(self.path, flags, 0o600), "wb") as ledger:
            ledger.write(self.header + b"\n" + str(carried_bytes).encode("ascii") + b"\n")
            ledger.flush()
            os.fsync(ledger.fileno())

    def reserve(self, size: int, limit: int) -> int:
        if not 0 < size <= limit <= MAX_RECEIVED_BYTES:
            raise TransferLimitError("Invalid reservation")
        flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(self.path, flags), "r+b") as ledger:
            identity = os.fstat(ledger.fileno())
            if not stat.S_ISREG(identity.st_mode) or identity.st_uid != os.getuid():
                raise TransferLimitError("Transfer journal is not an owned regular file")
            if stat.S_IMODE(identity.st_mode) != 0o600 or identity.st_nlink != 1:
                raise TransferLimitError("Transfer journal is not private and exclusive")
            fcntl.flock(ledger.fileno(), fcntl.LOCK_EX)
            body = ledger.read(64 << 10)
            lines = body.splitlines()
            if len(body) == 64 << 10 or not body.endswith(b"\n") or len(lines) < 2:
                raise TransferLimitError("Incomplete transfer journal")
            if lines[0] != self.header or any(not line.isdigit() for line in lines[1:]):
                raise TransferLimitError("Transfer journal does not match scope")
            totals = list(map(int, lines[1:]))
            if any(previous >= current for previous, current in zip(totals, totals[1:])):
                raise TransferLimitError("Transfer journal is not monotonic")
            reserved = totals[-1] + size
            if reserved > limit:
                raise TransferLimitError("Transfer budget exhausted before request")
            ledger.write(str(reserved).encode("ascii") + b"\n")
            ledger.flush()
            os.fsync(ledger.fileno())
            return reserved


class MeteredFetch:
    """A sequential receiver with conservative reservations and no auto retries."""

    def __init__(
        self,
        hosts: set[str],
        *,
        carried_bytes: int = 0,
        limit: int = MAX_RECEIVED_BYTES,
        journal: TransferJournal | None = None,
    ) -> None:
        if not 0 <= carried_bytes <= limit <= MAX_RECEIVED_BYTES:
            raise ValueError("Invalid byte budget")
        if journal is not None and carried_bytes:
            raise ValueError("Carry prior bytes in the journal")
        self.hosts = frozenset(hosts)
        self.limit = limit
        self.journal = journal
        self.reserved = carried_bytes
        self.receipts: list[dict] = []

    def _reserve(self, size: int) -> None:
        if self.journal is not None:
            self.reserved = self.journal.reserve(size, self.limit)
            return
        if size <= 0 or self.reserved + size > self.limit:
            raise TransferLimitError("Transfer budget exhausted before request")
        self.reserved += size

    def get(
        self,
        url: str,
        *,
        max_bytes: int,
        exact_bytes: int | None = None,
        sha256: str | None = None,
        headers: dict[str, str] | None = None,
        redirect_hosts: frozenset[str] = frozenset(),
    ) -> bytes:
        """Fetch a fixed or capped body, allowing at most one scoped redirect.

        Reservations are retained after failures, including partial transfers.
        HTTP framing and TLS overhead are outside the response-body meter.
        """
        if exact_bytes is not None and not 0 <= exact_bytes <= max_bytes:
            raise ValueError("Invalid expected response size")
        self._reserve(max_bytes + (REDIRECT_BODY_LIMIT if redirect_hosts else 0))
        original = urlsplit(url)
        response_headers = {**(headers or {}), "Accept-Encoding": "identity"}
        for attempt in range(2):
            parts = urlsplit(url)
            allowed = self.hosts if attempt == 0 else redirect_hosts & self.hosts
            hostname = parts.hostname
            if (
                parts.scheme != "https"
                or not hostname
                or hostname not in allowed
                or parts.username is not None
                or parts.port not in (None, 443)
                or parts.fragment
            ):
                raise TransferLimitError("URL outside the scoped HTTPS hosts")
            path = parts.path or "/"
            if parts.query:
                path += "?" + parts.query
            connection = http.client.HTTPSConnection(hostname, timeout=20)
            try:
                connection.request("GET", path, headers=response_headers)
                with connection.getresponse() as response:
                    redirect = response.status in (301, 302, 303, 307, 308)
                    if redirect and (attempt != 0 or not redirect_hosts):
                        raise TransferLimitError("Unapproved redirect")
                    if not redirect and response.status != 200:
                        raise TransferLimitError(f"HTTP {response.status} from {hostname}")
                    expected = None if redirect else exact_bytes
                    cap = REDIRECT_BODY_LIMIT if redirect else max_bytes
                    payload = self._read(response, cap, expected)
                    self.receipts.append(
                        {
                            "request_host": original.hostname,
                            "response_host": hostname,
                            "status": response.status,
                            "bytes": len(payload),
                        }
                    )
                    if not redirect:
                        if sha256 and hashlib.sha256(payload).hexdigest() != sha256:
                            raise TransferLimitError("Response SHA-256 mismatch")
                        return payload
                    location = response.getheader("Location")
                    if not location:
                        raise TransferLimitError("Redirect has no Location")
                    url = urljoin(url, location)
                    response_headers = {"Accept-Encoding": "identity"}
            finally:
                connection.close()
        raise TransferLimitError("Redirect limit exhausted")

    @staticmethod
    def _read(response: http.client.HTTPResponse, cap: int, expected: int | None) -> bytes:
        if response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise TransferLimitError("Unexpected response Content-Encoding")
        lengths = [value for key, value in response.getheaders() if key.lower() == "content-length"]
        encoding = response.getheader("Transfer-Encoding")
        if expected is None and not lengths and encoding and encoding.lower() == "chunked":
            payload = response.read(cap)
            if len(payload) >= cap:
                raise TransferLimitError("Chunked metadata reached its cap")
            return payload
        if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit() or encoding:
            raise TransferLimitError("Response must have one explicit Content-Length")
        size = int(lengths[0])
        if size > cap or (expected is not None and size != expected):
            raise TransferLimitError("Response length exceeds cap or differs from lock")
        payload = response.read(size)
        if len(payload) != size:
            raise TransferLimitError("Truncated response body")
        return payload
