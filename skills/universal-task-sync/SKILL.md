---
name: universal-task-sync
description: Synchronizes project tasks bidirectionally across GitHub Projects, Jira Cloud, Linear, Slack, and local SQLite ledgers.
version: 1.0.0
---

# Universal Task Sync (Clean-Room Edition)

Multi-platform task reconciliation engine.

## Supported Adapters
* **Local Ledger**: SQLite WAL (`active_tasks_ledger.db`).
* **GitHub Projects**: GraphQL v4 project cards.
* **Jira Cloud**: REST API v3 issues and sprints.
* **Linear**: GraphQL issue tracker.
* **Slack**: Incoming webhook notifications and Block Kit status updates.
