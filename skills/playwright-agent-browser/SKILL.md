---
name: playwright-agent-browser
description: High-performance headless browser CLI using Playwright with enterprise OAuth2/SAML SSO session support and virtual display.
version: 1.0.0
---

# Playwright Agent Browser (Clean-Room Edition)

Headless browsing, DOM traversal, and web screenshot extraction engine.

## Usage
```bash
# Headless page extraction
python3 -m playwright run test.py --headless

# Virtual display execution
DISPLAY=:99 python3 browser_runner.py
```
