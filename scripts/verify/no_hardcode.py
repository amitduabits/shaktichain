"""Static guardrail: reject known runtime hardcoded KPI values."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

# Known runtime literals that must not appear in product code.
BANNED_LITERALS = [
    'simulatedBalance="1,500.00"',
    'currentRound: 42',
    'timeRemaining: 300',
    "stakedAmount: '500.00'",
    "pendingRewards: '12.50'",
    "totalStaked: '5,000,000'",
    '"price": 6.0',
    '"source": "default"',
]

RUNTIME_PATHS = [
    REPO_ROOT / "v2g-marketplace" / "backend",
    REPO_ROOT / "v2g-marketplace" / "frontend" / "src",
    REPO_ROOT / "ml" / "ml-service" / "app",
]

SKIP_SUFFIXES = {".md", ".txt", ".json", ".lock", ".svg"}


def main() -> int:
    violations: list[tuple[Path, str]] = []

    for root in RUNTIME_PATHS:
        if not root.exists():
            continue

        for path in root.rglob("*"):
            if not path.is_file() or path.suffix in SKIP_SUFFIXES:
                continue

            text = path.read_text(encoding="utf-8", errors="ignore")
            for literal in BANNED_LITERALS:
                if literal in text:
                    violations.append((path.relative_to(REPO_ROOT), literal))

    if violations:
        print("Hardcoded runtime literal(s) found:")
        for file_path, literal in violations:
            print(f"- {file_path}: {literal}")
        return 1

    print("No banned runtime hardcoded literals found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
