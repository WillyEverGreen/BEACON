# BEACON Monetization & Tiering Strategy

This document outlines the planned monetization tiers for the BEACON Accessibility Engine. These tiers are enforced at the API and Crawler levels.

## Plan Tiers

| Feature | FREE | PRO | ENTERPRISE |
| :--- | :--- | :--- | :--- |
| **Price** | $0/mo | $49/mo | Contact Us |
| **Max Pages/Scan** | 10 | 50 | 200+ |
| **AI Fix Budget** | 5 issues/audit | 25 issues/audit | 100+ issues/audit |
| **Concurrency** | 2 pages | 5 pages | 10+ pages |
| **Retention** | 30 Days | 1 Year | Unlimited |
| **White-labeling** | No | Yes | Yes |
| **API Access** | Limited | Full | Full + High Rate Limits |

## Enforcement Mechanism

### 1. Database (Supabase)
The `usage_limits` table tracks the current plan and consumed units for each `user_id`.
- `plan`: Enum ('free', 'pro', 'enterprise')
- `ai_budget_per_audit`: Dynamic limit passed to the LLM service.
- `pages_per_audit`: Hard ceiling for the crawler.

### 2. Config (`app/config.py`)
The `PLAN_TIERS` dictionary serves as the source of truth for the capacity of each tier.

### 3. Middleware/Service Layer
- **Audit Runner**: Fetches user limits before starting a scan.
- **LLM Service**: Respects the `max_enrich_issues` parameter to prevent over-spending on free-tier users.
- **Crawler**: Truncates discovery lists to the `max_pages` limit.

## Future Considerations: "Scheduled Mode"
Post-launch, a "Scheduled" tier will be introduced for Enterprise users:
- Deep-crawls run overnight (2:00 AM - 5:00 AM).
- No concurrency limits during off-peak hours.
- Full site accessibility regression testing with automated Diff reports.
