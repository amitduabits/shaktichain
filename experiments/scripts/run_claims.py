"""Generate deterministic claim-matrix evidence artifacts from runnable experiments."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from experiments.core.experiment_runner import ExperimentConfig, ExperimentRunner


def _git_commit(root: Path) -> str | None:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        return value or None
    except Exception:
        pass

    git_dir = root / ".git"
    head_file = git_dir / "HEAD"
    if not head_file.exists():
        return None

    head = head_file.read_text(encoding="utf-8", errors="ignore").strip()
    if not head:
        return None

    if not head.startswith("ref: "):
        return head

    ref = head.split(" ", 1)[1].strip()
    ref_file = git_dir / ref
    if ref_file.exists():
        value = ref_file.read_text(encoding="utf-8", errors="ignore").strip()
        return value or None

    packed_refs = git_dir / "packed-refs"
    if packed_refs.exists():
        for line in packed_refs.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line or line.startswith("#") or line.startswith("^"):
                continue
            parts = line.split(" ")
            if len(parts) == 2 and parts[1].strip() == ref:
                return parts[0].strip()

    return None


def _docker_http_get(path: str) -> Dict[str, Any] | None:
    sock_path = "/var/run/docker.sock"
    if not Path(sock_path).exists():
        return None

    request = (
        f"GET {path} HTTP/1.1\r\n"
        "Host: docker\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("utf-8")

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(2.0)
            client.connect(sock_path)
            client.sendall(request)

            chunks: list[bytes] = []
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)

        raw = b"".join(chunks)
        if b"\r\n\r\n" not in raw:
            return None

        header_raw, body = raw.split(b"\r\n\r\n", 1)
        header_lines = header_raw.splitlines()
        status_line = header_lines[0].decode("utf-8", errors="ignore")
        if " 200 " not in status_line:
            return None

        headers: Dict[str, str] = {}
        for line in header_lines[1:]:
            text = line.decode("utf-8", errors="ignore")
            if ":" not in text:
                continue
            key, value = text.split(":", 1)
            headers[key.strip().lower()] = value.strip().lower()

        if headers.get("transfer-encoding") == "chunked":
            decoded = bytearray()
            cursor = 0
            while cursor < len(body):
                end = body.find(b"\r\n", cursor)
                if end == -1:
                    break
                size_raw = body[cursor:end].decode("utf-8", errors="ignore").strip()
                try:
                    chunk_size = int(size_raw, 16)
                except ValueError:
                    break
                cursor = end + 2
                if chunk_size == 0:
                    break
                decoded.extend(body[cursor:cursor + chunk_size])
                cursor += chunk_size + 2
            body = bytes(decoded)

        return json.loads(body.decode("utf-8", errors="ignore"))
    except Exception:
        return None


def _container_image_digest() -> str | None:
    digest_from_env = os.getenv("CONTAINER_IMAGE_DIGEST", "").strip()
    if digest_from_env:
        return digest_from_env

    container_id = os.getenv("HOSTNAME", "").strip()
    if not container_id:
        return None

    container_info = _docker_http_get(f"/v1.41/containers/{container_id}/json")
    if not container_info:
        return None

    image_id = str(container_info.get("Image", "")).strip()
    if not image_id:
        return None

    image_info = _docker_http_get(f"/v1.41/images/{image_id}/json")
    if image_info:
        repo_digests = image_info.get("RepoDigests") or []
        if repo_digests:
            digest_ref = str(repo_digests[0])
            if "@" in digest_ref:
                return digest_ref.split("@", 1)[1]
            return digest_ref

    return image_id


def _result_signature(result: Dict[str, Any]) -> tuple[float, float]:
    price_mean = float(result.get("metrics", {}).get("clearing_price", {}).get("mean", 0.0))
    efficiency_mean = float(result.get("metrics", {}).get("efficiency", {}).get("mean", 0.0))
    return price_mean, efficiency_mean


async def _run(mode: str, output_dir: Path) -> Dict[str, Any]:
    workspace_root = Path(__file__).resolve().parents[2]
    docs_dir = workspace_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    artifact_dir = output_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)

    run_mode = "quick" if mode in {"dev", "test"} else "standard"
    base_seed = 42

    runner = ExperimentRunner(
        config_path=workspace_root / "experiments" / "config" / "experiment_config.yaml",
        output_dir=workspace_root / "artifacts" / "experiments",
        cache_enabled=False,
        max_retries=1,
        checkpoint_interval_minutes=15,
    )

    config_same_1 = ExperimentConfig(
        name=f"claim_matrix_{mode}_seed42_a",
        run_mode=run_mode,
        scenario="normal_demand",
        agent_distribution="default",
        random_seed=base_seed,
    )
    config_same_2 = ExperimentConfig(
        name=f"claim_matrix_{mode}_seed42_b",
        run_mode=run_mode,
        scenario="normal_demand",
        agent_distribution="default",
        random_seed=base_seed,
    )
    config_diff = ExperimentConfig(
        name=f"claim_matrix_{mode}_seed314",
        run_mode=run_mode,
        scenario="normal_demand",
        agent_distribution="default",
        random_seed=314,
    )

    result_same_1 = await runner.run_experiment(config_same_1, use_cache=False)
    result_same_2 = await runner.run_experiment(config_same_2, use_cache=False)
    result_diff = await runner.run_experiment(config_diff, use_cache=False)

    sig_same_1 = _result_signature(result_same_1.to_dict())
    sig_same_2 = _result_signature(result_same_2.to_dict())
    sig_diff = _result_signature(result_diff.to_dict())

    reproducible = sig_same_1 == sig_same_2
    invariant_to_seed = sig_same_1 != sig_diff

    generated_at = datetime.now(timezone.utc).isoformat()

    payload = {
        "generated_at": generated_at,
        "mode": mode,
        "claims": [
            {
                "claim_id": "EXP-REPRO-001",
                "description": "Same seed reproduces identical aggregate metrics.",
                "passed": reproducible,
                "evidence": {
                    "seed": base_seed,
                    "run_a": sig_same_1,
                    "run_b": sig_same_2,
                },
            },
            {
                "claim_id": "EXP-INVAR-001",
                "description": "Changing random seed changes aggregate outcomes.",
                "passed": invariant_to_seed,
                "evidence": {
                    "seed_a": base_seed,
                    "seed_b": 314,
                    "run_a": sig_same_1,
                    "run_b": sig_diff,
                },
            },
        ],
        "runs": {
            "same_seed_a": result_same_1.to_dict(),
            "same_seed_b": result_same_2.to_dict(),
            "different_seed": result_diff.to_dict(),
        },
        "provenance": {
            "git_commit": _git_commit(workspace_root),
            "container_image_digest": _container_image_digest(),
            "config_hashes": {
                "same_seed_a": config_same_1.get_config_hash(),
                "same_seed_b": config_same_2.get_config_hash(),
                "different_seed": config_diff.get_config_hash(),
            },
            "seeds": {
                "same_seed_a": config_same_1.random_seed,
                "same_seed_b": config_same_2.random_seed,
                "different_seed": config_diff.random_seed,
            },
            "timestamp": generated_at,
        },
    }

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    artifact_file = artifact_dir / f"claim_matrix_{stamp}.json"
    artifact_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    markdown = [
        "# Claim Matrix",
        "",
        f"Generated: `{generated_at}`",
        "",
        "| Claim ID | Description | Status |",
        "| --- | --- | --- |",
    ]
    for claim in payload["claims"]:
        status = "PASS" if claim["passed"] else "FAIL"
        markdown.append(f"| {claim['claim_id']} | {claim['description']} | {status} |")

    (docs_dir / "claim_matrix.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate claim-matrix evidence artifacts")
    parser.add_argument("--mode", choices=["dev", "test", "prod"], default="test")
    parser.add_argument("--output", default=str(Path("artifacts") / "claim_matrix"))
    args = parser.parse_args()

    output_dir = Path(args.output)
    if not output_dir.is_absolute():
        output_dir = Path(__file__).resolve().parents[2] / args.output

    payload = asyncio.run(_run(args.mode, output_dir))

    failing = [c for c in payload["claims"] if not c["passed"]]
    if failing:
        print("Claim checks failed:")
        for claim in failing:
            print(f"- {claim['claim_id']}: {claim['description']}")
        return 1

    print("Claim matrix generated successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
