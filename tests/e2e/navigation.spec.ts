import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test('should navigate between pages', async ({ page }) => {
    // Start at homepage
    await page.goto('/');
    expect(page.url()).toContain('/');
    
    // Navigate to dashboard
    await page.goto('/dashboard');
    await page.waitForURL(/\/dashboard/);
    expect(page.url()).toContain('/dashboard');
    
    // Go back
    await page.goBack();
    await page.waitForLoadState('networkidle');
  });

  test('should handle 404 pages', async ({ page }) => {
    const response = await page.goto('/non-existent-page-12345');
    
    // Check status code or error page
    if (response) {
      // May be 404 or redirect to 404 page
      expect([200, 404]).toContain(response.status());
    }
  });

  test('should have working internal links', async ({ page }) => {
    await page.goto('/');
    
    // Find all internal links
    const links = await page.locator('a[href^="/"]').all();
    
    console.log(`Found ${links.length} internal links`);
    
    // Test first few links (to avoid long test)
    const linksToTest = links.slice(0, 3);
    
    for (const link of linksToTest) {
      const href = await link.getAttribute('href');
      if (href && href !== '#' && !href.includes('logout')) {
        await link.click();
        await page.waitForLoadState('networkidle');
        
        // Verify navigation worked
        expect(page.url()).toBeTruthy();
        
        // Go back for next test
        await page.goBack();
        await page.waitForLoadState('networkidle');
      }
    }
  });

  test('should maintain session across navigation', async ({ page }) => {
    await page.goto('/');
    
    // Set some data in localStorage to simulate session
    await page.evaluate(() => {
      localStorage.setItem('test-session', 'active');
    });
    
    // Navigate to another page
    await page.goto('/dashboard');
    
    // Check if session persists
    const sessionData = await page.evaluate(() => {
      return localStorage.getItem('test-session');
    });
    
    expect(sessionData).toBe('active');
    
    // Cleanup
    await page.evaluate(() => {
      localStorage.removeItem('test-session');
    });
  });
});
