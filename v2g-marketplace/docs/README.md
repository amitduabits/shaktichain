# V2G Marketplace Documentation

Welcome to the V2G Marketplace documentation. This guide will help you understand, deploy, and contribute to the platform.

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [**API Reference**](API.md) | Complete REST API documentation with examples |
| [**Deployment Guide**](DEPLOYMENT.md) | Local, Docker, and cloud deployment instructions |
| [**Architecture**](ARCHITECTURE.md) | System design, data flow, and component details |
| [**Math & Economics**](MATH.md) | Auction mechanism and token model explanations |
| [**Roadmap**](ROADMAP.md) | Feature roadmap and contribution guide |
| [**Launch Checklist**](LAUNCH_CHECKLIST.md) | Pre-production deployment checklist |

---

## Quick Links

### For Users
- [Quick Start](../README.md#quick-start) - Get running in 3 commands
- [Dashboard Overview](../README.md#screenshots) - UI walkthrough
- [FAQ](#faq) - Common questions

### For Developers
- [API Reference](API.md) - Endpoint documentation
- [Architecture](ARCHITECTURE.md) - System design
- [Contributing](ROADMAP.md#how-to-contribute) - Contribution guidelines

### For Operators
- [Deployment Guide](DEPLOYMENT.md) - Installation instructions
- [Launch Checklist](LAUNCH_CHECKLIST.md) - Pre-launch verification
- [Monitoring](DEPLOYMENT.md#monitoring--logging) - Logging and metrics

---

## Overview

V2G Marketplace is a Vehicle-to-Grid energy trading platform designed for the Indian energy market. Key features include:

- **McAfee Double Auction**: Incentive-compatible price discovery
- **SHAKTI Token**: Velocity-based token economics
- **Smart Agents**: Autonomous trading prosumer agents
- **Indian Demand Modeling**: Regional and seasonal load profiles

### Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend    │  React 19, Vite, Recharts, Axios             │
├──────────────┼──────────────────────────────────────────────┤
│  Backend     │  Python 3.11, FastAPI, Uvicorn               │
├──────────────┼──────────────────────────────────────────────┤
│  Database    │  SQLite                                       │
├──────────────┼──────────────────────────────────────────────┤
│  Auth        │  JWT + bcrypt                                 │
├──────────────┼──────────────────────────────────────────────┤
│  Container   │  Docker, Docker Compose                       │
├──────────────┼──────────────────────────────────────────────┤
│  Testing     │  Pytest, Vitest, Playwright                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/amitduabits/shaktichain/issues)
- **Discussions**: [GitHub Discussions](https://github.com/amitduabits/shaktichain/discussions)

---

## FAQ

### General

**Q: What is V2G?**
A: Vehicle-to-Grid (V2G) is a system where electric vehicles can send power back to the grid during peak demand, providing grid stability and earning revenue for EV owners.

**Q: Is this for real energy trading?**
A: Currently, this is a simulation platform for testing and modeling V2G scenarios. Real grid integration is on the roadmap.

**Q: Which regions of India are supported?**
A: The platform models demand profiles for Delhi, Mumbai, Bangalore, Chennai, Kolkata, Pune, Hyderabad, and Ahmedabad.

### Technical

**Q: Why SQLite instead of PostgreSQL?**
A: SQLite provides zero-configuration deployment suitable for MVP scale. PostgreSQL migration is planned for v1.2.

**Q: How does the McAfee auction work?**
A: See [Math & Economics](MATH.md#mcafee-double-auction) for a detailed explanation with examples.

**Q: What is the SHAKTI token?**
A: SHAKTI is the marketplace's native token with velocity-based pricing. See [Token Model](MATH.md#shakti-token-model) for details.

### Deployment

**Q: What are the minimum system requirements?**
A: 2 CPU cores, 4GB RAM, 10GB disk space for a basic deployment.

**Q: Can I deploy on Kubernetes?**
A: Yes, see the [Cloud Deployment](DEPLOYMENT.md#cloud-deployment) section for guidance.

**Q: How do I set up HTTPS?**
A: See [SSL/HTTPS Setup](DEPLOYMENT.md#sslhttps-setup) in the deployment guide.

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| v1.0.0 | 2024-01-15 | Initial release with core trading platform |

See [CHANGELOG](../CHANGELOG.md) for detailed release notes.

---

## License

V2G Marketplace is released under the MIT License. See [LICENSE](../LICENSE) for details.
