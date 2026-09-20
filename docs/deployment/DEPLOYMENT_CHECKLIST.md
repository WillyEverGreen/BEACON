# BEACON Production Deployment Checklist

Complete this checklist before deploying BEACON to production.

---

## Pre-Deployment Checklist

### 1. Environment Configuration

#### Backend (.env)

- [ ] All placeholder values replaced (no `your-*`, `example-*`, `xxx-*`)
- [ ] `ENVIRONMENT=production` set
- [ ] Valid `NVIDIA_API_KEY` configured
- [ ] Valid `SUPABASE_URL` and `SUPABASE_KEY` configured
- [ ] Strong API keys generated (min 32 characters):
  - [ ] `BOOTSTRAP_VIEWER_API_KEY`
  - [ ] `BOOTSTRAP_AUDITOR_API_KEY`
  - [ ] `BOOTSTRAP_ADMIN_API_KEY`
- [ ] CORS origins set to production frontend domain(s)
- [ ] Rate limiting configured appropriately
- [ ] No `.env` file committed to git

#### Frontend (.env.local)

- [ ] `NEXT_PUBLIC_SUPABASE_URL` matches backend Supabase project
- [ ] `NEXT_PUBLIC_SUPABASE_ANON_KEY` configured
- [ ] `BEACON_API_URL` points to production backend
- [ ] Bootstrap API keys match backend configuration
- [ ] Feature flags set appropriately
- [ ] No `.env.local` file committed to git

### 2. Security Verification

- [ ] API key authentication enabled (`AUTH_ENABLED=true`)
- [ ] Strong API keys in use (not default/placeholder)
- [ ] CORS restricted to production domains only
- [ ] Rate limiting enabled and configured
- [ ] HTTPS enforced (Vercel and Render auto-provide)
- [ ] Security headers configured
- [ ] No secrets in source code
- [ ] SSRF protection enabled (default)

### 3. Database Setup

- [ ] Supabase project created
- [ ] Database tables created (run migrations if any)
- [ ] Row Level Security (RLS) policies configured
- [ ] Database backups enabled
- [ ] Connection pooling configured

### 4. Code Quality

- [ ] All print statements replaced with logging
- [ ] No hardcoded credentials in code
- [ ] No TODO/FIXME in critical paths
- [ ] Error handling implemented
- [ ] Logging configured (JSON format in production)
- [ ] Type hints added to public APIs

### 5. Build & Test

- [ ] Backend builds successfully: `docker build -t beacon .`
- [ ] Frontend builds successfully: `cd frontend && npm run build`
- [ ] Unit tests pass (if implemented)
- [ ] Integration tests pass (if implemented)
- [ ] Environment validation passes on startup

### 6. Documentation

- [ ] README.md updated with production setup
- [ ] API documentation generated/updated
- [ ] Deployment guides reviewed
- [ ] Environment variable reference complete
- [ ] Security documentation reviewed

---

## Render Deployment (Backend)

### Initial Setup

1. **Create Render Account**
   - [ ] Sign up at https://render.com
   - [ ] Connect GitHub repository

2. **Create Web Service**
   - [ ] New > Web Service
   - [ ] Select BEACON repository
   - [ ] Branch: `main`
   - [ ] Runtime: Docker
   - [ ] Region: Oregon (or nearest to users)
   - [ ] Plan: Starter ($7/month minimum)

3. **Configure Environment Variables**

   Copy from `.env.example` and set in Render dashboard:

   **Required:**
   ```
   ENVIRONMENT=production
   NVIDIA_API_KEY=<your-key>
   LLM_MODEL=meta/llama-3.1-70b-instruct
   LLM_BASE_URL=https://integrate.api.nvidia.com/v1
   SUPABASE_URL=<your-project-url>
   SUPABASE_KEY=<your-anon-key>
   CORS_ORIGINS=https://your-app.vercel.app
   ```

   **API Keys (generate secure random values):**
   ```
   BOOTSTRAP_VIEWER_API_KEY=<generate-32-char-random>
   BOOTSTRAP_AUDITOR_API_KEY=<generate-32-char-random>
   BOOTSTRAP_ADMIN_API_KEY=<generate-32-char-random>
   ```

   **Optional (adjust as needed):**
   ```
   RATE_LIMIT_ENABLED=true
   RATE_LIMIT_PER_MINUTE=60
   RATE_LIMIT_PER_HOUR=1000
   MAX_REQUEST_SIZE_MB=10
   BACKEND_LOG_LEVEL=INFO
   ```

4. **Deploy**
   - [ ] Click "Create Web Service"
   - [ ] Wait for build to complete (5-10 minutes first time)
   - [ ] Check logs for errors
   - [ ] Verify health endpoint: `https://your-app.onrender.com/health`

5. **Post-Deployment Verification**

   Run verification script:
   ```bash
   bash scripts/verify_render_deployment.sh \
     https://your-app.onrender.com \
     your-viewer-api-key
   ```

   Manual checks:
   - [ ] Health endpoint returns 200
   - [ ] Authentication works (test with API key)
   - [ ] CORS headers present
   - [ ] Rate limiting works
   - [ ] Error responses formatted correctly
   - [ ] Logs appearing in Render dashboard

---

## Vercel Deployment (Frontend)

### Initial Setup

1. **Create Vercel Account**
   - [ ] Sign up at https://vercel.com
   - [ ] Connect GitHub repository

2. **Import Project**
   - [ ] New Project > Import from GitHub
   - [ ] Select BEACON repository
   - [ ] Root Directory: `frontend`
   - [ ] Framework Preset: Next.js
   - [ ] Build Command: `npm run build` (default)
   - [ ] Output Directory: `.next` (default)

3. **Configure Environment Variables**

   In Vercel Project Settings > Environment Variables:

   **Production:**
   ```
   NEXT_PUBLIC_SUPABASE_URL=<your-supabase-project-url>
   NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
   BEACON_API_URL=https://your-app.onrender.com
   BOOTSTRAP_VIEWER_API_KEY=<matches-backend>
   BOOTSTRAP_AUDITOR_API_KEY=<matches-backend>
   BOOTSTRAP_ADMIN_API_KEY=<matches-backend>
   ```

   **Optional:**
   ```
   BEACON_AI_ENABLED=true
   BEACON_LIGHTHOUSE_ENRICHMENT_ENABLED=true
   NEXT_PUBLIC_ENABLE_REALTIME=true
   ```

   - [ ] All required variables set
   - [ ] API keys match backend configuration
   - [ ] Supabase project matches backend

4. **Deploy**
   - [ ] Click "Deploy"
   - [ ] Wait for build to complete (3-5 minutes)
   - [ ] Check build logs for errors
   - [ ] Verify deployment at `https://your-app.vercel.app`

5. **Post-Deployment Verification**

   Run verification script:
   ```bash
   bash scripts/verify_frontend_config.sh
   ```

   Manual checks:
   - [ ] Homepage loads without errors
   - [ ] Can access /dashboard
   - [ ] API calls to backend work
   - [ ] Authentication flow works
   - [ ] No console errors in browser
   - [ ] Security headers present (check DevTools Network tab)
   - [ ] Images load correctly

---

## Post-Deployment Configuration

### 1. Custom Domain (Optional)

**Vercel (Frontend):**
- [ ] Project Settings > Domains > Add Domain
- [ ] Update DNS records (A/CNAME as instructed)
- [ ] Wait for SSL certificate (automatic)
- [ ] Test HTTPS access

**Render (Backend):**
- [ ] Service Settings > Custom Domain
- [ ] Add domain (e.g., api.yourdomain.com)
- [ ] Update DNS records
- [ ] Wait for SSL certificate (automatic)
- [ ] Update frontend `BEACON_API_URL` to custom domain

### 2. Update CORS

After custom domain setup:

**Backend (Render):**
```
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

Redeploy backend after updating.

### 3. Monitoring Setup

- [ ] Enable Vercel Analytics
- [ ] Configure Render log retention
- [ ] Set up uptime monitoring (e.g., UptimeRobot)
- [ ] Configure error alerts
- [ ] Set up log aggregation (optional: Papertrail, Datadog)

### 4. Backup Strategy

- [ ] Supabase automatic backups enabled (free tier: daily)
- [ ] Export initial database snapshot
- [ ] Document recovery procedures
- [ ] Test restoration process

---

## Verification Testing

### Backend API Tests

```bash
API_URL="https://your-app.onrender.com"
API_KEY="your-viewer-api-key"

# Health check
curl $API_URL/health

# Authentication test
curl -H "X-API-Key: $API_KEY" $API_URL/v1/rag/health

# CORS test
curl -H "Origin: https://your-app.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS $API_URL/v1/audit

# Rate limit test (should return headers)
curl -v -H "X-API-Key: $API_KEY" $API_URL/v1/rag/health
```

### Frontend Tests

1. **Navigation**
   - [ ] Homepage loads
   - [ ] /dashboard accessible
   - [ ] /dashboard/projects loads
   - [ ] Navigation between pages works

2. **Functionality**
   - [ ] Can start audit
   - [ ] Audit results display
   - [ ] RAG chat works (if enabled)
   - [ ] Error states display correctly

3. **Performance**
   - [ ] Initial load < 3s
   - [ ] Pages interactive < 1s
   - [ ] No console errors
   - [ ] No memory leaks

---

## Rollback Plan

### If Deployment Fails

**Vercel (Frontend):**
1. Go to Deployments tab
2. Find last working deployment
3. Click "..." > "Promote to Production"

**Render (Backend):**
1. Manual rollback via Render dashboard
2. Or: revert git commit and push
3. Auto-deploy will trigger

### Emergency Procedures

1. **Total outage:**
   - Disable both services
   - Post status update
   - Investigate locally
   - Deploy fix to staging first

2. **Partial outage:**
   - Identify failing component
   - Rollback that component only
   - Monitor other components

3. **Data corruption:**
   - Stop write operations immediately
   - Restore from latest backup
   - Verify data integrity
   - Resume operations

---

## Post-Deployment Monitoring

### First 24 Hours

- [ ] Monitor error logs continuously
- [ ] Check API response times
- [ ] Verify no rate limit issues
- [ ] Watch for authentication failures
- [ ] Monitor memory/CPU usage
- [ ] Check database connection pool

### First Week

- [ ] Daily log review
- [ ] Performance metrics trending up/down
- [ ] User-reported issues
- [ ] Database growth rate
- [ ] API usage patterns
- [ ] Cost monitoring

### Ongoing

- [ ] Weekly log reviews
- [ ] Monthly security audits
- [ ] Quarterly dependency updates
- [ ] API key rotation
- [ ] Backup testing
- [ ] Disaster recovery drills

---

## Troubleshooting

### Common Issues

**Build fails on Render:**
- Check Dockerfile syntax
- Verify all dependencies in requirements.txt
- Check Docker build logs for errors
- Ensure sufficient disk space

**Build fails on Vercel:**
- Check package.json dependencies
- Verify Node version compatibility
- Check environment variables set
- Review build logs

**API returns 500 errors:**
- Check Render logs
- Verify environment variables
- Test database connection
- Check LLM API quota/limits

**CORS errors:**
- Verify CORS_ORIGINS includes frontend domain
- Check protocol (http vs https)
- Verify no trailing slashes
- Redeploy after CORS changes

**Authentication fails:**
- Verify API keys match between frontend/backend
- Check key format (no extra whitespace)
- Verify AUTH_ENABLED=true
- Check request headers

**Rate limiting too aggressive:**
- Increase RATE_LIMIT_PER_MINUTE/HOUR
- Check if same IP shared by multiple users
- Consider API key-based tracking only

---

## Support Contacts

- **Render Support**: https://render.com/docs/support
- **Vercel Support**: https://vercel.com/support
- **Supabase Support**: https://supabase.com/support
- **NVIDIA API**: https://build.nvidia.com/support

---

## Deployment Sign-Off

Deployment completed by: _________________  
Date: _________________  
Version: _________________  
Frontend URL: _________________  
Backend URL: _________________  

Verified by: _________________  
Date: _________________  

---

**Last Updated**: January 2024  
**Version**: 1.0  
**Next Review**: After first deployment
