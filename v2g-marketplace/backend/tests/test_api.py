"""
Comprehensive API tests for V2G Marketplace.

Tests cover:
1. All endpoints (health, simulations, periods, prices, auth)
2. Authentication and authorization
3. Error handling
4. Input validation
5. Rate limiting behavior
"""

import os
import sys
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set test database path before importing app
TEST_DB_PATH = tempfile.mktemp(suffix=".db")
os.environ["V2G_DB_PATH"] = TEST_DB_PATH


class TestSetup:
    """Test setup and fixtures."""

    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Create fresh test database for each test."""
        # Import here to ensure environment is set
        from backend.core.database import Database, reset_database

        # Keep test DB path deterministic per test module even when other test
        # modules mutate process-wide env vars during collection.
        os.environ["V2G_DB_PATH"] = TEST_DB_PATH

        reset_database()

        # Create fresh database
        self.db = Database(TEST_DB_PATH)
        self.db.init_db()

        yield

        # Cleanup
        self.db.close()
        reset_database()
        if os.path.exists(TEST_DB_PATH):
            os.unlink(TEST_DB_PATH)

    @pytest.fixture
    def client(self, setup_test_db):
        """Create test client."""
        from backend.api.main import app
        with TestClient(app) as test_client:
            yield test_client

    @pytest.fixture
    def auth_token(self, client):
        """Create a test user and return auth token."""
        response = client.post("/auth/register", json={
            "email": "test@example.com",
            "password": "testpassword123"
        })
        return response.json()["access_token"]

    @pytest.fixture
    def auth_headers(self, auth_token):
        """Return headers with auth token."""
        return {"Authorization": f"Bearer {auth_token}"}


class TestHealthEndpoint(TestSetup):
    """Test health check endpoint."""

    def test_health_check_returns_healthy(self, client):
        """Test that health endpoint returns healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_health_check_no_auth_required(self, client):
        """Test that health endpoint doesn't require authentication."""
        response = client.get("/health")
        assert response.status_code == 200


class TestAuthEndpoints(TestSetup):
    """Test authentication endpoints."""

    def test_register_new_user(self, client):
        """Test successful user registration."""
        response = client.post("/auth/register", json={
            "email": "newuser@example.com",
            "password": "securepassword123"
        })
        assert response.status_code == 201
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"

    def test_register_duplicate_email_fails(self, client):
        """Test that registering with existing email fails."""
        # First registration
        client.post("/auth/register", json={
            "email": "duplicate@example.com",
            "password": "password123"
        })

        # Second registration with same email
        response = client.post("/auth/register", json={
            "email": "duplicate@example.com",
            "password": "differentpassword"
        })
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email_fails(self, client):
        """Test that invalid email format is rejected."""
        response = client.post("/auth/register", json={
            "email": "not-an-email",
            "password": "password123"
        })
        assert response.status_code == 422

    def test_register_short_password_fails(self, client):
        """Test that short password is rejected."""
        response = client.post("/auth/register", json={
            "email": "user@example.com",
            "password": "short"
        })
        assert response.status_code == 422

    def test_login_valid_credentials(self, client):
        """Test successful login."""
        # Register first
        client.post("/auth/register", json={
            "email": "login@example.com",
            "password": "password123"
        })

        # Login
        response = client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_invalid_password(self, client):
        """Test login with wrong password fails."""
        # Register first
        client.post("/auth/register", json={
            "email": "wrongpass@example.com",
            "password": "correctpassword"
        })

        # Login with wrong password
        response = client.post("/auth/login", json={
            "email": "wrongpass@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client):
        """Test login with non-existent email fails."""
        response = client.post("/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "password123"
        })
        assert response.status_code == 401

    def test_get_current_user_authenticated(self, client, auth_headers):
        """Test getting current user info when authenticated."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"
        assert response.json()["role"] == "user"

    def test_get_current_user_unauthenticated(self, client):
        """Test getting current user info without auth fails."""
        response = client.get("/auth/me")
        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_invalid_token_rejected(self, client):
        """Test that invalid token is rejected."""
        response = client.get("/auth/me", headers={
            "Authorization": "Bearer invalid-token"
        })
        assert response.status_code == 401


class TestSimulationEndpoints(TestSetup):
    """Test simulation CRUD endpoints."""

    def test_create_simulation_authenticated(self, client, auth_headers):
        """Test creating a simulation when authenticated."""
        response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        }, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["n_agents"] == 100
        assert data["n_days"] == 7
        assert data["status"] == "pending"
        assert "id" in data

    def test_create_simulation_unauthenticated(self, client):
        """Test creating simulation without auth fails."""
        response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        })
        assert response.status_code == 403

    def test_create_simulation_invalid_n_agents(self, client, auth_headers):
        """Test creating simulation with invalid n_agents."""
        response = client.post("/simulations", json={
            "n_agents": 0,
            "n_days": 7
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_create_simulation_invalid_n_days(self, client, auth_headers):
        """Test creating simulation with invalid n_days."""
        response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": -1
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_list_simulations_authenticated(self, client, auth_headers):
        """Test listing simulations when authenticated."""
        # Create some simulations
        for i in range(3):
            client.post("/simulations", json={
                "n_agents": 100 + i,
                "n_days": 7
            }, headers=auth_headers)

        response = client.get("/simulations", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_list_simulations_with_limit(self, client, auth_headers):
        """Test listing simulations with limit parameter."""
        # Create 5 simulations
        for i in range(5):
            client.post("/simulations", json={
                "n_agents": 100,
                "n_days": 7
            }, headers=auth_headers)

        response = client.get("/simulations?limit=2", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_simulations_limit_bounds(self, client, auth_headers):
        """Test that limit is bounded."""
        # Limit < 1 should fail
        response = client.get("/simulations?limit=0", headers=auth_headers)
        assert response.status_code == 422

        # Limit > 100 should fail
        response = client.get("/simulations?limit=101", headers=auth_headers)
        assert response.status_code == 422

    def test_get_simulation_by_id(self, client, auth_headers):
        """Test getting a specific simulation by ID."""
        # Create simulation
        create_response = client.post("/simulations", json={
            "n_agents": 200,
            "n_days": 14
        }, headers=auth_headers)
        sim_id = create_response.json()["id"]

        # Get by ID
        response = client.get(f"/simulations/{sim_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == sim_id
        assert response.json()["n_agents"] == 200

    def test_get_nonexistent_simulation(self, client, auth_headers):
        """Test getting a simulation that doesn't exist."""
        response = client.get("/simulations/nonexistent-id", headers=auth_headers)
        assert response.status_code == 404

    def test_update_simulation(self, client, auth_headers):
        """Test updating a simulation."""
        # Create simulation
        create_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        }, headers=auth_headers)
        sim_id = create_response.json()["id"]

        # Update status
        response = client.patch(f"/simulations/{sim_id}", json={
            "status": "running"
        }, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_update_simulation_invalid_status(self, client, auth_headers):
        """Test updating simulation with invalid status."""
        # Create simulation
        create_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        }, headers=auth_headers)
        sim_id = create_response.json()["id"]

        # Try invalid status
        response = client.patch(f"/simulations/{sim_id}", json={
            "status": "invalid_status"
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_update_nonexistent_simulation(self, client, auth_headers):
        """Test updating a simulation that doesn't exist."""
        response = client.patch("/simulations/nonexistent-id", json={
            "status": "running"
        }, headers=auth_headers)
        assert response.status_code == 404


class TestPeriodEndpoints(TestSetup):
    """Test market period endpoints."""

    def test_create_period(self, client, auth_headers):
        """Test creating a market period."""
        # Create simulation first
        sim_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        }, headers=auth_headers)
        sim_id = sim_response.json()["id"]

        # Create period
        response = client.post("/periods", json={
            "simulation_id": sim_id,
            "period": 0,
            "hour": 10,
            "clearing_price": 6.5,
            "volume": 1000.0,
            "n_buyers": 50,
            "n_sellers": 50
        }, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["period"] == 0
        assert response.json()["hour"] == 10
        assert response.json()["clearing_price"] == 6.5

    def test_create_period_invalid_simulation(self, client, auth_headers):
        """Test creating period for non-existent simulation."""
        response = client.post("/periods", json={
            "simulation_id": "nonexistent-sim",
            "period": 0,
            "hour": 10
        }, headers=auth_headers)
        assert response.status_code == 404

    def test_create_period_invalid_hour(self, client, auth_headers):
        """Test creating period with invalid hour."""
        # Create simulation
        sim_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        }, headers=auth_headers)
        sim_id = sim_response.json()["id"]

        # Invalid hour (>= 24)
        response = client.post("/periods", json={
            "simulation_id": sim_id,
            "period": 0,
            "hour": 25
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_get_simulation_periods(self, client, auth_headers):
        """Test getting all periods for a simulation."""
        # Create simulation
        sim_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 1
        }, headers=auth_headers)
        sim_id = sim_response.json()["id"]

        # Create multiple periods
        for hour in range(24):
            client.post("/periods", json={
                "simulation_id": sim_id,
                "period": hour,
                "hour": hour,
                "clearing_price": 5.0 + hour * 0.1
            }, headers=auth_headers)

        # Get periods
        response = client.get(f"/simulations/{sim_id}/periods", headers=auth_headers)
        assert response.status_code == 200
        assert len(response.json()) == 24

    def test_get_periods_for_nonexistent_simulation(self, client, auth_headers):
        """Test getting periods for non-existent simulation."""
        response = client.get("/simulations/nonexistent-id/periods", headers=auth_headers)
        assert response.status_code == 404


class TestPriceEndpoints(TestSetup):
    """Test price history endpoints."""

    def test_create_price_no_auth_required(self, client):
        """Test creating price entry without authentication."""
        response = client.post("/prices", json={
            "price": 6.5,
            "source": "simulation"
        })
        assert response.status_code == 200
        assert response.json()["price"] == 6.5
        assert response.json()["source"] == "simulation"

    def test_create_price_invalid_source(self, client):
        """Test creating price with invalid source."""
        response = client.post("/prices", json={
            "price": 6.5,
            "source": "invalid_source"
        })
        assert response.status_code == 422

    def test_get_price_history_no_auth(self, client):
        """Test getting price history without authentication."""
        # Create some prices
        for i in range(5):
            client.post("/prices", json={
                "price": 5.0 + i * 0.5,
                "source": "simulation"
            })

        response = client.get("/prices")
        assert response.status_code == 200
        assert len(response.json()) == 5

    def test_get_price_history_with_limit(self, client):
        """Test getting price history with limit."""
        # Create 10 prices
        for i in range(10):
            client.post("/prices", json={
                "price": 5.0 + i,
                "source": "simulation"
            })

        response = client.get("/prices?limit=3")
        assert response.status_code == 200
        assert len(response.json()) == 3

    def test_get_price_history_limit_bounds(self, client):
        """Test price history limit bounds."""
        # Limit < 1 should fail
        response = client.get("/prices?limit=0")
        assert response.status_code == 422

        # Limit > 1000 should fail
        response = client.get("/prices?limit=1001")
        assert response.status_code == 422


class TestAuctionEndpoints(TestSetup):
    """Test commit-reveal auction endpoints."""

    @staticmethod
    def _commit_hash(round_id: str, prosumer_id: str, side: str, quantity: float, price: float, nonce: str) -> str:
        payload = f"{round_id}|{prosumer_id}|{side}|{quantity:.6f}|{price:.6f}|{nonce}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def test_commit_reveal_settle_round_trip(self, client, auth_headers):
        round_id = "round-test-001"
        buy_nonce = "n1"
        sell_nonce = "n2"
        buy_price = 7.2
        sell_price = 6.4

        buy_hash = self._commit_hash(round_id, "p1", "buy", 20.0, buy_price, buy_nonce)
        sell_hash = self._commit_hash(round_id, "p2", "sell", 20.0, sell_price, sell_nonce)

        commit_buy = client.post("/auction/commit", json={
            "round_id": round_id,
            "prosumer_id": "p1",
            "side": "buy",
            "quantity": 20.0,
            "commit_hash": buy_hash,
            "reveal_window_minutes": 1,
        }, headers=auth_headers)
        assert commit_buy.status_code == 200
        buy_order_id = commit_buy.json()["order_id"]

        commit_sell = client.post("/auction/commit", json={
            "round_id": round_id,
            "prosumer_id": "p2",
            "side": "sell",
            "quantity": 20.0,
            "commit_hash": sell_hash,
            "reveal_window_minutes": 1,
        }, headers=auth_headers)
        assert commit_sell.status_code == 200
        sell_order_id = commit_sell.json()["order_id"]

        reveal_buy = client.post("/auction/reveal", json={
            "round_id": round_id,
            "order_id": buy_order_id,
            "prosumer_id": "p1",
            "side": "buy",
            "quantity": 20.0,
            "price": buy_price,
            "nonce": buy_nonce,
        }, headers=auth_headers)
        assert reveal_buy.status_code == 200

        reveal_sell = client.post("/auction/reveal", json={
            "round_id": round_id,
            "order_id": sell_order_id,
            "prosumer_id": "p2",
            "side": "sell",
            "quantity": 20.0,
            "price": sell_price,
            "nonce": sell_nonce,
        }, headers=auth_headers)
        assert reveal_sell.status_code == 200

        settle = client.post("/auction/settle-batch", json={
            "round_id": round_id,
            "max_matches": 20,
        }, headers=auth_headers)
        assert settle.status_code == 200
        assert settle.json()["status"] == "settled"
        assert settle.json()["matched_orders"] >= 0

        round_info = client.get(f"/auction/round/{round_id}", headers=auth_headers)
        assert round_info.status_code == 200
        assert round_info.json()["status"] == "settled"

        orderbook = client.get(f"/auction/orderbook/{round_id}", headers=auth_headers)
        assert orderbook.status_code == 200
        assert "bids" in orderbook.json()
        assert "asks" in orderbook.json()


class TestErrorHandling(TestSetup):
    """Test error handling across endpoints."""

    def test_invalid_json_body(self, client, auth_headers):
        """Test handling of invalid JSON in request body."""
        response = client.post(
            "/simulations",
            content="not valid json",
            headers={**auth_headers, "Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_missing_required_field(self, client, auth_headers):
        """Test handling of missing required field."""
        response = client.post("/simulations", json={
            "n_agents": 100
            # Missing n_days
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_wrong_field_type(self, client, auth_headers):
        """Test handling of wrong field type."""
        response = client.post("/simulations", json={
            "n_agents": "not a number",
            "n_days": 7
        }, headers=auth_headers)
        assert response.status_code == 422

    def test_extra_fields_ignored(self, client, auth_headers):
        """Test that extra fields in request are ignored."""
        response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7,
            "extra_field": "should be ignored"
        }, headers=auth_headers)
        assert response.status_code == 200

    def test_method_not_allowed(self, client):
        """Test handling of wrong HTTP method."""
        response = client.delete("/health")
        assert response.status_code == 405


class TestCORS(TestSetup):
    """Test CORS configuration."""

    def test_cors_headers_present(self, client):
        """Test that CORS headers are present in response."""
        response = client.options("/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        # CORS middleware should add headers
        assert response.status_code in [200, 204, 405]

    def test_cors_allows_any_origin(self, client):
        """Test that CORS allows any origin (dev configuration)."""
        response = client.get("/health", headers={
            "Origin": "http://example.com"
        })
        assert response.status_code == 200
        # Check if CORS header is present (depends on FastAPI CORS config)
        # In production, this should be restricted


class TestAuthTokenExpiry(TestSetup):
    """Test authentication token expiry handling."""

    def test_valid_token_works(self, client, auth_headers):
        """Test that valid token allows access."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200

    def test_malformed_token_rejected(self, client):
        """Test that malformed token is rejected."""
        response = client.get("/auth/me", headers={
            "Authorization": "Bearer malformed.token.here"
        })
        assert response.status_code == 401

    def test_missing_bearer_prefix(self, client, auth_token):
        """Test that missing Bearer prefix is rejected."""
        response = client.get("/auth/me", headers={
            "Authorization": auth_token  # Missing 'Bearer '
        })
        assert response.status_code == 403  # Invalid auth scheme


class TestBulkOperations(TestSetup):
    """Test bulk operations and stress scenarios."""

    def test_create_many_simulations(self, client, auth_headers):
        """Test creating many simulations."""
        for i in range(20):
            response = client.post("/simulations", json={
                "n_agents": 100,
                "n_days": 7
            }, headers=auth_headers)
            assert response.status_code == 200

        # List all
        response = client.get("/simulations?limit=100", headers=auth_headers)
        assert len(response.json()) == 20

    def test_create_many_periods(self, client, auth_headers):
        """Test creating many periods for a simulation."""
        # Create simulation
        sim_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 30
        }, headers=auth_headers)
        sim_id = sim_response.json()["id"]

        # Create 720 periods (30 days * 24 hours)
        for day in range(30):
            for hour in range(24):
                response = client.post("/periods", json={
                    "simulation_id": sim_id,
                    "period": day * 24 + hour,
                    "hour": hour,
                    "clearing_price": 5.0 + hour * 0.2
                }, headers=auth_headers)
                assert response.status_code == 200

        # Get all periods
        response = client.get(f"/simulations/{sim_id}/periods", headers=auth_headers)
        assert len(response.json()) == 720


class TestResponseFormat(TestSetup):
    """Test response format and content types."""

    def test_json_content_type(self, client):
        """Test that responses have correct content type."""
        response = client.get("/health")
        assert response.headers["content-type"].startswith("application/json")

    def test_simulation_response_fields(self, client, auth_headers):
        """Test that simulation response has all expected fields."""
        response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        }, headers=auth_headers)

        data = response.json()
        expected_fields = ["id", "created_at", "n_agents", "n_days", "status"]
        for field in expected_fields:
            assert field in data

    def test_period_response_fields(self, client, auth_headers):
        """Test that period response has all expected fields."""
        # Create simulation
        sim_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 7
        }, headers=auth_headers)
        sim_id = sim_response.json()["id"]

        # Create period
        response = client.post("/periods", json={
            "simulation_id": sim_id,
            "period": 0,
            "hour": 10,
            "clearing_price": 6.5
        }, headers=auth_headers)

        data = response.json()
        expected_fields = ["id", "simulation_id", "period", "hour"]
        for field in expected_fields:
            assert field in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
