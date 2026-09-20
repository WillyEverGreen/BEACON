# Deploying BEACON Frontend to Vercel

This guide walks through deploying the Next.js frontend to Vercel.

## Prerequisites

- [Vercel account](https://vercel.com/signup) (free tier works)
- GitHub repository with BEACON code
- Production backend deployed (see [render-backend.md](./render-backend.md))
- Supabase project created

## Quick Start

### 1. Connect Repository to Vercel

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click "Add New..." → "Project"
3. Import your GitHub repository
4. Vercel will auto-detect Next.js

### 2. Configure Build Settings

Vercel should auto-detect these, but verify:

- **Framework Preset**: Next.js
- **Root Directory**: `frontend`
- **Build Command**: `npm run build` (default)
- **Output Directory**: `.next` (default)
- **Install Command**: `npm install` (default)

### 3. Configure Environment Variables

Click "Environment Variables" and add the following:

#### Required Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://your-project.supabase.co` | From Supabase dashboard |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `eyJhbGci...` | From Supabase API settings |
| `BEACON_API_URL` | `https://beacon-api.onrender.com` | Your Render backend URL |
| `BOOTSTRAP_VIEWER_API_KEY` | (generate secure key) | Matches backend config |
| `BOOTSTRAP_AUDITOR_API_KEY` | (generate secure key) | Matches backend config |
| `BOOTSTRAP_ADMIN_API_KEY` | (generate secure key) | Matches backend config |

#### Optional Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXT_PUBLIC_ENABLE_AI_FEATURES` | `true` | Enable AI-powered features |
| `NEXT_PUBLIC_ENABLE_LIGHTHOUSE_ENRICHMENT` | `true` | Enable Lighthouse integration |
| `NEXT_PUBLIC_GA_ID` | `G-XXXXXXXXXX` | Google Analytics ID |
| `NEXT_PUBLIC_SENTRY_DSN` | `https://...` | Sentry error tracking |

#### Generating Secure API Keys

```bash
# Using Node.js
node -e "console.log(require('crypto').randomBytes(32).toString('base64'))"

# Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Using OpenSSL
openssl rand -base64 32
```

### 4. Deploy

1. Click "Deploy"
2. Vercel will build and deploy your application
3. Wait for deployment to complete (~2-3 minutes)
4. Visit your deployment URL

## Post-Deployment Configuration

### Custom Domain

1. Go to Project Settings → Domains
2. Add your custom domain
3. Configure DNS records as instructed
4. Wait for DNS propagation (~5-60 minutes)

### CORS Configuration

Update your backend's `BACKEND_CORS_ORIGINS` to include your Vercel domain:

```env
BACKEND_CORS_ORIGINS=https://your-app.vercel.app,https://your-domain.com
```

### Vercel Analytics

1. Go to Project Settings → Analytics
2. Enable "Vercel Analytics"
3. No code changes required

### Speed Insights

1. Go to Project Settings → Speed Insights
2. Enable "Speed Insights"
3. Monitor Core Web Vitals

## Environment Management

### Development vs Production

Vercel supports multiple environments:

- **Production**: Deployments from `main` branch
- **Preview**: Deployments from pull requests
- **Development**: Local development with `npm run dev`

### Environment Variables per Environment

You can set different values for each environment:

1. Go to Project Settings → Environment Variables
2. Select which environments each variable applies to:
   - Production
   - Preview
   - Development

Example:
- `BEACON_API_URL` (Production): `https://api.production.com`
- `BEACON_API_URL` (Preview): `https://api.staging.com`
- `BEACON_API_URL` (Development): `http://localhost:8000`

## Deployment Workflows

### Automatic Deployments

Vercel automatically deploys:
- **Production**: Every push to `main` branch
- **Preview**: Every pull request

### Manual Deployments

Deploy specific branches manually:

```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# Deploy to preview
vercel

# Deploy to production
vercel --prod
```

### Rollbacks

If a deployment fails:

1. Go to Deployments tab
2. Find a previous working deployment
3. Click "..." → "Promote to Production"

## Monitoring & Debugging

### View Logs

1. Go to Deployments → Select deployment
2. Click "View Function Logs"
3. Filter by type: Build, Edge, Functions

### Build Errors

Common issues:

**Missing environment variables:**
```
Error: Missing required environment variable: NEXT_PUBLIC_SUPABASE_URL
```
Solution: Add variables in Project Settings

**Type errors:**
```
Type error: Cannot find module '../lib/utils'
```
Solution: Fix import paths, ensure `npm install` ran

**Build timeouts:**
```
Error: Command "npm run build" timed out
```
Solution: Optimize build, increase timeout in vercel.json

### Runtime Errors

Check browser console:
- Press F12 → Console tab
- Look for errors related to API calls or Supabase

Common issues:

**CORS errors:**
```
Access to fetch blocked by CORS policy
```
Solution: Update backend `BACKEND_CORS_ORIGINS`

**Failed API calls:**
```
Failed to fetch backend API
```
Solution: Verify `BEACON_API_URL` and backend is running

## Performance Optimization

### Enable Caching

Add caching headers for static assets:

```typescript
// next.config.ts
async headers() {
  return [
    {
      source: '/static/:path*',
      headers: [
        {
          key: 'Cache-Control',
          value: 'public, max-age=31536000, immutable',
        },
      ],
    },
  ];
}
```

### Image Optimization

Vercel automatically optimizes images using Next.js Image component:

```tsx
import Image from 'next/image';

<Image
  src="/logo.png"
  alt="BEACON Logo"
  width={200}
  height={100}
  priority
/>
```

### Bundle Analysis

Analyze bundle size:

```bash
cd frontend
npm run build
npx @next/bundle-analyzer
```

## Security Best Practices

### 1. Protect API Keys

- ✅ Use `NEXT_PUBLIC_` prefix only for browser-safe values
- ✅ Server-side keys (BOOTSTRAP_*) are NOT exposed to browser
- ❌ Never log or expose API keys in client code

### 2. Content Security Policy

Add CSP headers in `next.config.ts`:

```typescript
{
  key: 'Content-Security-Policy',
  value: "default-src 'self'; script-src 'self' 'unsafe-eval' 'unsafe-inline';"
}
```

### 3. Rate Limiting

Vercel has built-in DDoS protection, but implement application-level rate limiting in backend.

### 4. Environment Variable Security

- ✅ Rotate API keys every 90 days
- ✅ Use Vercel's secret scanning
- ✅ Never commit `.env.local` or `.env.production`

## Troubleshooting

### Build Fails with "Cannot find module"

```bash
# Clear Vercel cache
vercel --force

# Or in dashboard: Settings → General → Clear Build Cache
```

### Environment Variables Not Working

1. Verify variable names exactly match (case-sensitive)
2. Redeploy after changing variables
3. Check if `NEXT_PUBLIC_` prefix is needed

### Frontend Can't Connect to Backend

1. Check CORS configuration on backend
2. Verify `BEACON_API_URL` is correct
3. Test backend health endpoint: `curl https://your-backend.com/health`

### Deployments Slow or Timing Out

1. Reduce bundle size (analyze with bundle analyzer)
2. Remove unused dependencies
3. Enable incremental builds in `next.config.ts`

## Advanced Configuration

### Custom Server

If you need custom server logic, deploy as Docker container instead:

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Edge Functions

Move API routes to Edge for better performance:

```typescript
// app/api/example/route.ts
export const runtime = 'edge';

export async function GET(request: Request) {
  return new Response('Hello from Edge');
}
```

### Incremental Static Regeneration (ISR)

Cache pages and revalidate periodically:

```typescript
export const revalidate = 3600; // Revalidate every hour

export default function Page({ data }) {
  return <div>{data}</div>;
}
```

## Cost Optimization

### Free Tier Limits

Vercel Pro plan recommended for production:
- 100 GB bandwidth
- Unlimited deployments
- Priority support

### Reduce Bandwidth Usage

1. Enable compression (default in Next.js)
2. Optimize images
3. Implement proper caching
4. Use CDN for static assets

## Support & Resources

- [Vercel Documentation](https://vercel.com/docs)
- [Next.js Documentation](https://nextjs.org/docs)
- [Vercel Support](https://vercel.com/support)
- BEACON GitHub Issues: [Report bugs](https://github.com/your-org/beacon/issues)

## Checklist

Before going live:

- [ ] All environment variables configured
- [ ] Custom domain set up
- [ ] CORS configured on backend
- [ ] Analytics enabled
- [ ] Error tracking (Sentry) configured
- [ ] Performance monitoring enabled
- [ ] Security headers verified
- [ ] SSL certificate active
- [ ] Tested authentication flow
- [ ] Tested API integrations
- [ ] Load testing completed
- [ ] Rollback plan documented
