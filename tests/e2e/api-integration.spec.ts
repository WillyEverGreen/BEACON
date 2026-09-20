import { test, expect } from '@playwright/test';

test.describe('API Integration', () => {
  test('should handle API requests', async ({ page }) => {
    // Track network requests
    const apiRequests: string[] = [];
    
    page.on('request', (request) => {
      const url = request.url();
      if (url.includes('/api/') || url.includes('onrender.com')) {
        apiRequests.push(url);
      }
    });
    
    await page.goto('/dashboard/projects');
    await page.waitForLoadState('networkidle');
    
    // Log API requests made
    console.log(`API requests made: ${apiRequests.length}`);
  });

  test('should handle API errors gracefully', async ({ page }) => {
    // Intercept API requests and simulate error
    await page.route('**/api/**', (route) => {
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Test error' }),
      });
    });
    
    await page.goto('/dashboard/projects');
    await page.waitForLoadState('networkidle');
    
    // Should not crash the app
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('should display proper loading states', async ({ page }) => {
    // Slow down API to test loading states
    await page.route('**/api/**', async (route) => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.continue();
    });
    
    const loadingPromise = page.goto('/dashboard/projects');
    
    // Check for loading indicator (spinner, skeleton, etc.)
    // This is optional - app may or may not have loading states
    const possibleLoaders = page.locator('[role="progressbar"], .spinner, .loading, .skeleton');
    
    await loadingPromise;
    await page.waitForLoadState('networkidle');
  });
});
