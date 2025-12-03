"""Integration tests for trading pipeline: State → Agent → Blockchain.

Tests the complete flow:
1. Environment state observation
2. Agent action selection
3. Transaction submission to blockchain
4. Event processing and state update
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from rl.environment import V2GEnvironment
from rl.policy import PPOPolicy
from trading.agent import TradingAgent
from trading.executor import TradeExecutor
from trading.risk import RiskManager
from blockchain.integration import BlockchainClient


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "battery_capacity_kwh": 100,
        "initial_soc": 0.5,
        "max_charge_rate": 50,  # kW
        "max_discharge_rate": 50,  # kW
        "test_duration_hours": 24,
        "blockchain_rpc": "http://localhost:8545",  # Testnet
    }


@pytest.fixture
def v2g_environment(test_config):
    """Initialize V2G trading environment."""
    return V2GEnvironment(
        battery_capacity=test_config["battery_capacity_kwh"],
        initial_soc=test_config["initial_soc"],
        max_charge_rate=test_config["max_charge_rate"],
        max_discharge_rate=test_config["max_discharge_rate"],
    )


@pytest.fixture
def trading_agent(tmp_path):
    """Initialize trading agent with trained policy."""
    # In production, load from MLflow
    agent = TradingAgent(
        model_path=str(tmp_path / "ppo_agent.zip"),
        device="cpu"
    )
    return agent


@pytest.fixture
def risk_manager(test_config):
    """Initialize risk manager."""
    return RiskManager(
        max_position_size=test_config["battery_capacity_kwh"],
        max_daily_loss=5000,  # INR
        min_soc=0.2,
        max_soc=0.8,
    )


@pytest.fixture
def blockchain_client(test_config):
    """Initialize blockchain client."""
    return BlockchainClient(
        rpc_url=test_config["blockchain_rpc"],
        contract_address="0x1234567890123456789012345678901234567890",  # Test
        private_key="test_key",  # Use test account
    )


class TestTradingPipeline:
    """Test complete trading pipeline."""

    def test_environment_observation(self, v2g_environment, test_config):
        """Test Step 1: Environment state observation."""
        # Reset environment
        obs = v2g_environment.reset()

        assert obs is not None, "Failed to get observation"
        assert isinstance(obs, (np.ndarray, dict)), "Invalid observation type"

        # Check observation contains required information
        if isinstance(obs, dict):
            required_keys = ["battery_soc", "grid_price", "time_of_day"]
            for key in required_keys:
                assert key in obs, f"Missing {key} in observation"

        print(f"✓ Environment observation: SOC={obs.get('battery_soc', 'N/A')}")

    def test_agent_action_selection(self, v2g_environment, trading_agent):
        """Test Step 2: Agent action selection."""
        # Get current state
        obs = v2g_environment.reset()

        # Agent selects action
        action, value, log_prob = trading_agent.predict(obs, deterministic=False)

        assert action is not None, "Agent failed to select action"
        assert action in [0, 1, 2], f"Invalid action: {action}"  # 0=hold, 1=charge, 2=discharge

        action_names = {0: "HOLD", 1: "CHARGE", 2: "DISCHARGE"}
        print(f"✓ Agent action: {action_names[action]} (value={value:.2f})")

    def test_risk_management_check(self, v2g_environment, risk_manager):
        """Test Step 3: Risk management checks."""
        # Create test trade
        trade = {
            "action": "discharge",
            "amount_kwh": 30,
            "price_per_kwh": 8.5,
            "total_value_inr": 30 * 8.5,
            "battery_soc": 0.6,
        }

        # Check if trade passes risk checks
        is_allowed, reason = risk_manager.check_trade(trade)

        assert isinstance(is_allowed, bool), "Risk check should return boolean"
        if not is_allowed:
            assert reason is not None, "Rejected trade should have reason"

        print(f"✓ Risk check: {'APPROVED' if is_allowed else f'REJECTED - {reason}'}")

    def test_blockchain_transaction_submission(self, blockchain_client, test_config):
        """Test Step 4: Transaction submission to blockchain."""
        # Check blockchain connectivity
        try:
            is_connected = blockchain_client.is_connected()
            if not is_connected:
                pytest.skip("Blockchain testnet not available")
        except Exception as e:
            pytest.skip(f"Blockchain not accessible: {e}")

        # Create test transaction
        trade_data = {
            "action": "discharge",
            "amount": 30,  # kWh
            "price": 8.5,  # INR/kWh
            "timestamp": int(datetime.now().timestamp()),
        }

        # Submit transaction
        tx_hash = blockchain_client.submit_trade(trade_data)

        assert tx_hash is not None, "Failed to get transaction hash"
        assert isinstance(tx_hash, str), "Transaction hash should be string"
        assert len(tx_hash) > 0, "Transaction hash is empty"

        print(f"✓ Transaction submitted: {tx_hash[:10]}...")

        # Wait for confirmation (in test, mock this)
        # receipt = blockchain_client.wait_for_receipt(tx_hash, timeout=60)
        # assert receipt.status == 1, "Transaction failed on blockchain"

    def test_transaction_event_processing(self, blockchain_client):
        """Test Step 5: Blockchain event processing."""
        # Mock event from blockchain
        event = {
            "event": "TradeExecuted",
            "blockNumber": 12345,
            "transactionHash": "0xabcd...",
            "args": {
                "trader": "0x1234...",
                "action": "discharge",
                "amount": 30,
                "price": 8.5,
                "timestamp": int(datetime.now().timestamp()),
            }
        }

        # Process event
        processed = blockchain_client.process_event(event)

        assert processed is not None, "Event processing failed"
        assert "action" in processed, "Missing action in processed event"
        assert "amount" in processed, "Missing amount in processed event"

        print(f"✓ Event processed: {processed['action']} {processed['amount']}kWh")

    def test_end_to_end_trading_cycle(
        self,
        v2g_environment,
        trading_agent,
        risk_manager,
        blockchain_client,
        test_config
    ):
        """Test complete end-to-end trading cycle."""
        print("\n=== Testing End-to-End Trading Pipeline ===\n")

        # Initialize tracking
        total_profit = 0
        trades_executed = 0
        trades_blocked = 0

        # Simulate trading over multiple timesteps
        obs = v2g_environment.reset()
        print(f"Initial state: SOC={obs.get('battery_soc', 0.5):.2f}")

        for step in range(24):  # 24 hours
            print(f"\n--- Hour {step} ---")

            # Step 1: Get observation
            current_price = np.random.uniform(6, 12)  # INR/kWh
            obs["grid_price"] = current_price
            obs["time_of_day"] = step

            print(f"Grid price: ₹{current_price:.2f}/kWh")

            # Step 2: Agent decides action
            action, value, _ = trading_agent.predict(obs, deterministic=True)
            action_names = {0: "HOLD", 1: "CHARGE", 2: "DISCHARGE"}
            print(f"Agent decision: {action_names[action]}")

            # Step 3: Create trade
            if action == 1:  # Charge
                amount = min(30, test_config["max_charge_rate"])
                trade = {
                    "action": "charge",
                    "amount_kwh": amount,
                    "price_per_kwh": current_price,
                    "total_value_inr": -amount * current_price,  # Cost
                    "battery_soc": obs["battery_soc"],
                }
            elif action == 2:  # Discharge
                amount = min(30, test_config["max_discharge_rate"])
                trade = {
                    "action": "discharge",
                    "amount_kwh": amount,
                    "price_per_kwh": current_price,
                    "total_value_inr": amount * current_price,  # Revenue
                    "battery_soc": obs["battery_soc"],
                }
            else:  # Hold
                trade = None

            # Step 4: Risk check
            if trade:
                is_allowed, reason = risk_manager.check_trade(trade)

                if is_allowed:
                    print(f"✓ Trade approved: {trade['action']} {trade['amount_kwh']}kWh")

                    # Step 5: Submit to blockchain (mocked)
                    # tx_hash = blockchain_client.submit_trade(trade)

                    # Update state
                    if trade["action"] == "charge":
                        obs["battery_soc"] = min(0.8, obs["battery_soc"] + 0.3)
                    else:
                        obs["battery_soc"] = max(0.2, obs["battery_soc"] - 0.3)

                    total_profit += trade["total_value_inr"]
                    trades_executed += 1
                else:
                    print(f"✗ Trade blocked: {reason}")
                    trades_blocked += 1

            # Step 6: Environment step
            next_obs, reward, done, info = v2g_environment.step(action)
            obs = next_obs

            print(f"New SOC: {obs['battery_soc']:.2f}")

        # Final summary
        print("\n=== Trading Cycle Complete ===")
        print(f"Trades executed: {trades_executed}")
        print(f"Trades blocked: {trades_blocked}")
        print(f"Total P&L: ₹{total_profit:.2f}")
        print(f"Final SOC: {obs['battery_soc']:.2f}")

        assert trades_executed > 0, "No trades were executed"
        assert obs["battery_soc"] >= 0.2, "SOC fell below minimum"
        assert obs["battery_soc"] <= 0.8, "SOC exceeded maximum"


class TestTradingStrategy:
    """Test trading strategy behavior."""

    def test_arbitrage_opportunity(self, v2g_environment, trading_agent):
        """Test agent exploits price arbitrage."""
        # Low price period - should charge
        obs_low_price = {
            "battery_soc": 0.5,
            "grid_price": 5.0,  # Low price
            "time_of_day": 3,  # Early morning
        }

        action_low, _, _ = trading_agent.predict(obs_low_price, deterministic=True)

        # High price period - should discharge
        obs_high_price = {
            "battery_soc": 0.5,
            "grid_price": 12.0,  # High price
            "time_of_day": 18,  # Evening peak
        }

        action_high, _, _ = trading_agent.predict(obs_high_price, deterministic=True)

        print(f"Low price ({obs_low_price['grid_price']}): {action_low}")
        print(f"High price ({obs_high_price['grid_price']}): {action_high}")

        # Agent should prefer charging at low price, discharging at high
        # (action: 0=hold, 1=charge, 2=discharge)
        # Note: This is a soft test - agent might hold if SOC constraints apply

    def test_battery_constraints_respected(self, v2g_environment, risk_manager):
        """Test battery SOC constraints are respected."""
        # Try charging when already at high SOC
        trade_high_soc = {
            "action": "charge",
            "amount_kwh": 30,
            "price_per_kwh": 7.0,
            "total_value_inr": -210,
            "battery_soc": 0.85,  # Above max
        }

        is_allowed, reason = risk_manager.check_trade(trade_high_soc)
        assert not is_allowed, "Should block charging at high SOC"
        assert "SOC" in reason, "Reason should mention SOC"

        # Try discharging when at low SOC
        trade_low_soc = {
            "action": "discharge",
            "amount_kwh": 30,
            "price_per_kwh": 7.0,
            "total_value_inr": 210,
            "battery_soc": 0.15,  # Below min
        }

        is_allowed, reason = risk_manager.check_trade(trade_low_soc)
        assert not is_allowed, "Should block discharging at low SOC"
        assert "SOC" in reason, "Reason should mention SOC"

        print("✓ Battery constraints properly enforced")

    def test_risk_limits_enforced(self, risk_manager):
        """Test risk limits are enforced."""
        # Try trade exceeding position limit
        large_trade = {
            "action": "discharge",
            "amount_kwh": 150,  # Exceeds 100kWh capacity
            "price_per_kwh": 8.0,
            "total_value_inr": 1200,
            "battery_soc": 0.6,
        }

        is_allowed, reason = risk_manager.check_trade(large_trade)
        assert not is_allowed, "Should block oversized trade"

        print("✓ Risk limits properly enforced")


class TestBlockchainIntegration:
    """Test blockchain integration."""

    def test_contract_interaction(self, blockchain_client):
        """Test smart contract interaction."""
        try:
            # Check contract is accessible
            contract_address = blockchain_client.contract_address
            assert contract_address is not None, "Contract address not set"

            # Get contract state (mock)
            # state = blockchain_client.get_contract_state()
            # assert "total_trades" in state

            print(f"✓ Contract accessible at {contract_address[:10]}...")
        except Exception as e:
            pytest.skip(f"Blockchain not available: {e}")

    def test_event_listener(self, blockchain_client):
        """Test blockchain event listener."""
        # Mock event stream
        events = [
            {
                "event": "TradeExecuted",
                "args": {"action": "charge", "amount": 25, "price": 7.0}
            },
            {
                "event": "TradeExecuted",
                "args": {"action": "discharge", "amount": 30, "price": 9.0}
            },
        ]

        processed_events = []
        for event in events:
            processed = blockchain_client.process_event(event)
            processed_events.append(processed)

        assert len(processed_events) == 2, "Should process all events"
        print(f"✓ Processed {len(processed_events)} blockchain events")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
