# Deploying BEACON Backend to Render

This guide walks through deploying the FastAPI backend to Render using Docker.

## Prerequisites

- [Render account](https://render.com/) (free tier available)
- GitHub repository with BEACON code
- Supabase project created (database)
- LLM API key (NVIDIA NIM or Featherless)

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Render Web Service                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Docker Container (Non-root user: beacon)             │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  FastAPI App (Uvicorn)                          │  │  │
│  │  │  - Multi-engine accessibility scanning          │  │  │
│  │  │  - RAG-powered remediation                      │  │  │
│  │  │  - Lighthouse enrichment                        │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │                                                          │  │
│  │  Persistent Storage:                                    │  │
│  │  /app/chroma_db (ChromaDB vector store)                │  │
│  │  /app/logs (Application logs)                          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
  ┌─────────────┐           ┌─────────────┐
  │  Supabase   │           │  NVIDIA NIM │
  │  PostgreSQL │           │  LLM API    │
  └─────────────┘           └─────────────┘
```

## Quick Start

### 1. Create New Web Service

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure as follows:

**Basic Settings:**
- **Name**: `beacon-api` (or your preferred name)
- **Region**: Oregon (US West) - recommended for low latency
- **Branch**: `main`
- **Root Directory**: Leave blank (Dockerfile is in root)
- **Environment**: Docker
- **Docker Build Context Directory**: `.`
- **Dockerfile Path**: `./Dockerfile`

**Instance Settings:**
- **Plan**: Starter ($7/month) or higher
  - Free tier: Limited RAM, will struggle with browser automation
  - Starter: 512MB RAM, sufficient for light usage
  - Standard: 2GB RAM, recommended for production
  
**Auto-Deploy:**
- ✅ Enable auto-deploy from `main` branch

### 2. Configure Environment Variables

Click "Environment" tab and add these variables:

#### Critical Variables (REQUIRED)

| Variable | Value | How to Get |
|----------|-------|------------|
| `ENVIRONMENT` | `production` | Fixed value |
| `NVIDIA_API_KEY` | `nvapi-...` | https://build.nvidia.com/explore/discover |
| `SUPABASE_URL` | `https://xxx.supabase.co` | Supabase Dashboard → Settings → API |
| `SUPABASE_KEY` | `eyJhbGci...` | Supabase Dashboard → Settings → API (anon key) |
| `DATABASE_URL` | `postgresql://...` | Supabase Dashboard → Settings → Database |

#### API Keys (Generate Secure Random Values)

Generate three secure API keys:

```bash
# Generate secure random keys
python3 -c "import secrets; print('VIEWER:', secrets.token_urlsafe(32))"
python3 -c "import secrets; print('AUDITOR:', secrets.token_urlsafe(32))"
python3 -c "import secrets; print('ADMIN:', secrets.token_urlsafe(32))"
```

Add to Render:
- `BOOTSTRAP_VIEWER_API_KEY`: (generated value)
- `BOOTSTRAP_AUDITOR_API_KEY`: (generated value)
- `BOOTSTRAP_ADMIN_API_KEY`: (generated value)

#### CORS Configuration

**IMPORTANT**: Set this to your Vercel frontend domain(s):

```
BACKEND_CORS_ORIGINS=https://your-app.vercel.app,https://your-domain.com
```

For testing, you can temporarily include `http://localhost:3000`, but remove it before going live.

#### Optional But Recommended

| Variable | Default | Notes |
|----------|---------|-------|
| `BACKEND_LOG_LEVEL` | `INFO` | Use `DEBUG` for troubleshooting |
| `AUTH_ENABLED` | `true` | **Never disable in production!** |
| `BEACON_AI_ENABLED` | `true` | Enable AI-powered features |
| `MAX_SCAN_GLOBAL_CAP` | `80` | Maximum pages per site scan |
| `MAX_CONCURRENT_SITE_AUDITS` | `3` | Concurrent scan limit |

### 3. Deploy

1. Click "Create Web Service"
2. Render will:
   - Pull code from GitHub
   - Build Docker image (~5-10 minutes first time)
   - Start container
   - Run health checks
3. Wait for "Live" status

## Post-Deployment Setup

### 1. Verify Deployment

Check health endpoints:

```bash
# Replace with your Render URL
BACKEND_URL="https://beacon-api.onrender.com"

# Liveness check
curl $BACKEND_URL/health/live

# Readiness check (verifies DB + vector store)
curl $BACKEND_URL/health/ready

# Audit runtime health
curl $BACKEND_URL/health/audit
```

Expected responses:
```json
{"status":"live"}
{"status":"ready","db_ready":true,"vector_ready":true,...}
{"status":"healthy","saturation":0.0,...}
```

### 2. Test API with Authentication

```bash
# Test with viewer API key
curl -H "X-API-Key: YOUR_VIEWER_KEY" \
  $BACKEND_URL/health

# Test audit endpoint (requires auditor key)
curl -X POST $BACKEND_URL/v1/audit \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_AUDITOR_KEY" \
  -d '{"url": "https://example.com", "scan_mode": "fast"}'
```

### 3. Update Frontend Configuration

In Vercel, update `BEACON_API_URL`:

```env
BEACON_API_URL=https://beacon-api.onrender.com
```

Also update the three `BOOTSTRAP_*_API_KEY` values to match what you set in Render.

### 4. Initialize Vector Database

The first request will be slow as the vector database initializes. You can pre-populate it:

```bash
# Run ingestion to populate ChromaDB
curl -X POST $BACKEND_URL/v1/ingest \
  -H "X-API-Key: YOUR_ADMIN_KEY"
```

This takes 5-10 minutes but only needs to run once.

## Persistent Storage

### ChromaDB Vector Store

Location: `/app/chroma_db`

**Important**: Render's filesystem is ephemeral. Data persists during:
- Application restarts
- Code deployments

Data is lost during:
- Plan changes
- Region migrations
- Manual container rebuilds

**Recommendation**: For production, migrate to Supabase pgvector (see Task 5).

### Application Logs

Location: `/app/logs`

Logs are also ephemeral. Use Render's log aggregation:

1. Go to Logs tab in Render dashboard
2. Logs are retained for 7 days on free tier, 30 days on paid plans
3. For longer retention, ship logs to external service

## Monitoring & Debugging

### View Logs

**Real-time logs:**
1. Go to Service → Logs tab
2. Filter by level: `ERROR`, `WARNING`, `INFO`, `DEBUG`
3. Search for specific terms

**Download logs:**
```bash
# Install Render CLI
brew install renderinc/render/render  # macOS
# or download from https://render.com/docs/cli

# Login
render login

# View logs
render logs -s beacon-api --tail 100
```

### Common Issues

**Build fails with "Cannot find module":**
```
Check Dockerfile paths are correct
Verify all required files are copied
```

**Health check fails:**
```
ERROR: GET /health/ready → 503 Service Unavailable
```
Solutions:
1. Check DATABASE_URL is correct
2. Verify Supabase is accessible from Render IPs
3. Check SUPABASE_KEY has correct permissions

**Out of Memory errors:**
```
Process killed with signal 9 (SIGKILL)
```
Solutions:
1. Upgrade to larger plan (2GB+ RAM recommended)
2. Reduce MAX_CONCURRENT_SITE_AUDITS
3. Disable browser automation features if needed

**CORS errors in frontend:**
```
Access-Control-Allow-Origin header missing
```
Solution: Update `BACKEND_CORS_ORIGINS` to include frontend domain

### Performance Monitoring

**Render Metrics:**
- CPU usage
- Memory usage
- Response time
- Request rate

Access at: Service → Metrics tab

**Application Metrics:**

Prometheus endpoint (requires admin key):
```bash
curl -H "X-API-Key: YOUR_ADMIN_KEY" \
  $BACKEND_URL/metrics
```

## Scaling

### Horizontal Scaling

Render supports multiple instances:

1. Go to Service → Settings
2. Under "Scaling", increase instance count
3. Render provides automatic load balancing

**Considerations:**
- Each instance has its own ChromaDB (not shared)
- Use shared PostgreSQL (Supabase) for state
- Consider Redis for shared cache

### Vertical Scaling

Upgrade plan for more resources:

| Plan | RAM | CPU | Price |
|------|-----|-----|-------|
| Starter | 512MB | 0.5 CPU | $7/mo |
| Standard | 2GB | 1 CPU | $25/mo |
| Pro | 4GB | 2 CPU | $85/mo |

**Recommendation**: Standard plan for production use.

### Autoscaling

Enable autoscaling:
1. Service → Settings → Autoscaling
2. Set min and max instances
3. Define scaling rules based on CPU/Memory

## Deployment Workflows

### Automatic Deployments

Every push to `main` branch automatically deploys.

**Disable auto-deploy:**
1. Service → Settings
2. Uncheck "Auto-deploy"

### Manual Deployments

Deploy specific commits:

```bash
# Via dashboard
Service → Manual Deploy → "Clear build cache & deploy"

# Via CLI
render deploy -s beacon-api
```

### Rollbacks

If deployment fails:

1. Service → Events tab
2. Find previous successful deployment
3. Click "Rollback to this deploy"

### Preview Deployments

Create preview environments for testing:

1. Create new branch: `git checkout -b feature/new-feature`
2. Create new Render service linked to this branch
3. Set different environment variables (staging values)
4. Test thoroughly before merging to main

## Database Management

### Running Migrations

Connect to Render shell:

```bash
# Via dashboard: Service → Shell tab

# Via CLI
render shell -s beacon-api
```

Then run migrations:

```bash
# Inside container
python scripts/run_migration.py
```

### Database Backups

Supabase handles backups automatically:
- Point-in-time recovery
- Daily automated backups
- Manual backups on demand

Access: Supabase Dashboard → Database → Backups

## Security Best Practices

### 1. Rotate API Keys

Rotate every 90 days:

```bash
# Generate new keys
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Update in Render dashboard
# Deploy to restart with new keys
# Update in Vercel frontend
```

### 2. Network Security

- ✅ HTTPS enforced automatically by Render
- ✅ TLS 1.2+ only
- ✅ HTTP/2 support
- ❌ No IP whitelisting on free tier (available on Team+ plans)

### 3. Secret Management

- ✅ Use Render's environment variables (encrypted at rest)
- ✅ Never log secrets in application
- ❌ Never commit secrets to repository
- ✅ Use different keys for staging/production

### 4. Rate Limiting

Implement application-level rate limiting (see Task 10).

## Cost Optimization

### Reduce Costs

1. **Use free tier for development**
   - Limited resources, but good for testing

2. **Sleep on inactivity** (free tier only)
   - Service sleeps after 15 minutes
   - Cold start: ~30 seconds

3. **Optimize Docker image size**
   - Multi-stage builds (already implemented)
   - .dockerignore excludes unnecessary files
   - Alpine base images where possible

4. **Monitor usage**
   - Check CPU/Memory metrics
   - Identify optimization opportunities

### Estimated Monthly Costs

| Scenario | Plan | Price | Notes |
|----------|------|-------|-------|
| Development | Free | $0 | Sleeps on inactivity |
| Light Production | Starter | $7 | 512MB RAM, always on |
| Production | Standard | $25 | 2GB RAM, better performance |
| High Traffic | Pro | $85 | 4GB RAM, autoscaling |

Add:
- Database: Supabase free tier or Pro ($25/mo)
- LLM API: Pay-per-use (varies)

## Troubleshooting

### Build Failures

**Error: "Docker build failed"**
- Check Dockerfile syntax
- Verify all COPY paths exist
- Review build logs for specific error

**Error: "requirements.txt not found"**
- Ensure requirements.txt is in root directory
- Check .dockerignore isn't excluding it

### Runtime Failures

**Error: "Module not found"**
- Verify all dependencies in requirements.txt
- Check Python version compatibility (3.10+)

**Error: "Permission denied"**
- Ensure non-root user has correct permissions
- Check chown commands in Dockerfile

**Error: "Health check timeout"**
- Increase health check timeout in render.yaml
- Check application is actually listening on port 8000
- Verify dependencies (DB, vector store) are accessible

### Performance Issues

**Slow response times:**
1. Check CPU/Memory usage in Metrics
2. Review logs for bottlenecks
3. Consider upgrading plan
4. Optimize database queries

**Frequent timeouts:**
1. Increase timeout values in config
2. Reduce concurrent operation limits
3. Scale horizontally (add instances)

## Advanced Configuration

### Custom Domain

1. Service → Settings → Custom Domains
2. Add your domain
3. Configure DNS:
   ```
   CNAME beacon-api.yourdomain.com → beacon-api.onrender.com
   ```
4. Wait for SSL certificate (~5-15 minutes)

### Background Workers

For long-running tasks, create separate worker service:

```yaml
# render.yaml
services:
  - type: web
    name: beacon-api
    # ... main API configuration

  - type: worker
    name: beacon-worker
    runtime: docker
    dockerfilePath: ./Dockerfile
    dockerCommand: python worker.py
    # ... worker-specific configuration
```

### Redis Cache

Add Redis for shared cache:

```yaml
# render.yaml
services:
  - type: web
    name: beacon-api
    # ... configuration
    envVars:
      - key: REDIS_URL
        fromService:
          type: redis
          name: beacon-redis
          property: connectionString

  - type: redis
    name: beacon-redis
    plan: starter
```

## Support & Resources

- [Render Documentation](https://render.com/docs)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- BEACON GitHub Issues

## Checklist

Before going live:

- [ ] All required environment variables set
- [ ] Secure API keys generated and configured
- [ ] CORS configured with production domains
- [ ] Health checks passing
- [ ] Database connected and migrations run
- [ ] Vector database initialized (ingestion complete)
- [ ] Frontend can successfully call backend
- [ ] Authentication working end-to-end
- [ ] Monitoring and alerting configured
- [ ] Backup and rollback procedures documented
- [ ] Load testing completed
- [ ] Security audit passed
