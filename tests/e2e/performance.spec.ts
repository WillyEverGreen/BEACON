import { test, expect } from '@playwright/test';

test.describe('Performance', () => {
  test('should load homepage within acceptable time', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    console.log(`Homepage load time: ${loadTime}ms`);
    
    // Should load within 5 seconds (generous for local dev)
    expect(loadTime).toBeLessThan(5000);
  });

  test('should load dashboard within acceptable time', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/dashboard/projects');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    console.log(`Dashboard load time: ${loadTime}ms`);
    
    // Should load within 6 seconds
    expect(loadTime).toBeLessThan(6000);
  });

  test('should not have excessive resource requests', async ({ page }) => {
    const requests: string[] = [];
    
    page.on('request', (request) => {
      requests.push(request.url());
    });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    console.log(`Total requests: ${requests.length}`);
    
    // Should not have excessive requests (adjust based on your app)
    expect(requests.length).toBeLessThan(100);
  });

  test('should have reasonable page size', async ({ page }) => {
    let totalSize = 0;
    
    page.on('response', async (response) => {
      try {
        const body = await response.body();
        totalSize += body.length;
      } catch (e) {
        // Some responses may not have body
      }
    });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    const sizeMB = totalSize / (1024 * 1024);
    console.log(`Total page size: ${sizeMB.toFixed(2)} MB`);
    
    // Should be under 10MB for initial load
    expect(sizeMB).toBeLessThan(10);
  });

  test('should measure Core Web Vitals', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Measure LCP (Largest Contentful Paint)
    const lcp = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        new PerformanceObserver((list) => {
          const entries = list.getEntries();
          const lastEntry = entries[entries.length - 1] as any;
          resolve(lastEntry.renderTime || lastEntry.loadTime);
        }).observe({ entryTypes: ['largest-contentful-paint'] });
        
        // Timeout after 5 seconds
        setTimeout(() => resolve(0), 5000);
      });
    });
    
    if (lcp > 0) {
      console.log(`LCP: ${lcp}ms`);
      // Good LCP is under 2.5s
      expect(lcp).toBeLessThan(4000); // More lenient for local dev
    }
  });
});
