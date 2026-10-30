"""Streaming reader for gzipped CSV files: hashes the bytes, counts rows, and selects columns."""

from __future__ import annotations

import gzip
import hashlib
import operator
from collections.abc import Callable, Sequence
from io import BufferedIOBase
from pathlib import Path

CHUNK_BYTES = 1 << 22


def column_plan(header: Sequence[str], keep: Sequence[str], drop: Sequence[str] = ()) -> list[int]:
    """Positions of the kept columns in header order, so output follows the keep order."""
    unexpected = set(header) - set(keep) - set(drop)
    missing = set(keep) - set(header)
    if unexpected or missing:
        raise ValueError(
            f"header mismatch: unexpected {sorted(unexpected)}, missing {sorted(missing)}"
        )
    return [header.index(name) for name in keep]


def selector(indexes: Sequence[int]) -> Callable[[bytes], bytes]:
    """Return a function that keeps the given comma-separated fields of one line."""
    if len(indexes) == 1:
        index = indexes[0]
        return lambda line: line.split(b",")[index]
    pick = operator.itemgetter(*indexes)
    return lambda line: b",".join(pick(line.split(b",")))


class RawStream:
    """Read a gzipped CSV as bytes, optionally keeping a subset of columns.

    The header is consumed on open. Output holds data lines only. The SHA-256 covers the
    decompressed file including its header, so it can be compared to a recorded checksum.
    """

    def __init__(self, source: BufferedIOBase) -> None:
        """Wrap an open binary stream and read the header line."""
        self._source = source
        self._sha = hashlib.sha256()
        self._pending = b""
        self._out = bytearray()
        self._eof = False
        self._project: Callable[[bytes], bytes] | None = None
        self.rows = 0
        first = source.readline()
        self._sha.update(first)
        self.header = first.decode("latin-1").strip().split(",")

    @property
    def sha256(self) -> str:
        """Hex digest of everything read so far."""
        return self._sha.hexdigest()

    def close(self) -> None:
        """Close the underlying file."""
        self._source.close()

    def keep_columns(self, indexes: Sequence[int]) -> None:
        """Emit only these header positions, in the given order."""
        self._project = selector(indexes)

    def _lines(self, data: bytes) -> bytes:
        """Count the rows in a block of complete lines and apply the column selection."""
        lines = [line.rstrip(b"\r") for line in data.split(b"\n") if line.strip()]
        self.rows += len(lines)
        if self._project is not None:
            lines = [self._project(line) for line in lines]
        return b"\n".join(lines) + b"\n" if lines else b""

    def _fill(self) -> None:
        """Read one more chunk and move its complete lines to the output buffer."""
        chunk = self._source.read(CHUNK_BYTES)
        if not chunk:
            self._eof = True
            self._out += self._lines(self._pending)
            self._pending = b""
            return
        self._sha.update(chunk)
        data = self._pending + chunk
        cut = data.rfind(b"\n") + 1
        self._pending = data[cut:]
        self._out += self._lines(data[:cut])

    def read(self, size: int = -1) -> bytes:
        """Return up to size bytes of output; an empty result means the end of the file."""
        while not self._eof and (size < 0 or len(self._out) < size):
            self._fill()
        if size < 0:
            size = len(self._out)
        result = bytes(self._out[:size])
        del self._out[:size]
        return result

    def readline(self, size: int = -1) -> bytes:
        """Return one output line, which is what COPY's reader protocol requires."""
        while not self._eof and b"\n" not in self._out:
            self._fill()
        end = self._out.find(b"\n") + 1 or len(self._out)
        return self.read(end if size < 0 else min(end, size))


def open_stream(path: Path) -> RawStream:
    """Open a gzipped CSV for streaming; the caller calls close() when done."""
    return RawStream(gzip.open(path, "rb"))
