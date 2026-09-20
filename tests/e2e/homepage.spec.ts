import { test, expect } from '@playwright/test';

test.describe('Homepage', () => {
  test('should load homepage successfully', async ({ page }) => {
    await page.goto('/');
    
    // Check if page loads
    await expect(page).toHaveTitle(/BEACON/i);
    
    // Verify main content is visible
    await expect(page.locator('body')).toBeVisible();
  });

  test('should have no console errors', async ({ page }) => {
    const errors: string[] = [];
    
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    
    // Filter out known acceptable errors (like development warnings)
    const criticalErrors = errors.filter(
      error => !error.includes('React DevTools') && 
               !error.includes('Download')
    );
    
    expect(criticalErrors).toHaveLength(0);
  });

  test('should have responsive navigation', async ({ page }) => {
    await page.goto('/');
    
    // Check if main navigation exists
    const nav = page.locator('nav, header');
    await expect(nav.first()).toBeVisible();
  });

  test('should handle accessibility attributes', async ({ page }) => {
    await page.goto('/');
    
    // Check for basic accessibility
    const mainContent = page.locator('main, [role="main"]');
    await expect(mainContent.first()).toBeVisible();
  });
});
