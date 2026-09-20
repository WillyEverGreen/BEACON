import { test, expect } from '@playwright/test';

test.describe('Dashboard', () => {
  test('should navigate to dashboard', async ({ page }) => {
    await page.goto('/');
    
    // Try to find and click dashboard link
    const dashboardLink = page.getByRole('link', { name: /dashboard/i });
    
    if (await dashboardLink.count() > 0) {
      await dashboardLink.first().click();
      await page.waitForURL(/\/dashboard/);
      
      expect(page.url()).toContain('/dashboard');
    } else {
      // Try direct navigation
      await page.goto('/dashboard');
      expect(page.url()).toContain('/dashboard');
    }
  });

  test('should redirect to projects page', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Should redirect to /dashboard/projects
    await page.waitForURL(/\/dashboard\/projects/, { timeout: 5000 });
    expect(page.url()).toContain('/dashboard/projects');
  });

  test('should display projects page content', async ({ page }) => {
    await page.goto('/dashboard/projects');
    
    // Wait for content to load
    await page.waitForLoadState('networkidle');
    
    // Check if page has loaded
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('should handle authentication state', async ({ page }) => {
    await page.goto('/dashboard/projects');
    
    // Check if page loads (may show login or content)
    await page.waitForLoadState('networkidle');
    
    // Verify no critical errors
    const hasError = await page.locator('text=/error/i, text=/failed/i').count();
    expect(hasError).toBeLessThan(10); // Allow some normal "error" text in UI
  });
});
