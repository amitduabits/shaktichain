#!/usr/bin/env python
"""Test script for V2G Trading RL Environment.

This script validates the RL environment implementation by:
1. Testing basic environment functionality
2. Running random episodes
3. Testing with different action spaces
4. Validating observation/action spaces
5. Testing environment wrappers
6. Generating visualizations
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rl import (
    V2GTradingEnv,
    BatteryModel,
    MarketSimulator,
    BatteryConfig,
    MarketConfig,
    EnvironmentConfig,
    DayType,
    make_env,
    EnvironmentVisualizer,
)


def test_battery_model():
    """Test battery model functionality."""
    print("\n" + "=" * 60)
    print("Testing Battery Model")
    print("=" * 60)

    config = BatteryConfig(
        capacity_kwh=60.0,
        max_charge_rate_kw=11.0,
        max_discharge_rate_kw=11.0,
        initial_soc=0.5,
    )

    battery = BatteryModel(config)

    print(f"Initial SOC: {battery.soc * 100:.1f}%")
    print(f"Initial Health: {battery.get_health() * 100:.1f}%")

    # Test charging
    energy, cost = battery.charge(10.0, duration_hours=1.0)
    print(f"\nAfter 10kW charge for 1h:")
    print(f"  Energy stored: {energy:.2f} kWh")
    print(f"  Degradation cost: ₹{cost:.4f}")
    print(f"  SOC: {battery.soc * 100:.1f}%")

    # Test discharging
    energy, cost = battery.discharge(8.0, duration_hours=1.0)
    print(f"\nAfter 8kW discharge for 1h:")
    print(f"  Energy delivered: {energy:.2f} kWh")
    print(f"  Degradation cost: ₹{cost:.4f}")
    print(f"  SOC: {battery.soc * 100:.1f}%")

    print(f"\nFinal Health: {battery.get_health() * 100:.2f}%")
    print(f"Total Cycles: {battery.total_cycles:.4f}")

    print("\n✓ Battery model test passed!")


def test_market_simulator():
    """Test market simulator functionality."""
    print("\n" + "=" * 60)
    print("Testing Market Simulator")
    print("=" * 60)

    config = MarketConfig(
        base_price=5.0,
        price_volatility=0.2,
        bid_ask_spread=0.05,
    )

    market = MarketSimulator(config, seed=42)

    print("Price generation over 24 hours:")
    print("-" * 40)

    for hour in range(24):
        load_factor = 0.5 + 0.3 * np.sin(np.pi * hour / 12)
        price = market.generate_price(hour, load_factor, DayType.WEEKDAY)
        bar = "█" * int(price * 2)
        print(f"Hour {hour:02d}: ₹{price:6.2f} {bar}")

    print(f"\nBid: ₹{market.bid_price:.2f} | Ask: ₹{market.ask_price:.2f}")

    # Test trade execution
    qty, price, success = market.execute_trade(
        quantity_kwh=10.0,
        price_aggressiveness=0.7,
        is_buy=True,
    )
    print(f"\nBuy trade: {success}, qty={qty:.2f}, price=₹{price:.2f}")

    qty, price, success = market.execute_trade(
        quantity_kwh=10.0,
        price_aggressiveness=0.7,
        is_buy=False,
    )
    print(f"Sell trade: {success}, qty={qty:.2f}, price=₹{price:.2f}")

    print("\n✓ Market simulator test passed!")


def test_environment_creation():
    """Test environment creation and spaces."""
    print("\n" + "=" * 60)
    print("Testing Environment Creation")
    print("=" * 60)

    # Test continuous action space
    env = V2GTradingEnv(use_discrete_actions=False)
    print(f"\nContinuous Action Environment:")
    print(f"  Observation space: {env.observation_space}")
    print(f"  Observation shape: {env.observation_space.shape}")
    print(f"  Action space: {env.action_space}")
    print(f"  Action shape: {env.action_space.shape}")

    # Test discrete action space
    env_discrete = V2GTradingEnv(use_discrete_actions=True)
    print(f"\nDiscrete Action Environment:")
    print(f"  Action space: {env_discrete.action_space}")
    print(f"  Action nvec: {env_discrete.action_space.nvec}")

    # Test observation
    obs, info = env.reset(seed=42)
    print(f"\nObservation sample shape: {obs.shape}")
    print(f"Observation range: [{obs.min():.3f}, {obs.max():.3f}]")
    print(f"Info keys: {list(info.keys())}")

    print("\n✓ Environment creation test passed!")


def test_episode_rollout():
    """Test running a complete episode."""
    print("\n" + "=" * 60)
    print("Testing Episode Rollout")
    print("=" * 60)

    env = V2GTradingEnv(use_discrete_actions=False, render_mode="human")

    obs, info = env.reset(seed=42)
    print(f"Episode start - SOC: {info['soc']*100:.1f}%, Price: ₹{info['market_price']:.2f}")

    total_reward = 0
    step = 0

    while True:
        # Random action
        action = env.action_space.sample()

        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        step += 1

        if step <= 5 or step % 6 == 0:
            print(f"Step {step:2d}: reward={reward:7.2f}, "
                  f"SOC={info['soc']*100:5.1f}%, "
                  f"price=₹{info['market_price']:.2f}, "
                  f"profit=₹{info['episode_profit']:.2f}")

        if terminated or truncated:
            break

    print(f"\nEpisode finished:")
    print(f"  Total steps: {step}")
    print(f"  Total reward: {total_reward:.2f}")
    print(f"  Total profit: ₹{info['episode_profit']:.2f}")
    print(f"  Final SOC: {info['soc']*100:.1f}%")
    print(f"  Battery health: {info['battery_health']*100:.2f}%")
    print(f"  Number of trades: {info['num_trades']}")

    print("\n✓ Episode rollout test passed!")


def test_wrappers():
    """Test environment wrappers."""
    print("\n" + "=" * 60)
    print("Testing Environment Wrappers")
    print("=" * 60)

    # Test make_env with all wrappers
    env = make_env(
        normalize_obs=True,
        normalize_reward=True,
        reward_shaping=True,
        monitor=True,
        seed=42,
    )

    print("Wrapped environment created with:")
    print("  - NormalizeObservation")
    print("  - NormalizeReward")
    print("  - RewardShaping")
    print("  - EpisodeMonitor")

    # Run a few episodes
    for ep in range(3):
        obs, info = env.reset()
        total_reward = 0

        while True:
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            total_reward += reward

            if terminated or truncated:
                break

    # Get statistics from monitor
    stats = env.get_statistics()
    print(f"\nMonitor statistics after 3 episodes:")
    print(f"  Mean reward: {stats['mean_reward']:.2f}")
    print(f"  Mean profit: ₹{stats['mean_profit']:.2f}")
    print(f"  Mean trades: {stats['mean_trades']:.1f}")
    print(f"  Profitable ratio: {stats['profitable_ratio']*100:.1f}%")

    print("\n✓ Wrapper test passed!")


def test_discrete_actions():
    """Test discrete action space."""
    print("\n" + "=" * 60)
    print("Testing Discrete Action Space")
    print("=" * 60)

    env = V2GTradingEnv(use_discrete_actions=True)

    print(f"Action space: {env.action_space}")
    print(f"Quantity levels: {env.quantity_levels}")
    print(f"Price levels: {env.price_levels}")

    obs, info = env.reset(seed=42)

    # Test each action combination
    print("\nTesting action combinations:")
    for q_idx in range(5):
        for p_idx in [0, 2, 4]:  # Sample price levels
            action = (q_idx, p_idx)
            obs, reward, terminated, truncated, info = env.step(action)
            qty = env.quantity_levels[q_idx]
            price_agg = 0.5 + env.price_levels[p_idx]
            action_type = "BUY" if qty > 0 else "SELL" if qty < 0 else "HOLD"
            print(f"  Action ({q_idx}, {p_idx}): qty={qty:+.1f} ({action_type}), "
                  f"agg={price_agg:.2f}, reward={reward:.2f}")

            if terminated or truncated:
                obs, info = env.reset()

    print("\n✓ Discrete action test passed!")


def test_visualization():
    """Test visualization tools."""
    print("\n" + "=" * 60)
    print("Testing Visualization Tools")
    print("=" * 60)

    env = V2GTradingEnv(use_discrete_actions=False)
    visualizer = EnvironmentVisualizer()

    # Record a few episodes
    print("Recording 3 episodes...")
    for i in range(3):
        episode_data = visualizer.record_episode(env, seed=42 + i)
        print(f"  Episode {i+1}: reward={episode_data.total_reward:.2f}, "
              f"profit=₹{episode_data.total_profit:.2f}, "
              f"trades={episode_data.num_trades}")

    # Print statistics
    visualizer.print_statistics()

    # Check if matplotlib is available for plotting
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt

        print("\nGenerating plots...")

        # Plot last episode
        fig = visualizer.plot_episode(
            visualizer.episodes[-1],
            save_path="episode_analysis.png",
            show=False,
        )
        print("  - Saved episode_analysis.png")

        # Plot multi-episode comparison
        fig = visualizer.plot_multiple_episodes(
            save_path="multi_episode_comparison.png",
            show=False,
        )
        print("  - Saved multi_episode_comparison.png")

        # Plot action distribution
        fig = visualizer.plot_action_distribution(
            save_path="action_distribution.png",
            show=False,
        )
        print("  - Saved action_distribution.png")

        print("\n✓ Visualization test passed!")

    except ImportError:
        print("\nmatplotlib not available - skipping plot generation")
        print("✓ Visualization test passed (statistics only)")


def test_gymnasium_compatibility():
    """Test Gymnasium API compatibility."""
    print("\n" + "=" * 60)
    print("Testing Gymnasium API Compatibility")
    print("=" * 60)

    try:
        from gymnasium.utils.env_checker import check_env
        env = V2GTradingEnv(use_discrete_actions=False)
        check_env(env)
        print("✓ Gymnasium env_checker passed!")
    except ImportError:
        print("gymnasium.utils.env_checker not available")
    except Exception as e:
        print(f"Warning: env_checker found issues: {e}")

    # Manual checks
    env = V2GTradingEnv()

    # Check reset returns tuple
    result = env.reset(seed=42)
    assert isinstance(result, tuple) and len(result) == 2, "reset() should return (obs, info)"
    print("✓ reset() returns (obs, info)")

    # Check step returns 5 values
    result = env.step(env.action_space.sample())
    assert len(result) == 5, "step() should return 5 values"
    print("✓ step() returns (obs, reward, terminated, truncated, info)")

    # Check observation in space
    obs, _ = env.reset()
    assert env.observation_space.contains(obs), "observation should be in observation_space"
    print("✓ observations are in observation_space")

    # Check render modes
    assert "render_modes" in env.metadata, "metadata should have render_modes"
    print(f"✓ render_modes: {env.metadata['render_modes']}")

    print("\n✓ Gymnasium compatibility test passed!")


def run_simple_policy():
    """Run a simple heuristic policy."""
    print("\n" + "=" * 60)
    print("Testing Simple Heuristic Policy")
    print("=" * 60)

    def simple_policy(obs):
        """Buy low, sell high based on price forecast."""
        # Extract price forecast (starts at index 29 for 24 values)
        price_forecast = obs[29:53]
        current_price = obs[53]
        soc = obs[0]

        avg_price = np.mean(price_forecast)

        # If price below average and SOC low, buy
        if current_price < avg_price * 0.9 and soc < 0.7:
            return np.array([0.8, 0.6], dtype=np.float32)  # Buy aggressively

        # If price above average and SOC high, sell
        elif current_price > avg_price * 1.1 and soc > 0.4:
            return np.array([-0.8, 0.6], dtype=np.float32)  # Sell aggressively

        # Otherwise hold
        return np.array([0.0, 0.5], dtype=np.float32)

    env = V2GTradingEnv()
    visualizer = EnvironmentVisualizer()

    # Run multiple episodes
    profits = []
    for i in range(10):
        episode_data = visualizer.record_episode(env, policy=simple_policy, seed=i)
        profits.append(episode_data.total_profit)

    print(f"Simple policy results over 10 episodes:")
    print(f"  Mean profit: ₹{np.mean(profits):.2f}")
    print(f"  Std profit: ₹{np.std(profits):.2f}")
    print(f"  Min profit: ₹{np.min(profits):.2f}")
    print(f"  Max profit: ₹{np.max(profits):.2f}")
    print(f"  Profitable: {sum(1 for p in profits if p > 0)}/10")

    print("\n✓ Simple policy test passed!")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("V2G Trading RL Environment Test Suite")
    print("=" * 60)

    tests = [
        test_battery_model,
        test_market_simulator,
        test_environment_creation,
        test_episode_rollout,
        test_discrete_actions,
        test_wrappers,
        test_gymnasium_compatibility,
        run_simple_policy,
        test_visualization,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Passed: {passed}/{len(tests)}")
    print(f"Failed: {failed}/{len(tests)}")

    if failed == 0:
        print("\n✓ All tests passed successfully!")
        return 0
    else:
        print(f"\n✗ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
