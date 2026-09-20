# BEACON Security Guide

This document outlines the security features, configurations, and best practices for the BEACON API.

## Table of Contents

- [Security Architecture](#security-architecture)
- [Authentication & Authorization](#authentication--authorization)
- [CORS Configuration](#cors-configuration)
- [Rate Limiting](#rate-limiting)
- [Input Validation](#input-validation)
- [Security Headers](#security-headers)
- [Error Handling](#error-handling)
- [Request Size Limits](#request-size-limits)
- [SSRF Protection](#ssrf-protection)
- [Deployment Security](#deployment-security)
- [Security Checklist](#security-checklist)

---

## Security Architecture

BEACON implements defense-in-depth with multiple security layers:

```
┌─────────────────────────────────────────────────┐
│            Client Request                        │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  1. Request Size Limit Middleware                │
│     └─ Blocks oversized requests (max 10MB)      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  2. CORS Middleware                              │
│     └─ Validates origin headers                  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  3. Rate Limiting Middleware                     │
│     └─ Enforces 60/min, 1000/hr per client       │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  4. Request Logging Middleware                   │
│     └─ Logs request details + timing             │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  5. Authentication Middleware                    │
│     └─ Validates API keys                        │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  6. Route Handler                                │
│     └─ Input validation + business logic         │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  7. Error Handler Middleware (outermost)         │
│     └─ Catches all exceptions, standardizes      │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  8. Security Headers Middleware                  │
│     └─ Adds security headers to response         │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│            Response to Client                    │
└─────────────────────────────────────────────────┘
```

---

## Authentication & Authorization

### API Key Authentication

BEACON uses API key-based authentication with three role-based keys:

- **Viewer**: Read-only access to audit results
- **Auditor**: Can trigger audits and view results
- **Admin**: Full access including configuration and management

### Configuration

Set the following environment variables:

```bash
# Enable/disable authentication
AUTH_ENABLED=true

# Bootstrap API keys (generate secure random values)
BOOTSTRAP_VIEWER_API_KEY=viewer_key_here
BOOTSTRAP_AUDITOR_API_KEY=auditor_key_here
BOOTSTRAP_ADMIN_API_KEY=admin_key_here
```

### Usage

Include API key in request headers:

```bash
curl -H "X-API-Key: your-api-key-here" \
     https://api.beacon.com/v1/audit
```

### Best Practices

✅ **DO:**
- Generate strong random API keys (min 32 characters)
- Rotate keys regularly (quarterly recommended)
- Use different keys for different environments
- Store keys in secure environment variables
- Revoke compromised keys immediately

❌ **DON'T:**
- Commit API keys to version control
- Share keys across teams or services
- Use default/placeholder values in production
- Include keys in client-side code
- Log API keys in application logs

---

## CORS Configuration

### Overview

Cross-Origin Resource Sharing (CORS) restricts which domains can access your API.

### Configuration

```bash
# .env or Render environment variables
CORS_ORIGINS=https://your-app.vercel.app,https://www.your-domain.com
```

### Multiple Origins

Separate multiple origins with commas:

```bash
CORS_ORIGINS=https://app.example.com,https://staging.example.com,https://admin.example.com
```

### Development vs Production

**Development:**
```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
```

**Production:**
```bash
CORS_ORIGINS=https://beacon.yourdomain.com
```

### Allowed Methods & Headers

BEACON allows:
- **Methods**: GET, POST, PUT, DELETE, PATCH, OPTIONS
- **Headers**: Content-Type, Authorization, X-API-Key, X-Request-ID, Accept, Origin, User-Agent

### Testing CORS

```bash
# Test preflight request
curl -X OPTIONS https://api.beacon.com/v1/audit \
     -H "Origin: https://your-app.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -v

# Check for Access-Control-Allow-Origin in response
```

---

## Rate Limiting

### Overview

Rate limiting prevents abuse and ensures fair resource allocation using a sliding window algorithm.

### Default Limits

- **Per Minute**: 60 requests
- **Per Hour**: 1000 requests

### Configuration

```bash
# Enable/disable rate limiting
RATE_LIMIT_ENABLED=true

# Adjust limits
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
```

### Client Identification

Clients are identified by:
1. **API Key** (preferred) - more accurate tracking
2. **IP Address** (fallback) - respects X-Forwarded-For header

### Response Headers

Every response includes rate limit headers:

```http
X-RateLimit-Limit-Minute: 60
X-RateLimit-Limit-Hour: 1000
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1609459200
```

### Rate Limit Exceeded

When limit is exceeded, API returns:

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 42
X-RateLimit-Remaining: 0

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Please try again in 42 seconds.",
    "details": {
      "retry_after": 42
    }
  },
  "request_id": "abc-123",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### Exempt Paths

These paths are exempt from rate limiting:
- `/health`
- `/`
- `/docs`
- `/openapi.json`

### Best Practices

✅ **DO:**
- Respect the `Retry-After` header
- Implement exponential backoff
- Monitor `X-RateLimit-Remaining` header
- Use batch endpoints for bulk operations
- Cache responses when possible

❌ **DON'T:**
- Retry immediately after 429 response
- Create multiple API keys to circumvent limits
- Ignore rate limit headers
- Make unnecessary API calls

### Adjusting for Production

For high-volume production workloads, contact support or:

```bash
# Increase limits for specific use cases
RATE_LIMIT_PER_MINUTE=120
RATE_LIMIT_PER_HOUR=5000
```

---

## Input Validation

### URL Validation

All URLs are validated for:
- **Scheme**: Only http/https allowed
- **Length**: Max 2048 characters
- **SSRF Protection**: Private IPs and internal hostnames blocked
- **Injection**: Suspicious patterns filtered

```python
# Blocked patterns
- Private IPs: 10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12
- Loopback: 127.0.0.1, localhost
- Link-local: 169.254.0.0/16
- Internal TLDs: .internal, .local
- Metadata endpoints: 169.254.169.254
```

### Scan Mode Validation

Valid scan modes:
- `quick` - Fast scan (< 30 seconds)
- `comprehensive` - Standard audit (2-5 minutes)
- `deep` - Thorough analysis (5-15 minutes)
- `custom` - User-defined configuration

### String Validation

All string inputs are:
- Stripped of leading/trailing whitespace
- Length-validated (max 1000 chars by default)
- Pattern-matched when applicable
- Sanitized to prevent injection

### Filename Sanitization

Filenames are sanitized to prevent path traversal:
- Remove path separators (`/`, `\`)
- Strip dangerous characters (`<`, `>`, `|`, etc.)
- Block reserved names (CON, PRN, AUX, etc.)
- Max length: 255 characters

---

## Security Headers

### Automatically Added Headers

Every response includes:

```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

**Production only** (HTTPS):
```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### Header Descriptions

| Header | Purpose |
|--------|---------|
| `X-Content-Type-Options` | Prevents MIME-type sniffing attacks |
| `X-Frame-Options` | Prevents clickjacking by disabling iframes |
| `X-XSS-Protection` | Enables browser XSS filter |
| `Strict-Transport-Security` | Enforces HTTPS for 1 year |
| `Referrer-Policy` | Controls referrer information leakage |
| `Permissions-Policy` | Disables unnecessary browser features |

---

## Error Handling

### Standardized Error Format

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "field": "field_name",
    "details": {}
  },
  "request_id": "unique-id",
  "timestamp": "2024-01-01T12:00:00Z",
  "path": "/v1/audit"
}
```

### Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `VALIDATION_ERROR` | 422 | Invalid input data |
| `AUTHENTICATION_ERROR` | 401 | Missing/invalid API key |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `RESOURCE_NOT_FOUND` | 404 | Resource doesn't exist |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `DATABASE_ERROR` | 503 | Database operation failed |
| `EXTERNAL_SERVICE_ERROR` | 502 | LLM/external API failure |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

### Production Error Hiding

In production (`ENVIRONMENT=production`), internal error details are hidden:

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An internal server error occurred. Please try again later."
  }
}
```

Development exposes full stack traces for debugging.

---

## Request Size Limits

### Configuration

```bash
# Maximum request body size in megabytes
MAX_REQUEST_SIZE_MB=10
```

### When Limit is Exceeded

```json
HTTP/1.1 413 Request Entity Too Large

{
  "error": {
    "code": "REQUEST_TOO_LARGE",
    "message": "Request size exceeds maximum allowed size of 10MB"
  }
}
```

### Recommended Limits

| Use Case | Limit |
|----------|-------|
| API requests | 10 MB |
| File uploads | 50 MB |
| Bulk imports | 100 MB |

---

## SSRF Protection

### Built-in Protections

BEACON blocks:
- Private IP addresses (RFC 1918)
- Loopback addresses
- Link-local addresses
- IPv6 ULA and link-local
- Cloud metadata endpoints (169.254.169.254)
- Internal TLDs (.internal, .local)

### DNS Rebinding Protection

All URLs are resolved before scanning:
1. Hostname is resolved to IP address(es)
2. Each resolved IP is validated
3. Blocked IPs cause immediate rejection
4. Only validated URLs proceed to scanning

### Example Blocked URLs

```bash
# These will all be rejected
http://localhost:8080
http://192.168.1.1
http://10.0.0.1
http://metadata.google.internal
http://169.254.169.254/latest/meta-data/
```

---

## Deployment Security

### Environment Variables

✅ **DO:**
- Use Render's secret environment variables
- Enable "Sync: false" for sensitive values
- Use `generateValue: true` for API keys
- Rotate secrets quarterly

❌ **DON'T:**
- Commit `.env` file to git
- Use placeholder values in production
- Share secrets in chat/email
- Reuse secrets across environments

### Docker Security

Image includes:
- Non-root user (`beacon:beacon`)
- Minimal base image (python:3.10-slim)
- No unnecessary packages
- Read-only filesystem where possible
- Health checks configured

### Network Security

- HTTPS enforced in production (HSTS header)
- TLS 1.2+ required
- Certificate validation enabled
- No self-signed certificates accepted

### Logging Security

- API keys are NEVER logged
- Sensitive fields redacted in logs
- Request IDs for tracing
- Structured JSON logging

---

## Security Checklist

### Pre-Deployment

- [ ] All placeholder values replaced in `.env`
- [ ] Strong API keys generated (min 32 chars)
- [ ] CORS origins configured for production domain
- [ ] Rate limits adjusted for expected traffic
- [ ] HTTPS enabled and enforced
- [ ] Security headers verified
- [ ] Authentication enabled (`AUTH_ENABLED=true`)
- [ ] Environment set to `production`

### Post-Deployment

- [ ] Test API key authentication
- [ ] Verify CORS from frontend
- [ ] Confirm rate limiting works
- [ ] Check security headers in response
- [ ] Test error handling (invalid inputs)
- [ ] Verify SSRF protection (try blocked URLs)
- [ ] Monitor logs for suspicious activity
- [ ] Set up alerts for security events

### Monthly Maintenance

- [ ] Review API key usage
- [ ] Rotate API keys
- [ ] Update dependencies
- [ ] Review access logs
- [ ] Check for failed auth attempts
- [ ] Verify rate limit effectiveness
- [ ] Update blocked domain list

### Incident Response

If security incident detected:

1. **Immediately**: Rotate compromised API keys
2. **Within 1 hour**: Review access logs
3. **Within 24 hours**: Identify impact scope
4. **Within 1 week**: Implement additional controls
5. **Document**: Create postmortem report

---

## Support

For security concerns or to report vulnerabilities:
- **Email**: security@beacon.com (if available)
- **GitHub**: Open a private security advisory
- **Response SLA**: 24 hours for critical issues

---

**Last Updated**: January 2024
**Security Version**: 1.0
**Compliance**: OWASP Top 10 2021
