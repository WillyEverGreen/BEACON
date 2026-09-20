# BEACON Logging Guide

## Overview

BEACON uses a centralized, structured logging system that supports both development (human-readable) and production (JSON) formats with automatic request tracing.

## Architecture

### Components

1. **Centralized Configuration** (`app/core/logging_config.py`)
   - JSON formatter for production
   - Contextual formatter for development
   - Request/audit ID injection
   - Rotating file handlers

2. **Request Logging Middleware** (`app/middleware/logging_middleware.py`)
   - Automatic request ID generation
   - Request/response timing
   - Context injection into all logs
   - Health check endpoint filtering

3. **Context Variables**
   - `request_id`: Unique identifier for each API request
   - `user_id`: User performing the operation
   - `audit_id`: Audit being processed

## Usage

### Basic Logging

```python
import logging

logger = logging.getLogger(__name__)

# Log at different levels
logger.debug("Detailed information for debugging")
logger.info("General informational messages")
logger.warning("Warning messages for potential issues")
logger.error("Error messages for failures")
logger.critical("Critical errors that require immediate attention")
```

### With Context

```python
from app.core.logging_config import set_request_context

# In an async handler
set_request_context(
    request_id=request.state.request_id,
    user_id=user.id,
    audit_id=audit.id
)

# All subsequent logs will include this context
logger.info("Processing audit")  # Includes request_id, user_id, audit_id
```

### Structured Logging with Extra Fields

```python
logger.info(
    "Audit completed successfully",
    extra={
        "audit_id": audit_id,
        "duration_ms": duration,
        "issues_found": len(issues),
        "score": score
    }
)
```

## Configuration

### Environment Variables

- `BACKEND_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOGS_DIR`: Directory for log files (default: `./logs`)
- `ENVIRONMENT`: Determines log format (json for production, text for development)

### Log Formats

**Development (text)**:
```
2024-01-15 10:30:45 | INFO     | app.services.audit_runner:run_audit:123 | Audit started
```

**Production (JSON)**:
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "logger": "app.services.audit_runner",
  "message": "Audit started",
  "module": "audit_runner",
  "function": "run_audit",
  "line": 123,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user_123",
  "audit_id": "audit_456"
}
```

## Log Levels Guide

### DEBUG
Use for detailed diagnostic information. Disabled in production by default.

```python
logger.debug(f"Processing chunk {i}/{total}: {chunk[:50]}...")
logger.debug(f"Cache hit for key: {cache_key}")
```

### INFO
Use for general informational messages about normal operation.

```python
logger.info(f"Audit completed: {url} -> score={score}")
logger.info(f"Vector store initialized with {count} chunks")
```

### WARNING
Use for potentially problematic situations that don't prevent operation.

```python
logger.warning(f"API rate limit approaching: {requests}/{limit}")
logger.warning(f"Deprecated function called: {func_name}")
```

### ERROR
Use for error events that don't stop the application.

```python
logger.error(f"Failed to enrich issue: {issue_id}", exc_info=True)
logger.error(f"Database connection lost, retrying...")
```

### CRITICAL
Use for severe errors that may cause application failure.

```python
logger.critical("Unable to connect to database after 5 retries")
logger.critical("Out of memory, cannot process more requests")
```

## Migration from print()

### ❌ Don't Use print()

```python
# BAD - bypasses log levels and configuration
print(f"Processing {url}...")
print(f"ERROR: Failed to connect")
```

### ✅ Use Logging Instead

```python
# GOOD - proper logging with levels
logger.info(f"Processing {url}...")
logger.error(f"Failed to connect to {url}")
```

### Automated Migration

Use the provided script to migrate existing code:

```bash
# Dry run to see what would change
python scripts/replace_print_with_logging.py --dry-run

# Apply changes
python scripts/replace_print_with_logging.py
```

## Best Practices

### 1. Use Appropriate Log Levels
Match the severity of the message to the log level.

### 2. Include Context
Add relevant context as extra fields for better debugging.

```python
logger.info(
    "Scan completed",
    extra={"url": url, "duration_ms": duration, "issues": count}
)
```

### 3. Log Exceptions Properly
Always include exception information for errors.

```python
try:
    result = risky_operation()
except Exception as exc:
    logger.error(f"Operation failed: {exc}", exc_info=True)
    raise
```

### 4. Avoid Sensitive Data
Never log passwords, API keys, or PII.

```python
# BAD
logger.info(f"User logged in: {email}, password: {password}")

# GOOD
logger.info(f"User logged in: {user_id}")
```

### 5. Use Lazy Formatting
Let the logger handle string formatting for performance.

```python
# GOOD - only formats if level is enabled
logger.debug("Processing %s with %d items", name, count)
```

### 6. Don't Log in Hot Paths
Avoid excessive logging in tight loops.

```python
# BAD - logs for every iteration
for i in range(10000):
    logger.debug(f"Processing item {i}")

# GOOD - log periodically
for i in range(10000):
    if i % 1000 == 0:
        logger.debug(f"Processed {i}/10000 items")
```

## File Organization

### Log Files

- `logs/beacon.log`: All logs (rotates at 10MB, keeps 5 backups)
- `logs/beacon.error.log`: Errors and above only
- Logs rotate automatically to prevent disk space issues

### Access Logs

Request/response logs are automatically captured by the middleware:
- Request start with method, path, query params
- Request completion with status code and duration
- Health check endpoints are filtered out to reduce noise

## Troubleshooting

### Logs Not Appearing

1. Check log level: `BACKEND_LOG_LEVEL` may be too high
2. Check if logs directory is writable
3. Verify logger is properly initialized

### Too Much Noise

1. Increase log level: `BACKEND_LOG_LEVEL=WARNING`
2. Adjust third-party library log levels in `logging_config.py`
3. Filter health checks in middleware

### Missing Context

1. Ensure middleware is registered in `main.py`
2. Check context is set via `set_request_context()`
3. Verify context variables are in scope

## Examples

### Audit Operation

```python
from app.core.logging_config import set_request_context, get_logger

logger = get_logger(__name__)

async def run_audit(url: str, user_id: str) -> dict:
    audit_id = generate_audit_id()
    set_request_context(audit_id=audit_id, user_id=user_id)
    
    logger.info(f"Starting audit for {url}")
    
    try:
        result = await perform_audit(url)
        logger.info(
            "Audit completed successfully",
            extra={
                "score": result["score"],
                "issues_found": len(result["issues"]),
                "duration_ms": result["duration"]
            }
        )
        return result
        
    except Exception as exc:
        logger.error(f"Audit failed for {url}", exc_info=True)
        raise
```

### Long-Running Operation

```python
logger.info(f"Starting ingestion of {len(documents)} documents")

for i, doc in enumerate(documents):
    if i % 100 == 0:
        logger.info(f"Progress: {i}/{len(documents)} documents processed")
    
    try:
        process_document(doc)
    except Exception as exc:
        logger.warning(f"Failed to process document {doc['id']}: {exc}")
        continue

logger.info(f"Ingestion complete: {len(documents)} documents processed")
```

## Testing

### Test Logging

In tests, use `caplog` fixture to verify logging:

```python
def test_audit_logs_completion(caplog):
    with caplog.at_level(logging.INFO):
        result = run_audit("https://example.com")
    
    assert "Audit completed successfully" in caplog.text
    assert any(record.levelname == "INFO" for record in caplog.records)
```

### Mock Logger

For unit tests, mock the logger to verify calls:

```python
from unittest.mock import patch

def test_error_handling():
    with patch('app.services.audit_runner.logger') as mock_logger:
        with pytest.raises(Exception):
            run_failing_audit()
        
        mock_logger.error.assert_called_once()
```
