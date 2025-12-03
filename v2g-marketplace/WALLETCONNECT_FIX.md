# 🔧 WalletConnect Error Fix

## Problem

You're seeing `400 Bad Request` errors to `pulse.walletconnect.org` because:

1. **Invalid Project ID**: The app is using `demo-project-id` which WalletConnect rejects
2. **WalletConnect Required**: RainbowKit requires a valid WalletConnect project ID

## Quick Fix (5 minutes)

### Get a FREE WalletConnect Project ID

1. **Go to**: https://cloud.walletconnect.com/
2. **Click**: "Sign In" (or "Get Started")
3. **Sign up** with your email (it's free)
4. **Create a new project**:
   - Project Name: `SHAKTI-CHAIN V2G Marketplace`
   - Click "Create"
5. **Copy your Project ID** (looks like: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`)

### Add Project ID to Your App

**Edit**: `frontend/.env.development`

Replace this line:
```bash
VITE_WALLET_CONNECT_PROJECT_ID=2c5e2f6f3d1e4b8a9c0d1e2f3a4b5c6d
```

With your real project ID:
```bash
VITE_WALLET_CONNECT_PROJECT_ID=your-actual-project-id-here
```

### Restart Frontend

```bash
# Stop current server (Ctrl+C)
# Then restart:
cd frontend
npm run dev
```

**Result**: ✅ WalletConnect errors will be gone!

---

## Alternative: Use Without Wallet (Temporary)

If you don't want to set up WalletConnect right now, you can use simulation mode only:

### Option 1: Start in Simulation Mode

Your app defaults to `simulation` mode which doesn't need wallet connection. Just ignore the WalletConnect errors - they won't affect the simulation features.

### Option 2: Disable Wallet Features Temporarily

**Edit**: `frontend/src/App.jsx`

Comment out wallet-related imports:
```jsx
// import { ConnectWallet, TransactionStatus } from './components/web3';
```

This will hide wallet UI elements until you're ready to set up WalletConnect.

---

## Understanding the Error

### What's Happening?

```
Request: https://pulse.walletconnect.org/e?projectId=demo-project-id
Response: 400 Bad Request
```

**Reason**: WalletConnect validates project IDs. `demo-project-id` is not a valid ID.

### Why It's Needed?

WalletConnect is used for:
- 🔌 Connecting MetaMask mobile wallet
- 🦊 Connecting other Web3 wallets
- 🔐 Signing blockchain transactions

**Not needed for**:
- ✅ Backend API calls (already working)
- ✅ Simulation mode (no blockchain)
- ✅ Basic app functionality

---

## Current Status

| Feature | Status | Notes |
|---------|--------|-------|
| Backend API | ✅ Working | Port 8000, Polygon Amoy |
| Frontend UI | ✅ Working | React app loads |
| Blockchain RPC | ✅ Working | Polygon Amoy testnet |
| WalletConnect | ⚠️ Invalid ID | Get free ID to fix |
| Simulation Mode | ✅ Working | No wallet needed |

---

## Recommended Action

### For Development (Right Now)

**Option 1**: Get a free WalletConnect Project ID (5 minutes)
- https://cloud.walletconnect.com/
- Free tier is perfect for development
- Unlimited projects

**Option 2**: Use simulation mode and ignore wallet errors
- App works fine without wallet
- Add WalletConnect later

### For Production (Later)

You **must** get a valid WalletConnect Project ID for production:
- Required for wallet connections
- Free tier: 1M requests/month
- Takes 5 minutes to set up

---

## Testing Without Wallet

If you want to test without fixing WalletConnect now:

### 1. Use Simulation Mode

When you open the app, stay in **Simulation Mode** (default):
- No wallet connection needed
- Works with backend API
- Perfect for testing features

### 2. Ignore Console Errors

The `400 Bad Request` errors won't affect:
- ✅ Login/Register
- ✅ Dashboard
- ✅ Simulations
- ✅ Market data
- ✅ API calls

They only affect:
- ❌ Connecting MetaMask
- ❌ Real blockchain transactions

---

## Summary

**Current Issue**: WalletConnect requires valid project ID
**Impact**: Can't connect wallet, but app works otherwise
**Quick Fix**: Get free project ID from https://cloud.walletconnect.com/
**Time**: 5 minutes
**Cost**: Free

**Workaround**: Use simulation mode, add wallet later

---

## Files Modified

1. ✅ `frontend/.env.development` - Added placeholder project ID
2. ✅ `frontend/src/providers/Web3Provider.tsx` - Added error handling
3. ✅ `frontend/src/config/wagmi.ts` - Already configured for Polygon Amoy

---

## Next Steps

### Immediate (to fix the error)
```bash
1. Visit https://cloud.walletconnect.com/
2. Create free account
3. Create new project
4. Copy Project ID
5. Update frontend/.env.development
6. Restart frontend (npm run dev)
```

### Or (to use without wallet)
```bash
1. Just use the app in simulation mode
2. Ignore WalletConnect errors in console
3. Add wallet connection later when needed
```

---

**Status**: ⚠️ WalletConnect needs valid project ID
**App Status**: ✅ Works fine otherwise
**Action**: Get free WalletConnect project ID or use simulation mode

**Last Updated**: 2025-12-03
