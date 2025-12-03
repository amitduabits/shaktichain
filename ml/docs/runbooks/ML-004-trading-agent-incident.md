# ML-004: Trading Agent Incident

## Overview
**Alert**: TradingAgentOffline / TradingProfitabilityLow
**Severity**: Critical (offline) / Warning (low profitability)
**Component**: Trading Agent, RL Agent
**SLO Impact**: Yes - affects trading operations and revenue

## Symptoms
- Trading agent stopped responding (no updates > 10 minutes)
- Negative P&L over 24 hours
- Unexpected trading actions
- Battery SOC abnormal (too high/low, not varying)
- Trading execution errors

## Investigation Steps

### 1. Check Agent Status
```bash
# Check if trading agent is running
docker ps | grep trading-agent

# Check agent logs
docker logs shakti-trading-agent --tail 100

# Check for errors
docker logs shakti-trading-agent --tail 500 | grep -i "error\|exception\|failed"

# Check agent health
curl http://trading-agent:8080/health
```

### 2. Check Trading Metrics
```bash
# Check current P&L
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_pnl_current{period="daily"}' | jq

# Check trading actions
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(ml_trading_actions_total[1h]) by (action_type)' | jq

# Check profit/loss
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=increase(ml_trading_profit_total[24h]) - increase(ml_trading_loss_total[24h])' | jq

# Check battery SOC
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_battery_soc' | jq
```

### 3. Check Model Status
```bash
# Check if trading model is loaded
curl http://ml-service:8000/models | jq '.[] | select(.name=="trading_agent")'

# Check model last updated
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=ml_model_last_updated_timestamp{model="trading_agent"}' | jq

# Check model version
curl http://trading-agent:8080/model/info
```

### 4. Check Trading Execution
```bash
# Check blockchain connectivity
curl http://trading-agent:8080/blockchain/status

# Check smart contract interaction
docker logs shakti-trading-agent | grep "contract\|transaction"

# Check transaction status
# Via blockchain explorer or subgraph
curl http://subgraph:8000/graphql \
  -X POST \
  -d '{"query": "{ transactions(orderBy: timestamp, orderDirection: desc, first: 10) { id timestamp type status } }"}'
```

### 5. Check Dependencies
```bash
# Check ML service
curl http://ml-service:8000/health

# Check price predictions
curl http://ml-service:8000/forecast/predict \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"city": "delhi", "horizon": 24}'

# Check blockchain node
curl http://blockchain-node:8545 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### 6. Check Environment State
```bash
# Check current market prices
curl http://trading-agent:8080/market/prices

# Check grid conditions
curl http://trading-agent:8080/grid/status

# Check battery status
curl http://trading-agent:8080/battery/status

# Check recent observations
docker exec shakti-trading-agent cat /tmp/agent_state.json
```

## Common Causes & Solutions

### Cause 1: Agent Process Crashed
**Symptoms**: Container running but no activity
**Solution**:
```bash
# Check process
docker exec shakti-trading-agent ps aux

# Check resource usage
docker stats shakti-trading-agent --no-stream

# Restart agent
docker-compose restart trading-agent

# If OOM, increase memory
# Edit docker-compose.yml:
#   trading-agent:
#     deploy:
#       resources:
#         limits:
#           memory: 4G

docker-compose up -d trading-agent
```

### Cause 2: Model Not Loaded
**Symptoms**: Model loading errors, predictions failing
**Solution**:
```bash
# Check model availability
ls -lh /app/models/trading/

# Download latest model
cd /app/shaktichain/ml
python scripts/download_model.py \
  --model trading_agent \
  --stage production \
  --output /app/models/trading/

# Reload model
curl -X POST http://trading-agent:8080/model/reload
```

### Cause 3: Poor Model Performance
**Symptoms**: Negative P&L, suboptimal actions
**Solution**:
```bash
# Analyze recent trades
cd /app/shaktichain/ml
python scripts/analyze_trading_performance.py \
  --start -24h \
  --output /tmp/trading_analysis.json

# Compare with baseline
python scripts/compare_with_baseline.py \
  --agent ppo \
  --baseline naive \
  --period 7d

# If significantly worse, rollback
curl -X POST http://trading-agent:8080/model/rollback \
  -H "Content-Type: application/json" \
  -d '{"version": "previous"}'

# Or switch to safe mode (conservative strategy)
curl -X POST http://trading-agent:8080/mode/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "safe"}'
```

### Cause 4: Blockchain Connectivity Issues
**Symptoms**: Transaction failures, contract errors
**Solution**:
```bash
# Check blockchain node
curl http://blockchain-node:8545 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"net_version","params":[],"id":1}'

# Check account balance
curl http://trading-agent:8080/account/balance

# Check gas prices
curl http://blockchain-node:8545 \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_gasPrice","params":[],"id":1}'

# Restart with different RPC endpoint if needed
# Edit .env:
#   BLOCKCHAIN_RPC_URL=https://alternate-rpc.example.com

docker-compose restart trading-agent
```

### Cause 5: Market Conditions Changed
**Symptoms**: Strategy not profitable, unusual market activity
**Solution**:
```bash
# Analyze market conditions
cd /app/shaktichain/ml
python scripts/analyze_market.py --period 7d

# Check for anomalies
python scripts/detect_market_anomalies.py

# Adjust risk parameters
curl -X POST http://trading-agent:8080/config/update \
  -H "Content-Type: application/json" \
  -d '{
    "risk_tolerance": 0.3,
    "max_position_size": 50,
    "stop_loss": 0.05
  }'

# Enable manual approval for large trades
curl -X POST http://trading-agent:8080/config/update \
  -H "Content-Type: application/json" \
  -d '{"require_approval": true, "approval_threshold": 1000}'
```

### Cause 6: Battery Management Issues
**Symptoms**: SOC stuck, battery not charging/discharging
**Solution**:
```bash
# Check battery status
curl http://trading-agent:8080/battery/status

# Check battery constraints
curl http://trading-agent:8080/battery/constraints

# Reset battery state if stuck
curl -X POST http://trading-agent:8080/battery/reset \
  -H "Content-Type: application/json" \
  -d '{"soc": 0.5}'  # Reset to 50%

# Check physical battery if persistent
# Contact battery management system team
```

## Resolution Steps

### Immediate Actions

#### If Agent Offline
1. **Restart agent**:
   ```bash
   docker-compose restart trading-agent
   docker logs -f shakti-trading-agent
   ```

2. **Enable safe mode**: Conservative trading
   ```bash
   curl -X POST http://trading-agent:8080/mode/switch \
     -H "Content-Type: application/json" \
     -d '{"mode": "safe"}'
   ```

3. **Manual monitoring**: Watch for 15 minutes
   ```bash
   watch -n 30 'curl -s http://trading-agent:8080/status | jq'
   ```

#### If Poor Performance
1. **Pause trading**: Stop automatic trading
   ```bash
   curl -X POST http://trading-agent:8080/trading/pause
   ```

2. **Analyze performance**: Review recent trades
   ```bash
   cd /app/shaktichain/ml
   python scripts/analyze_trading_performance.py --detailed
   ```

3. **Switch to baseline**: Use simple strategy
   ```bash
   curl -X POST http://trading-agent:8080/strategy/switch \
     -H "Content-Type: application/json" \
     -d '{"strategy": "baseline_momentum"}'
   ```

### Investigation & Fix
1. **Identify root cause**: Use investigation steps
2. **Apply solution**: Based on diagnosis
3. **Test in simulation**: Before resuming live trading
   ```bash
   cd /app/shaktichain/ml
   python scripts/simulate_trading.py \
     --agent ppo \
     --start -7d \
     --mode paper
   ```

### Resume Trading
1. **Verify fixes**:
   ```bash
   # Check health
   curl http://trading-agent:8080/health

   # Check model loaded
   curl http://trading-agent:8080/model/info

   # Test prediction
   curl -X POST http://trading-agent:8080/predict \
     -H "Content-Type: application/json" \
     -d '{"observation": {...}}'
   ```

2. **Resume with caution**:
   ```bash
   # Resume with reduced position sizes
   curl -X POST http://trading-agent:8080/config/update \
     -H "Content-Type: application/json" \
     -d '{"max_position_size": 25}'  # 50% of normal

   # Resume trading
   curl -X POST http://trading-agent:8080/trading/resume
   ```

3. **Monitor closely**: For 4 hours
   ```bash
   watch -n 60 'curl -s http://trading-agent:8080/status | jq'
   ```

## Verification
```bash
# Check agent responding
curl http://trading-agent:8080/health

# Check recent trades
curl http://trading-agent:8080/trades/recent | jq

# Check P&L trending up
curl -s http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=deriv(ml_pnl_current{period="daily"}[1h])' | jq

# Check alert resolved
curl -s http://prometheus:9090/api/v1/alerts | \
  jq '.data.alerts[] | select(.labels.alertname=="TradingAgentOffline")'
```

## Risk Management

### Trading Pause Criteria
Pause trading immediately if:
- P&L loss > 10% in 1 hour
- > 5 failed transactions in a row
- Battery SOC out of safe range (< 10% or > 90%)
- Market anomaly detected (price spike > 200%)
- Agent producing invalid actions

### Emergency Contacts
- **Trading Team Lead**: +91-XXX-XXX-XXXX
- **Risk Management**: risk@shaktichain.io
- **ML Engineering Lead**: +91-XXX-XXX-XXXX

### Manual Override
```bash
# Pause all trading
curl -X POST http://trading-agent:8080/emergency/stop

# Close all positions
curl -X POST http://trading-agent:8080/positions/close-all

# Switch to manual mode
curl -X POST http://trading-agent:8080/mode/manual
```

## Escalation
- **If offline > 15 minutes**: Page Trading Team Lead
- **If P&L loss > 5%**: Alert Risk Management immediately
- **If market anomaly**: Contact Market Operations
- **If blockchain issue**: Escalate to Blockchain Team

## Related Dashboards
- [Trading Performance](http://grafana:3000/d/trading-performance)
- [ML Service Overview](http://grafana:3000/d/ml-service-overview)
- [Anomaly Detection](http://grafana:3000/d/anomaly-detection)

## Related Runbooks
- ML-001: High Latency Troubleshooting
- ML-002: Model Performance Degradation
- TRADING-001: Market Circuit Breaker
- BLOCKCHAIN-001: Smart Contract Issues

## Post-Incident Actions
1. **P&L reconciliation**: Verify all trades
2. **Root cause analysis**: Why did agent fail/underperform
3. **Backtest fix**: Validate solution on historical data
4. **Update model**: Retrain if needed
5. **Improve monitoring**: Add checks for failure mode
6. **Risk review**: Assess if risk limits appropriate

## Metadata
- **Created**: 2024-12-03
- **Last Updated**: 2024-12-03
- **Owner**: Trading Team, ML Engineering
- **Reviewers**: Risk Management, SRE Team
