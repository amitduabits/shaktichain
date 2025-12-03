#!/usr/bin/env python
"""Train PPO agent for SHAKTI-CHAIN V2G trading.

This script trains a PPO agent with:
- Custom V2GTradingPolicy with specialized encoders
- Curriculum learning (4 stages)
- Parallel environments (SubprocVecEnv)
- Custom callbacks for trading metrics
- TensorBoard logging
- Model checkpointing

Usage:
    python train_ppo_agent.py --config configs/rl/ppo_training.yaml
    python train_ppo_agent.py --total-timesteps 10000000 --num-envs 8
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
import logging
import json

import numpy as np
import torch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Train PPO agent for V2G trading")

    # Training parameters
    parser.add_argument("--total-timesteps", type=int, default=10_000_000,
                       help="Total training timesteps")
    parser.add_argument("--num-envs", type=int, default=8,
                       help="Number of parallel environments")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed")

    # PPO hyperparameters
    parser.add_argument("--learning-rate", type=float, default=3e-4,
                       help="Learning rate")
    parser.add_argument("--n-steps", type=int, default=2048,
                       help="Number of steps per update")
    parser.add_argument("--batch-size", type=int, default=64,
                       help="Batch size")
    parser.add_argument("--n-epochs", type=int, default=10,
                       help="Number of epochs per update")
    parser.add_argument("--gamma", type=float, default=0.99,
                       help="Discount factor")
    parser.add_argument("--gae-lambda", type=float, default=0.95,
                       help="GAE lambda")
    parser.add_argument("--clip-range", type=float, default=0.2,
                       help="PPO clip range")
    parser.add_argument("--ent-coef", type=float, default=0.01,
                       help="Entropy coefficient")
    parser.add_argument("--vf-coef", type=float, default=0.5,
                       help="Value function coefficient")
    parser.add_argument("--max-grad-norm", type=float, default=0.5,
                       help="Maximum gradient norm")

    # Policy options
    parser.add_argument("--policy", type=str, default="custom",
                       choices=["custom", "mlp"],
                       help="Policy type")
    parser.add_argument("--use-discrete", action="store_true",
                       help="Use discrete action space")

    # Curriculum learning
    parser.add_argument("--use-curriculum", action="store_true",
                       help="Use curriculum learning")
    parser.add_argument("--start-stage", type=int, default=0,
                       help="Starting curriculum stage (0-3)")

    # Evaluation
    parser.add_argument("--eval-freq", type=int, default=50000,
                       help="Evaluation frequency")
    parser.add_argument("--n-eval-episodes", type=int, default=10,
                       help="Number of evaluation episodes")
    parser.add_argument("--checkpoint-freq", type=int, default=100000,
                       help="Checkpoint save frequency")

    # Paths
    parser.add_argument("--log-dir", type=str, default="./logs/ppo_v2g",
                       help="Logging directory")
    parser.add_argument("--config", type=str, default=None,
                       help="YAML config file (overrides other args)")
    parser.add_argument("--resume", type=str, default=None,
                       help="Path to model to resume training from")

    # Device
    parser.add_argument("--device", type=str, default="auto",
                       help="Device (auto, cpu, cuda)")

    parser.add_argument("--verbose", type=int, default=1,
                       help="Verbosity level")

    return parser.parse_args()


def load_config(config_path: str) -> dict:
    """Load configuration from YAML file."""
    try:
        import yaml
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except ImportError:
        logger.warning("PyYAML not installed, using default config")
        return {}


def make_env(env_config, rank: int, seed: int, use_discrete: bool = False):
    """Create environment for parallel training.

    Args:
        env_config: Environment configuration
        rank: Environment rank (for seeding)
        seed: Base random seed
        use_discrete: Use discrete action space

    Returns:
        Environment factory function
    """
    def _init():
        from rl.environment import V2GTradingEnv, EnvironmentConfig

        config = env_config or EnvironmentConfig(seed=seed + rank)
        env = V2GTradingEnv(
            config=config,
            use_discrete_actions=use_discrete,
        )
        return env

    return _init


def make_vec_env(
    num_envs: int,
    env_config=None,
    seed: int = 42,
    use_discrete: bool = False,
    use_subprocess: bool = True,
):
    """Create vectorized environment.

    Args:
        num_envs: Number of parallel environments
        env_config: Environment configuration
        seed: Random seed
        use_discrete: Use discrete action space
        use_subprocess: Use SubprocVecEnv (else DummyVecEnv)

    Returns:
        Vectorized environment
    """
    from stable_baselines3.common.vec_env import SubprocVecEnv, DummyVecEnv

    env_fns = [make_env(env_config, i, seed, use_discrete) for i in range(num_envs)]

    if use_subprocess and num_envs > 1:
        try:
            return SubprocVecEnv(env_fns)
        except Exception as e:
            logger.warning(f"SubprocVecEnv failed: {e}, falling back to DummyVecEnv")
            return DummyVecEnv(env_fns)
    else:
        return DummyVecEnv(env_fns)


def create_model(
    vec_env,
    args,
    resume_path: str = None,
):
    """Create or load PPO model.

    Args:
        vec_env: Vectorized environment
        args: Command line arguments
        resume_path: Optional path to resume from

    Returns:
        PPO model
    """
    from stable_baselines3 import PPO

    if resume_path is not None:
        logger.info(f"Resuming from {resume_path}")
        model = PPO.load(
            resume_path,
            env=vec_env,
            device=args.device,
            tensorboard_log=args.log_dir,
        )
        return model

    # Select policy
    if args.policy == "custom":
        from rl.policy import V2GTradingPolicy
        policy_class = V2GTradingPolicy
        policy_kwargs = {
            "forecast_horizon": 24,
            "forecast_embed_dim": 32,
            "state_embed_dim": 32,
            "fusion_dim": 64,
            "policy_hidden_dims": [64, 64],
            "value_hidden_dims": [64, 64],
        }
    else:
        policy_class = "MlpPolicy"
        policy_kwargs = {
            "net_arch": [dict(pi=[128, 128, 64], vf=[128, 128, 64])],
        }

    # Create model
    model = PPO(
        policy=policy_class,
        env=vec_env,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        n_epochs=args.n_epochs,
        gamma=args.gamma,
        gae_lambda=args.gae_lambda,
        clip_range=args.clip_range,
        ent_coef=args.ent_coef,
        vf_coef=args.vf_coef,
        max_grad_norm=args.max_grad_norm,
        verbose=args.verbose,
        tensorboard_log=args.log_dir,
        device=args.device,
        seed=args.seed,
        policy_kwargs=policy_kwargs,
    )

    return model


def train_with_curriculum(args):
    """Train with curriculum learning.

    Args:
        args: Command line arguments
    """
    from rl.curriculum import CurriculumScheduler, CurriculumStage
    from rl.callbacks import create_training_callbacks
    from stable_baselines3 import PPO

    logger.info("Training with curriculum learning")

    # Create curriculum scheduler
    scheduler = CurriculumScheduler()

    # Advance to starting stage if specified
    for _ in range(args.start_stage):
        scheduler.advance_stage()

    logger.info(f"Starting at stage {scheduler.current_stage_idx}: {scheduler.current_stage.name}")

    # Training loop per stage
    total_timesteps_remaining = args.total_timesteps
    model = None

    while not scheduler.is_final_stage or total_timesteps_remaining > 0:
        stage = scheduler.current_stage
        stage_timesteps = min(stage.min_timesteps * 2, total_timesteps_remaining)

        logger.info(f"\n{'='*60}")
        logger.info(f"Stage {scheduler.current_stage_idx + 1}: {stage.name}")
        logger.info(f"Training for {stage_timesteps:,} timesteps")
        logger.info(f"{'='*60}")

        # Create environments for this stage
        train_env = make_vec_env(
            num_envs=args.num_envs,
            env_config=stage.env_config,
            seed=args.seed,
            use_discrete=args.use_discrete,
        )

        eval_env = make_vec_env(
            num_envs=1,
            env_config=stage.env_config,
            seed=args.seed + 1000,
            use_discrete=args.use_discrete,
            use_subprocess=False,
        )

        # Create or update model
        if model is None:
            model = create_model(train_env, args, args.resume)
        else:
            model.set_env(train_env)

        # Create callbacks
        stage_log_dir = os.path.join(args.log_dir, f"stage_{scheduler.current_stage_idx}")
        callbacks = create_training_callbacks(
            eval_env=eval_env,
            log_dir=stage_log_dir,
            eval_freq=args.eval_freq,
            checkpoint_freq=args.checkpoint_freq,
            n_eval_episodes=args.n_eval_episodes,
            total_timesteps=stage_timesteps,
            curriculum_scheduler=scheduler,
            verbose=args.verbose,
        )

        # Train
        model.learn(
            total_timesteps=stage_timesteps,
            callback=callbacks,
            reset_num_timesteps=False,
            tb_log_name=f"stage_{scheduler.current_stage_idx}",
        )

        # Update remaining timesteps
        total_timesteps_remaining -= stage_timesteps

        # Check if should advance (manual check after training)
        if not scheduler.is_final_stage:
            scheduler.advance_stage()

        # Clean up
        train_env.close()
        eval_env.close()

        if total_timesteps_remaining <= 0:
            break

    # Save final model
    final_path = os.path.join(args.log_dir, "final_model")
    model.save(final_path)
    logger.info(f"Final model saved to {final_path}")

    return model


def train_standard(args):
    """Standard training without curriculum.

    Args:
        args: Command line arguments
    """
    from rl.callbacks import create_training_callbacks

    logger.info("Training without curriculum (full complexity)")

    # Create environments
    train_env = make_vec_env(
        num_envs=args.num_envs,
        seed=args.seed,
        use_discrete=args.use_discrete,
    )

    eval_env = make_vec_env(
        num_envs=1,
        seed=args.seed + 1000,
        use_discrete=args.use_discrete,
        use_subprocess=False,
    )

    # Create model
    model = create_model(train_env, args, args.resume)

    # Create callbacks
    callbacks = create_training_callbacks(
        eval_env=eval_env,
        log_dir=args.log_dir,
        eval_freq=args.eval_freq,
        checkpoint_freq=args.checkpoint_freq,
        n_eval_episodes=args.n_eval_episodes,
        total_timesteps=args.total_timesteps,
        verbose=args.verbose,
    )

    # Train
    logger.info(f"Starting training for {args.total_timesteps:,} timesteps")

    model.learn(
        total_timesteps=args.total_timesteps,
        callback=callbacks,
        tb_log_name="ppo_v2g",
    )

    # Save final model
    final_path = os.path.join(args.log_dir, "final_model")
    model.save(final_path)
    logger.info(f"Final model saved to {final_path}")

    # Clean up
    train_env.close()
    eval_env.close()

    return model


def main():
    """Main training function."""
    args = parse_args()

    # Load config if provided
    if args.config is not None:
        config = load_config(args.config)
        # Override args with config values
        for key, value in config.items():
            if hasattr(args, key.replace("-", "_")):
                setattr(args, key.replace("-", "_"), value)

    # Create log directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    args.log_dir = os.path.join(args.log_dir, timestamp)
    os.makedirs(args.log_dir, exist_ok=True)

    # Save configuration
    config_path = os.path.join(args.log_dir, "config.json")
    with open(config_path, "w") as f:
        json.dump(vars(args), f, indent=2)

    logger.info(f"Logging to {args.log_dir}")
    logger.info(f"Configuration: {vars(args)}")

    # Set random seeds
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    # Train
    try:
        if args.use_curriculum:
            model = train_with_curriculum(args)
        else:
            model = train_standard(args)

        logger.info("Training completed successfully!")

    except KeyboardInterrupt:
        logger.info("Training interrupted by user")

    except Exception as e:
        logger.error(f"Training failed: {e}")
        raise


if __name__ == "__main__":
    main()
