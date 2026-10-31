"""What an evaluation ran on: machine, interpreter and library versions, written once per run.

Stages stop at wall-clock limits, so results can depend on the CPU; the manifest keeps the machine
with the records. A results directory is tied to one commit and one environment: resuming under a
different one is refused, so a results file never mixes code versions.
"""

import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

MANIFEST_FILE = "manifest.json"


@dataclass(frozen=True)
class Environment:
    cpu: str
    os: str
    python: str
    ortools: str
    numpy: str
    scipy: str


@dataclass(frozen=True)
class Manifest:
    commit: str
    environment: Environment
    started: str  # UTC, ISO 8601; informational, not compared on resume

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Manifest":
        data = json.loads(text)
        return cls(data["commit"], Environment(**data["environment"]), data["started"])


def _cpu_model() -> str:
    """The CPU model name; `platform.processor()` alone gives only the family on Windows."""
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                capture_output=True,
                text=True,
                timeout=20,
                check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            out = ""
        if out:
            return out.splitlines()[0].strip()
    return platform.processor() or platform.machine() or "unknown"


def current_environment() -> Environment:
    return Environment(
        cpu=_cpu_model(),
        os=platform.platform(),
        python=platform.python_version(),
        ortools=version("ortools"),
        numpy=version("numpy"),
        scipy=version("scipy"),
    )


def check_or_write(out: Path, commit: str, environment: Environment) -> Manifest:
    """Write `<out>/manifest.json` for a new run; for a resumed one require the same code and setup.

    A results file that already has records but no manifest (an older run) is refused as well,
    because its machine and code are unknown.
    """
    path = out / MANIFEST_FILE
    if path.exists():
        existing = Manifest.from_json(path.read_text(encoding="utf-8"))
        if existing.commit != commit or existing.environment != environment:
            raise ValueError(
                f"{path} was written for commit {existing.commit[:12]} and "
                f"{existing.environment}; this run is {commit[:12]} and {environment}. "
                "Use an empty output directory (a results file must not mix code versions)."
            )
        return existing
    results = out / "results.jsonl"
    if results.exists() and results.stat().st_size > 0:
        raise ValueError(f"{results} has records but there is no {MANIFEST_FILE}; use a new --out")
    manifest = Manifest(commit, environment, datetime.now(UTC).isoformat(timespec="seconds"))
    path.write_text(manifest.to_json(), encoding="utf-8", newline="\n")
    return manifest
