"""Test that all imports work correctly."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing imports...")
print("-" * 50)

try:
    print("1. Testing blockchain services...")
    from services.blockchain import (
        Web3Provider,
        get_web3_provider,
        NetworkType,
        ContractManager,
        get_contract_manager,
        TransactionManager,
        TransactionStatus,
        TransactionResult,
        PendingTransaction,
        EventListener,
        BlockchainSync,
        BlockchainService,
        get_blockchain_service,
    )
    print("   ✓ All blockchain imports successful")
    print(f"   ✓ NetworkType available: {list(NetworkType)}")
    print(f"   ✓ TransactionStatus available: {list(TransactionStatus)}")
except ImportError as e:
    print(f"   ✗ Blockchain import failed: {e}")
    sys.exit(1)

try:
    print("\n2. Testing API routes...")
    from api.routes.blockchain import router as blockchain_router
    print("   ✓ Blockchain routes imported")
except ImportError as e:
    print(f"   ✗ API routes import failed: {e}")
    sys.exit(1)

try:
    print("\n3. Testing main app...")
    from api.main import app
    print("   ✓ Main app imported successfully")
except ImportError as e:
    print(f"   ✗ Main app import failed: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("✅ All imports successful!")
print("=" * 50)
print("\nBackend should start without import errors.")
print("Run: python -m uvicorn api.main:app --reload")
