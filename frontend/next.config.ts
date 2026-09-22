import type { NextConfig } from "next";

/**
 * Validate required environment variables at build time
 */
function validateEnv() {
  const requiredPublicVars = [
    'NEXT_PUBLIC_SUPABASE_URL',
    'NEXT_PUBLIC_SUPABASE_ANON_KEY',
  ];
  
  const requiredServerVars = [
    'BEACON_API_URL',
  ];
  
  const missing: string[] = [];
  
  // Check public vars
  requiredPublicVars.forEach(varName => {
    if (!process.env[varName]) {
      missing.push(varName);
    }
  });
  
  // Check server vars (only in production builds)
  if (process.env.NODE_ENV === 'production') {
    requiredServerVars.forEach(varName => {
      if (!process.env[varName]) {
        missing.push(varName);
      }
    });
  }
  
  if (missing.length > 0) {
    console.error('❌ Missing required environment variables:');
    missing.forEach(varName => {
      console.error(`   - ${varName}`);
    });
    console.error('\nPlease configure these environment variables in your Vercel Project Settings → Environment Variables:');
    console.error('   1. NEXT_PUBLIC_SUPABASE_URL');
    console.error('   2. NEXT_PUBLIC_SUPABASE_ANON_KEY');
    console.error('   3. BEACON_API_URL (e.g. https://your-backend.onrender.com)');
    console.error('See frontend/.env.example for the complete list.\n');
    
    if (process.env.NODE_ENV === 'production' && !process.env.CI_SKIP_ENV_VALIDATION) {
      throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
    }
  } else {
    console.log('✅ Environment variables validated');
  }
}

// Run validation
validateEnv();

const nextConfig: NextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  
  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on'
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=31536000; includeSubDomains'
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff'
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY'
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block'
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin'
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=(), interest-cohort=()'
          }
        ],
      },
    ];
  },
  
  // Image optimization domains
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.supabase.co',
      },
    ],
  },
  
  // Redirects for legacy routes
  async redirects() {
    return [];
  },
  
  // Environment variables to expose to the browser
  env: {
    NEXT_PUBLIC_APP_VERSION: process.env.npm_package_version || '3.0.0',
  },
  
  // Production optimizations
  ...(process.env.NODE_ENV === 'production' && {
    compress: true,
    poweredByHeader: false,
    generateEtags: true,
  }),
};

export default nextConfig;

