# Production Launch Checklist

Complete checklist for deploying V2G Marketplace to production. Follow this systematically before going live.

## Table of Contents

- [Pre-Launch Phase](#pre-launch-phase)
- [Infrastructure Setup](#infrastructure-setup)
- [Security Hardening](#security-hardening)
- [Testing & QA](#testing--qa)
- [Monitoring & Logging](#monitoring--logging)
- [Legal & Compliance](#legal--compliance)
- [Launch Day](#launch-day)
- [Post-Launch](#post-launch)

---

## Pre-Launch Phase

### Code Readiness

- [ ] **All Tests Passing**
  ```bash
  # Backend tests
  cd backend
  pytest tests/ -v --cov --cov-report=term-missing
  # Target: 80%+ coverage

  # Frontend tests
  cd frontend
  npm test
  npm run test:e2e
  ```

- [ ] **Code Review Completed**
  - [ ] All PRs reviewed by at least 2 maintainers
  - [ ] No "TODO" or "FIXME" comments in production code
  - [ ] Security-sensitive code audited

- [ ] **Performance Benchmarking**
  - [ ] API response time: p95 < 200ms
  - [ ] Simulation execution: 300 agents, 7 days < 5 minutes
  - [ ] Database queries: All < 100ms
  - [ ] Load test: 100 concurrent users, 0% error rate

- [ ] **Documentation Complete**
  - [ ] README.md updated with production URLs
  - [ ] API documentation current (Swagger UI)
  - [ ] Architecture diagrams up-to-date
  - [ ] Deployment guide tested by fresh reviewer
  - [ ] User guides available

### Smart Contract Readiness

- [ ] **Contracts Deployed to Testnet**
  - [ ] ShaktiToken deployed to Polygon Amoy
  - [ ] EnergyAuction deployed and linked
  - [ ] StakingPool deployed and linked
  - [ ] ReputationSystem deployed and linked
  - [ ] All contract addresses documented

- [ ] **Contract Testing**
  - [ ] Unit tests: 100% function coverage
  - [ ] Integration tests: Complete user journeys
  - [ ] Fuzz testing: No unexpected reverts
  - [ ] Gas optimization: Reasonable gas costs

- [ ] **Security Audit**
  - [ ] Smart contracts audited by reputable firm (e.g., OpenZeppelin, ConsenSys Diligence)
  - [ ] All critical/high severity issues resolved
  - [ ] Medium severity issues documented and mitigated
  - [ ] Audit report published

---

## Infrastructure Setup

### Domain & DNS

- [ ] **Domain Configured**
  - [ ] Domain purchased (e.g., v2g-marketplace.com)
  - [ ] DNS records configured:
    ```
    A     v2g-marketplace.com     -> <server-ip>
    A     www.v2g-marketplace.com -> <server-ip>
    A     api.v2g-marketplace.com -> <server-ip>
    ```
  - [ ] TTL set appropriately (300s for launch, 3600s after stabilization)

- [ ] **SSL/TLS Certificates**
  - [ ] Let's Encrypt certificate obtained
  - [ ] Auto-renewal configured (certbot cron job)
  - [ ] Certificate covers all subdomains (wildcard or SAN)
  - [ ] HTTPS redirect enabled (HTTP -> HTTPS)
  - [ ] TLS 1.2+ only (disable TLS 1.0/1.1)
  - [ ] Strong cipher suites configured

### Cloud Infrastructure

- [ ] **Server Provisioning**
  - [ ] Production server(s) provisioned
  - [ ] Minimum specs:
    - Backend: 4 vCPU, 8 GB RAM, 100 GB SSD
    - Database: 2 vCPU, 4 GB RAM, 200 GB SSD (if separate)
  - [ ] Auto-scaling group configured (if using cloud)
  - [ ] Load balancer configured (if multiple servers)

- [ ] **Network Configuration**
  - [ ] VPC/security groups configured
  - [ ] Firewall rules:
    - Allow: 80 (HTTP), 443 (HTTPS), 22 (SSH from specific IPs)
    - Block: All other inbound
  - [ ] DDoS protection enabled (e.g., Cloudflare, AWS Shield)

- [ ] **Database Setup**
  - [ ] Production database provisioned
  - [ ] For PostgreSQL:
    - [ ] Master instance with automated backups
    - [ ] Read replica for queries (optional)
    - [ ] Connection pooling (PgBouncer/RDS Proxy)
  - [ ] For SQLite:
    - [ ] File on persistent volume
    - [ ] Backup script scheduled

### Blockchain Infrastructure

- [ ] **Mainnet Deployment**
  - [ ] Smart contracts deployed to Polygon Mainnet
  - [ ] Contract addresses updated in backend .env
  - [ ] Contract addresses updated in frontend .env
  - [ ] Contract verification on Polygonscan

- [ ] **RPC Provider**
  - [ ] Production RPC endpoint configured (Alchemy, Infura, or Ankr)
  - [ ] Rate limits checked and acceptable
  - [ ] Fallback RPC endpoints configured
  - [ ] WebSocket endpoint for event listening

- [ ] **Private Key Management**
  - [ ] Backend signing key generated securely
  - [ ] Private key stored in secrets manager (AWS Secrets Manager, HashiCorp Vault)
  - [ ] Private key never committed to version control
  - [ ] Backup recovery phrase stored securely offline

---

## Security Hardening

### Application Security

- [ ] **Environment Variables**
  - [ ] All secrets in environment variables (not hardcoded)
  - [ ] JWT_SECRET_KEY: 256-bit random key
  - [ ] Database credentials: Strong passwords
  - [ ] API keys: Rotated and documented
  - [ ] `.env` file not in version control (.gitignore)

- [ ] **Authentication & Authorization**
  - [ ] JWT tokens: 24-hour expiration
  - [ ] Password hashing: bcrypt with salt rounds e 10
  - [ ] Role-based access control (RBAC) implemented
  - [ ] Admin endpoints protected (role check)

- [ ] **Input Validation**
  - [ ] All API inputs validated (Pydantic schemas)
  - [ ] SQL injection prevention (parameterized queries)
  - [ ] XSS prevention (React auto-escaping + CSP headers)
  - [ ] CSRF tokens (if using cookies)

- [ ] **Rate Limiting**
  - [ ] API rate limits configured:
    - Auth endpoints: 10 req/min per IP
    - Simulation creation: 10 req/min per user
    - Market data: 100 req/min per user
    - Blockchain ops: 20 req/min per user
  - [ ] Rate limit headers included in responses

- [ ] **CORS Configuration**
  - [ ] CORS_ORIGINS set to production domains only
  - [ ] Credentials allowed only for trusted origins
  - [ ] Preflight requests handled correctly

### Infrastructure Security

- [ ] **Server Hardening**
  - [ ] OS updates applied
  - [ ] Unnecessary services disabled
  - [ ] SSH key-only authentication (password auth disabled)
  - [ ] Fail2ban configured (ban after 5 failed SSH attempts)

- [ ] **Container Security**
  - [ ] Docker images from official sources
  - [ ] No root user in containers
  - [ ] Minimal base images (Alpine Linux)
  - [ ] Regular image updates (Dependabot)

- [ ] **Network Security**
  - [ ] Internal services not exposed publicly
  - [ ] Database accessible only from application servers
  - [ ] VPN/bastion host for admin access

### Compliance

- [ ] **Data Protection**
  - [ ] GDPR compliance (if EU users):
    - [ ] Data collection notice
    - [ ] Right to deletion implemented
    - [ ] Data export functionality
  - [ ] Indian data laws (DPDP Act 2023):
    - [ ] Data stored in India (or compliant location)
    - [ ] User consent mechanisms

- [ ] **Privacy Policy**
  - [ ] Privacy policy drafted and published
  - [ ] Cookie policy (if using analytics)
  - [ ] Link to privacy policy in footer

- [ ] **Terms of Service**
  - [ ] Terms of service drafted and published
  - [ ] User agreement checkbox on registration
  - [ ] Link to ToS in footer

---

## Testing & QA

### Functional Testing

- [ ] **User Flows**
  - [ ] Registration ’ Login ’ Dashboard: Works
  - [ ] Create simulation ’ View results ’ Download CSV: Works
  - [ ] Connect wallet ’ Stake tokens ’ Claim rewards: Works
  - [ ] Submit bid ’ Auction clears ’ Trade executed: Works

- [ ] **Edge Cases**
  - [ ] Invalid inputs rejected with clear error messages
  - [ ] Expired JWT tokens handled (401 response)
  - [ ] Blockchain RPC failures gracefully handled
  - [ ] Database connection failures handled

- [ ] **Browser Testing**
  - [ ] Chrome (latest): Fully functional
  - [ ] Firefox (latest): Fully functional
  - [ ] Safari (latest): Fully functional
  - [ ] Edge (latest): Fully functional
  - [ ] Mobile browsers (iOS Safari, Chrome Android): Functional

### Performance Testing

- [ ] **Load Testing**
  - [ ] Tool: Apache JMeter, k6, or Locust
  - [ ] Scenario: 100 concurrent users, 10 minutes
  - [ ] Results:
    - [ ] API response time: p95 < 500ms
    - [ ] Error rate: < 0.1%
    - [ ] Database connections: No exhaustion
    - [ ] Memory usage: Stable (no leaks)

- [ ] **Stress Testing**
  - [ ] Scenario: 500 concurrent users (5x expected load)
  - [ ] System degrades gracefully (no crashes)
  - [ ] Auto-scaling triggers (if configured)

### Security Testing

- [ ] **Vulnerability Scanning**
  - [ ] OWASP Top 10 checked:
    - [ ] No SQL injection
    - [ ] No XSS vulnerabilities
    - [ ] No broken authentication
    - [ ] No sensitive data exposure
  - [ ] Tools used: OWASP ZAP, Burp Suite, or Nessus

- [ ] **Penetration Testing**
  - [ ] Hired security firm or ethical hacker
  - [ ] Report received and issues resolved

---

## Monitoring & Logging

### Application Monitoring

- [ ] **Prometheus + Grafana**
  - [ ] Prometheus scraping backend metrics
  - [ ] Grafana dashboards created:
    - [ ] API Performance (latency, throughput)
    - [ ] Simulation Metrics (count, duration)
    - [ ] Blockchain Sync Health
    - [ ] System Resources (CPU, memory, disk)
  - [ ] Public dashboard URL (read-only): _____________

- [ ] **Alerting Configured**
  - [ ] Alert rules defined:
    - [ ] API error rate > 1% (5-minute window)
    - [ ] API p95 latency > 1s
    - [ ] Blockchain sync lag > 100 blocks
    - [ ] Database connection pool > 80% usage
    - [ ] Disk usage > 85%
  - [ ] Alert channels configured:
    - [ ] Email: devops@v2g-marketplace.com
    - [ ] Slack/PagerDuty (optional)

### Error Tracking

- [ ] **Sentry Integration**
  - [ ] Sentry SDK installed (backend)
  - [ ] Sentry SDK installed (frontend)
  - [ ] DSN configured in .env
  - [ ] Source maps uploaded (frontend)
  - [ ] Test error sent and received

### Logging

- [ ] **Centralized Logging**
  - [ ] Log aggregation tool: ELK Stack, CloudWatch, or Datadog
  - [ ] Backend logs forwarded (JSON format)
  - [ ] Nginx access logs forwarded
  - [ ] Frontend errors captured

- [ ] **Log Retention**
  - [ ] Retention policy: 90 days (or as per compliance)
  - [ ] Log rotation configured
  - [ ] Old logs archived or deleted

### Uptime Monitoring

- [ ] **Health Check Monitoring**
  - [ ] Tool: UptimeRobot, Pingdom, or StatusCake
  - [ ] Endpoints monitored:
    - [ ] https://v2g-marketplace.com (frontend)
    - [ ] https://api.v2g-marketplace.com/health (backend)
  - [ ] Check interval: 5 minutes
  - [ ] Alerts to: ops@v2g-marketplace.com

---

## Legal & Compliance

### Regulatory Approval

- [ ] **CERC (Central Electricity Regulatory Commission)**
  - [ ] Application submitted for V2G trading approval
  - [ ] Pilot project approval obtained (if applicable)
  - [ ] Compliance documentation prepared

- [ ] **State DISCOM Coordination**
  - [ ] Meetings with target state DISCOMs
  - [ ] Technical integration requirements understood
  - [ ] MoU signed (if applicable)

### Financial Compliance

- [ ] **GST Registration** (if in India)
  - [ ] GST number obtained
  - [ ] Tax invoicing system ready

- [ ] **AML/KYC** (if required)
  - [ ] KYC process defined
  - [ ] AML monitoring tools integrated

### Insurance

- [ ] **Cyber Insurance**
  - [ ] Policy obtained (covers data breach, downtime)
  - [ ] Coverage amount: _____________

- [ ] **Liability Insurance**
  - [ ] General liability coverage
  - [ ] Professional liability (E&O)

---

## Launch Day

### Pre-Launch (T-24 hours)

- [ ] **Final Testing**
  - [ ] Smoke tests on production environment
  - [ ] All integrations verified (blockchain, database)
  - [ ] Backup and restore tested

- [ ] **Team Briefing**
  - [ ] All team members aware of launch timeline
  - [ ] Roles and responsibilities assigned
  - [ ] Incident response plan reviewed

- [ ] **Communication Prepared**
  - [ ] Launch announcement drafted (blog, social media)
  - [ ] Press release ready (if applicable)
  - [ ] Support team trained

### Launch (T-0)

- [ ] **Deployment**
  ```bash
  # 1. Backend deployment
  git pull origin main
  docker-compose build
  docker-compose up -d

  # 2. Database migrations (if any)
  python manage.py migrate

  # 3. Frontend deployment
  npm run build
  # Deploy build to CDN/server

  # 4. Verify deployment
  curl https://api.v2g-marketplace.com/health
  # Expected: {"status": "healthy"}
  ```

- [ ] **Smoke Tests**
  - [ ] Homepage loads: https://v2g-marketplace.com
  - [ ] API health check passes
  - [ ] User can register and login
  - [ ] Simulation can be created

- [ ] **Monitoring Check**
  - [ ] Grafana dashboards showing data
  - [ ] Prometheus targets up
  - [ ] Sentry receiving events
  - [ ] Logs flowing to aggregator

### Post-Launch (T+4 hours)

- [ ] **Announcement**
  - [ ] Blog post published
  - [ ] Social media posts shared (Twitter, LinkedIn)
  - [ ] Email to beta users sent

- [ ] **Monitoring**
  - [ ] Team monitoring dashboards (first 24 hours)
  - [ ] No critical errors
  - [ ] Performance within acceptable range

---

## Post-Launch

### Week 1

- [ ] **User Feedback**
  - [ ] Collect feedback via support channel
  - [ ] Monitor social media mentions
  - [ ] Track key metrics:
    - [ ] User registrations
    - [ ] Simulations created
    - [ ] Blockchain transactions
    - [ ] Error rate

- [ ] **Performance Review**
  - [ ] API response times acceptable
  - [ ] Database performance acceptable
  - [ ] Blockchain sync lag minimal

- [ ] **Bug Fixes**
  - [ ] Prioritize critical bugs
  - [ ] Hotfix deployment process tested

### Week 2-4

- [ ] **Stability Assessment**
  - [ ] No critical incidents
  - [ ] Uptime > 99.5%
  - [ ] Error rate < 0.1%

- [ ] **Feature Feedback**
  - [ ] Identify most-requested features
  - [ ] Prioritize for next release

- [ ] **Scale Planning**
  - [ ] Analyze user growth trajectory
  - [ ] Plan infrastructure scaling (if needed)

### Month 1

- [ ] **Retrospective**
  - [ ] Team retrospective meeting
  - [ ] Document lessons learned
  - [ ] Update launch checklist for future releases

- [ ] **Metrics Report**
  - [ ] Total users
  - [ ] Total simulations
  - [ ] Total blockchain transactions
  - [ ] Average response time
  - [ ] Uptime percentage

---

## Emergency Contacts

| Role | Name | Email | Phone |
|------|------|-------|-------|
| Tech Lead | _________ | _________ | _________ |
| DevOps | _________ | _________ | _________ |
| Security | _________ | _________ | _________ |
| Product Manager | _________ | _________ | _________ |

### Incident Response

**If Critical Issue Occurs**:
1. **Assess Severity**: Critical, High, Medium, Low
2. **Notify Team**: Use emergency contact list
3. **Mitigate**: Rollback deployment if needed
   ```bash
   git checkout <previous-stable-commit>
   docker-compose up -d
   ```
4. **Communicate**: Update status page, notify users
5. **Resolve**: Fix issue, test, redeploy
6. **Postmortem**: Document incident, root cause, prevention

---

## Rollback Plan

**If deployment fails**:

```bash
# 1. Stop current deployment
docker-compose down

# 2. Checkout previous version
git log --oneline  # Find previous stable commit
git checkout <commit-hash>

# 3. Rebuild and deploy
docker-compose build
docker-compose up -d

# 4. Restore database (if needed)
sqlite3 data/v2g.db < backup/v2g_<timestamp>.db

# 5. Verify rollback
curl https://api.v2g-marketplace.com/health

# 6. Communicate to team and users
```

---

## Sign-Off

Before launching, obtain sign-off from:

- [ ] **Tech Lead**: Code quality and architecture approved
- [ ] **DevOps**: Infrastructure and monitoring ready
- [ ] **Security**: Security audit complete, issues resolved
- [ ] **Product Manager**: Features complete, documentation ready
- [ ] **Legal**: Terms, privacy policy, compliance checked
- [ ] **Management**: Business objectives clear, go/no-go decision

**Signatures**:

Tech Lead: _________________ Date: _______
DevOps: ___________________ Date: _______
Security: _________________ Date: _______
Product Manager: ___________ Date: _______
Legal: ____________________ Date: _______
Management: _______________ Date: _______

---

## Additional Resources

- **Runbooks**: [Link to operational runbooks]
- **Architecture Docs**: [docs/ARCHITECTURE.md](./ARCHITECTURE.md)
- **API Docs**: https://api.v2g-marketplace.com/docs
- **Monitoring Dashboards**: [Grafana URL]
- **Incident Response Plan**: [Link to IRP document]

---

**Launch Checklist Version**: 1.0
**Last Updated**: December 2025
**Next Review**: After launch retrospective

---

**Good luck with the launch! =€**
