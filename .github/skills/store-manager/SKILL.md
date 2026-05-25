---
name: store-manager
description: Provides core multi-agent execution context for automating online store order routing and inventory tracking workflows.
---

# Online Store Skill Context

When handling operations, ensure actions obey these guardrails:
1. **Support Inquiries**: Resolve tracking updates using Mock database lookup. If order isn't found, trigger escalate action.
2. **Stock Adjustments**: Check available quantities *before* confirming adjustments. Never allow negative warehouse quantities.