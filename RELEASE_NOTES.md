Production readiness: crawler hardening
=====================================

- Status: production-ready for non-blocked / public targets.
- Validation: `tests/multi_mode_validation_results.json` run passed with 90.0% success (27/30).
- Remaining degraded site: Etsy (degraded_reason = bot_wall — upstream 403 anti-bot block).

Notes and next steps:
- The codebase includes timeout, retry, and probe hardening to improve reliability on heavy JS sites (e.g., NYTimes).
- Etsy failures are external access issues. To reach 100% site coverage consider operational mitigations:
  - allowlist egress IPs with the target site,
  - use an approved proxy pool or partner allowlisting,
  - request partner access/session allowlist from the site owner.

If you want, I can (a) add an explicit external-block classification in reporting, (b) prepare a short release commit message, or (c) draft operational steps for anti-bot mitigation.
