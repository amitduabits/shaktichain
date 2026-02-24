"""Containerized integration smoke for SHAKTI-CHAIN stack."""

from __future__ import annotations

import hashlib
import os
import sys
import time
from datetime import datetime, timezone

import httpx


BACKEND_URL = os.getenv("BACKEND_URL", "http://backend-test-api:8000")
GRAPH_QUERY_URL = os.getenv("GRAPH_QUERY_URL", "http://graph-node:8000/subgraphs/name/shakti-chain/shakti-chain")
TIMEOUT_SECONDS = 180


def wait_for_health(client: httpx.Client, timeout: int = 60) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            res = client.get(f"{BACKEND_URL}/health", timeout=5)
            if res.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("Backend did not become healthy in time")


def commit_hash(round_id: str, prosumer_id: str, side: str, quantity: float, price: float, nonce: str) -> str:
    payload = f"{round_id}|{prosumer_id}|{side}|{quantity:.6f}|{price:.6f}|{nonce}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    with httpx.Client(timeout=20.0) as client:
        wait_for_health(client)

        email = f"integration_{int(time.time())}@example.com"
        register = client.post(
            f"{BACKEND_URL}/auth/register",
            json={"email": email, "password": "password123"},
        )
        register.raise_for_status()
        token = register.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Start simulation and wait to completion.
        start = client.post(
            f"{BACKEND_URL}/simulation/start",
            headers=headers,
            json={
                "num_agents": 80,
                "duration_days": 1,
                "agent_mix": {"residential": 50, "commercial": 30, "fleet": 20},
                "region": "delhi",
            },
        )
        start.raise_for_status()
        job_id = start.json()["job_id"]

        started_at = time.time()
        completed = False
        while time.time() - started_at < TIMEOUT_SECONDS:
            status = client.get(f"{BACKEND_URL}/simulation/status/{job_id}", headers=headers)
            status.raise_for_status()
            payload = status.json()
            if payload["status"] == "completed":
                completed = True
                break
            if payload["status"] == "failed":
                raise RuntimeError(f"Simulation failed: {payload.get('error')}")
            time.sleep(2)

        if not completed:
            raise RuntimeError("Simulation did not complete before timeout")

        csv_download = client.get(f"{BACKEND_URL}/simulation/download/{job_id}", headers=headers)
        csv_download.raise_for_status()

        # Commit-reveal-settle flow.
        price = client.get(f"{BACKEND_URL}/market/price")
        price.raise_for_status()

        buy_nonce = "buy-nonce-1"
        sell_nonce = "sell-nonce-1"

        first_round_id = f"round-{int(time.time())}"
        buy_price = 7.1
        sell_price = 6.5

        buy_hash = commit_hash(first_round_id, "prosumer_A", "buy", 20.0, buy_price, buy_nonce)
        commit_buy = client.post(
            f"{BACKEND_URL}/auction/commit",
            headers=headers,
            json={
                "round_id": first_round_id,
                "prosumer_id": "prosumer_A",
                "side": "buy",
                "quantity": 20.0,
                "commit_hash": buy_hash,
                "reveal_window_minutes": 1,
            },
        )
        commit_buy.raise_for_status()
        buy_order_id = commit_buy.json()["order_id"]

        sell_hash = commit_hash(first_round_id, "prosumer_B", "sell", 20.0, sell_price, sell_nonce)
        commit_sell = client.post(
            f"{BACKEND_URL}/auction/commit",
            headers=headers,
            json={
                "round_id": first_round_id,
                "prosumer_id": "prosumer_B",
                "side": "sell",
                "quantity": 20.0,
                "commit_hash": sell_hash,
                "reveal_window_minutes": 1,
            },
        )
        commit_sell.raise_for_status()
        sell_order_id = commit_sell.json()["order_id"]

        reveal_buy = client.post(
            f"{BACKEND_URL}/auction/reveal",
            headers=headers,
            json={
                "round_id": first_round_id,
                "order_id": buy_order_id,
                "prosumer_id": "prosumer_A",
                "side": "buy",
                "quantity": 20.0,
                "price": buy_price,
                "nonce": buy_nonce,
            },
        )
        reveal_buy.raise_for_status()

        reveal_sell = client.post(
            f"{BACKEND_URL}/auction/reveal",
            headers=headers,
            json={
                "round_id": first_round_id,
                "order_id": sell_order_id,
                "prosumer_id": "prosumer_B",
                "side": "sell",
                "quantity": 20.0,
                "price": sell_price,
                "nonce": sell_nonce,
            },
        )
        reveal_sell.raise_for_status()

        settle = client.post(
            f"{BACKEND_URL}/auction/settle-batch",
            headers=headers,
            json={"round_id": first_round_id, "max_matches": 20},
        )
        settle.raise_for_status()

        round_status = client.get(f"{BACKEND_URL}/auction/round/{first_round_id}", headers=headers)
        round_status.raise_for_status()
        if round_status.json().get("status") != "settled":
            raise RuntimeError("Auction round did not settle")

        orderbook = client.get(f"{BACKEND_URL}/auction/orderbook/{first_round_id}", headers=headers)
        orderbook.raise_for_status()

        prosumers = client.get(f"{BACKEND_URL}/prosumers", headers=headers)
        prosumers.raise_for_status()

        # Optional graph check; non-fatal if subgraph is not yet deployed.
        try:
            graph_res = client.post(
                GRAPH_QUERY_URL,
                json={"query": "{ _meta { block { number } } }"},
                timeout=10,
            )
            if graph_res.status_code >= 500:
                raise RuntimeError(graph_res.text)
        except Exception as exc:
            print(f"Graph query skipped: {exc}")

    print(
        f"Integration smoke passed at {datetime.now(timezone.utc).isoformat()} for job {job_id} and round {first_round_id}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Integration smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
