"""Test blockchain configuration."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load dotenv
from dotenv import load_dotenv
load_dotenv()

import os

print("=" * 60)
print("BLOCKCHAIN CONFIGURATION TEST")
print("=" * 60)

print("\n1. Environment Variables:")
print(f"   BLOCKCHAIN_NETWORK: {os.getenv('BLOCKCHAIN_NETWORK', 'NOT SET')}")
print(f"   POLYGON_AMOY_RPC_URL: {os.getenv('POLYGON_AMOY_RPC_URL', 'NOT SET')}")
print(f"   HARDHAT_RPC_URL: {os.getenv('HARDHAT_RPC_URL', 'NOT SET')}")

print("\n2. Importing blockchain service...")
try:
    from services.blockchain import get_blockchain_service, NetworkType
    print("   SUCCESS: Blockchain service imported")
except ImportError as e:
    print(f"   FAILED: {e}")
    sys.exit(1)

print("\n3. Creating blockchain service...")
try:
    bs = get_blockchain_service()
    print(f"   Network: {bs.network.value}")
    print(f"   RPC URL: {bs.provider.rpc_url}")
    print(f"   Connected: {bs.is_connected}")

    if bs.is_connected:
        info = bs.get_connection_info()
        print(f"   Chain ID: {info.get('chain_id')}")
        print(f"   Block Number: {info.get('block_number')}")
    else:
        print("   WARNING: Not connected to blockchain")

except Exception as e:
    print(f"   FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n4. Testing main API import...")
try:
    from api.main import app
    print("   SUCCESS: Main API app imported")
except ImportError as e:
    print(f"   FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
print("\nBackend is ready to start.")
print("Run: start_backend.bat")
