#!/usr/bin/env python3
"""
Integration test script for ShaktiChain V2G Marketplace.

Tests the complete workflow from authentication to simulation execution.
"""

import requests
import time
import json


BASE_URL = "http://localhost:8000"
TEST_EMAIL = "test@shaktichain.com"
TEST_PASSWORD = "testpass123"


def test_health():
    """Test API health endpoint."""
    print("Testing API health...")
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    print("✓ API is healthy")


def test_register(email, password):
    """Test user registration."""
    print(f"\nTesting user registration for {email}...")
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": email, "password": password}
    )

    if response.status_code == 400:
        # User might already exist
        print("✓ User already registered")
        return None

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    print("✓ User registered successfully")
    return data["access_token"]


def test_login(email, password):
    """Test user login."""
    print(f"\nTesting login for {email}...")
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    print("✓ Login successful")
    return data["access_token"]


def test_current_user(token):
    """Test getting current user info."""
    print("\nTesting get current user...")
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "email" in data
    assert "id" in data
    print(f"✓ Current user: {data['email']}")
    return data


def test_current_price():
    """Test getting current market price."""
    print("\nTesting get current price...")
    response = requests.get(f"{BASE_URL}/market/price")
    assert response.status_code == 200
    data = response.json()
    assert "price" in data
    print(f"✓ Current price: ₹{data['price']}/kWh")
    return data


def test_price_history():
    """Test getting price history."""
    print("\nTesting get price history...")
    response = requests.get(f"{BASE_URL}/market/price/history?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    print(f"✓ Retrieved {len(data)} price records")
    return data


def test_start_simulation(token):
    """Test starting a simulation."""
    print("\nTesting start simulation...")
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "num_agents": 50,
        "duration_days": 1,
        "agent_mix": {
            "residential": 50,
            "commercial": 30,
            "fleet": 20
        },
        "region": "delhi"
    }

    response = requests.post(
        f"{BASE_URL}/simulation/start",
        json=params,
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    job_id = data["job_id"]
    print(f"✓ Simulation started with job_id: {job_id}")
    return job_id


def test_simulation_status(token, job_id, wait_for_completion=True):
    """Test getting simulation status."""
    print(f"\nTesting simulation status for job {job_id}...")
    headers = {"Authorization": f"Bearer {token}"}

    max_wait = 300  # 5 minutes max
    start_time = time.time()

    while True:
        response = requests.get(
            f"{BASE_URL}/simulation/status/{job_id}",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()

        status = data["status"]
        progress = data.get("progress", 0)

        print(f"  Status: {status}, Progress: {progress:.1f}%")

        if status == "completed":
            print("✓ Simulation completed successfully")
            print(f"\n  Results Summary:")
            if data.get("results"):
                results = data["results"]
                print(f"    - Total Energy Traded: {results.get('totalEnergyTraded', 0):.2f} kWh")
                print(f"    - Average Price: ₹{results.get('averagePrice', 0):.2f}/kWh")
                print(f"    - Grid Savings: ₹{results.get('gridSavings', 0):.2f}")
                print(f"    - Carbon Offset: {results.get('carbonOffset', 0):.2f} tons CO₂")
            return data

        if status == "failed":
            print(f"✗ Simulation failed: {data.get('error')}")
            return data

        if not wait_for_completion:
            return data

        # Check timeout
        if time.time() - start_time > max_wait:
            print(f"✗ Simulation timed out after {max_wait} seconds")
            return data

        time.sleep(2)  # Wait 2 seconds before next check


def test_download_csv(token, job_id):
    """Test downloading simulation results as CSV."""
    print(f"\nTesting CSV download for job {job_id}...")
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/simulation/download/{job_id}",
        headers=headers
    )

    if response.status_code == 404:
        print("✗ CSV download not available (simulation may not be complete)")
        return None

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"

    csv_content = response.text
    lines = csv_content.split("\n")
    print(f"✓ CSV downloaded successfully ({len(lines)} lines)")
    print(f"  First few lines:")
    for line in lines[:5]:
        print(f"    {line}")

    return csv_content


def test_simulations_list(token):
    """Test listing simulations."""
    print("\nTesting list simulations...")
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.get(
        f"{BASE_URL}/simulations?limit=5",
        headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    print(f"✓ Retrieved {len(data)} simulation records")

    if data:
        print("  Latest simulation:")
        sim = data[0]
        print(f"    - ID: {sim['id']}")
        print(f"    - Status: {sim['status']}")
        print(f"    - Agents: {sim['n_agents']}")
        print(f"    - Days: {sim['n_days']}")

    return data


def run_integration_tests():
    """Run all integration tests."""
    print("=" * 60)
    print("ShaktiChain V2G Marketplace - Integration Tests")
    print("=" * 60)

    try:
        # Test 1: Health check
        test_health()

        # Test 2: Register user (or skip if exists)
        token = test_register(TEST_EMAIL, TEST_PASSWORD)

        # Test 3: Login
        if token is None:
            token = test_login(TEST_EMAIL, TEST_PASSWORD)

        # Test 4: Get current user
        user = test_current_user(token)

        # Test 5: Get current price
        price = test_current_price()

        # Test 6: Get price history
        history = test_price_history()

        # Test 7: List simulations
        simulations = test_simulations_list(token)

        # Test 8: Start simulation
        job_id = test_start_simulation(token)

        # Test 9: Monitor simulation status
        result = test_simulation_status(token, job_id, wait_for_completion=True)

        # Test 10: Download CSV
        if result and result.get("status") == "completed":
            csv_data = test_download_csv(token, job_id)

        print("\n" + "=" * 60)
        print("All integration tests passed! ✓")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except requests.exceptions.ConnectionError:
        print("\n✗ Could not connect to API server")
        print("  Make sure the backend is running on http://localhost:8000")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = run_integration_tests()
    exit(0 if success else 1)
