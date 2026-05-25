---
name: store-manager
description: Provides multi-agent execution context for automating online store order routing, inventory tracking, and quote/pricing updates.
---

# Online Store Skill Context

When handling operations, ensure actions obey these guardrails:
1. **Support Inquiries**: Resolve tracking updates using Mock database lookup. If order isn't found, trigger escalate action.
2. **Stock Adjustments**: Check available quantities *before* confirming adjustments. Never allow negative warehouse quantities.
3. **Pricing & Quotes**: Apply the current baseline sales tax (7%) to all quotes unless the product qualifies for wholesale discount tiers.