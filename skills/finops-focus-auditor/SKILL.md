---
name: finops-focus-auditor
description: Audits cloud consumption, commitment discounts (CUDs/RIs), and cost trends adhering to the FinOps Open Cost & Usage Specification (FOCUS 1.0).
version: 1.0.0
---

# FinOps FOCUS Auditor (Clean-Room Edition)

Reconciles multi-cloud spend against contracted commitment discounts.

## FOCUS 1.0 Schema Alignment
* Maps Provider Spend Tables to FOCUS 1.0 standard dimensions: `ChargeType`, `ContractedUnitPrice`, `EffectiveCost`, `BilledCost`, `CapacityReservation`.
* Automatically detects idle commitments and recommends optimal commitment coverage.
