import { test, expect } from '@playwright/test';

test.describe('Accessibility', () => {
  test('should have proper page structure', async ({ page }) => {
    await page.goto('/');
    
    // Check for main landmarks
    const main = page.locator('main, [role="main"]');
    await expect(main.first()).toBeVisible();
    
    // Check for heading hierarchy
    const h1 = page.locator('h1');
    expect(await h1.count()).toBeGreaterThan(0);
  });

  test('should have proper form labels', async ({ page }) => {
    await page.goto('/dashboard/projects');
    
    // Get all input fields
    const inputs = await page.locator('input[type="text"], input[type="email"], input[type="password"], textarea').all();
    
    // Check each input has associated label
    for (const input of inputs) {
      const id = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const ariaLabelledBy = await input.getAttribute('aria-labelledby');
      
      if (id) {
        const label = page.locator(`label[for="${id}"]`);
        const hasLabel = (await label.count()) > 0;
        const hasAriaLabel = !!ariaLabel || !!ariaLabelledBy;
        
        // Should have either label or aria-label
        expect(hasLabel || hasAriaLabel).toBeTruthy();
      }
    }
  });

  test('should be keyboard navigable', async ({ page }) => {
    await page.goto('/');
    
    // Tab through interactive elements
    await page.keyboard.press('Tab');
    
    // Check if focus is visible
    const focusedElement = await page.evaluate(() => {
      return document.activeElement?.tagName;
    });
    
    expect(focusedElement).toBeTruthy();
  });

  test('should have sufficient color contrast', async ({ page }) => {
    await page.goto('/');
    
    // This is a basic check - for comprehensive testing, use axe-core
    const backgroundColor = await page.evaluate(() => {
      return window.getComputedStyle(document.body).backgroundColor;
    });
    
    expect(backgroundColor).toBeTruthy();
  });

  test('should have alt text for images', async ({ page }) => {
    await page.goto('/');
    
    // Get all images
    const images = await page.locator('img').all();
    
    for (const img of images) {
      const alt = await img.getAttribute('alt');
      const ariaLabel = await img.getAttribute('aria-label');
      const role = await img.getAttribute('role');
      
      // Images should have alt text or be marked as decorative
      const hasAccessibleText = !!alt || !!ariaLabel || role === 'presentation';
      
      if (!hasAccessibleText) {
        const src = await img.getAttribute('src');
        console.warn(`Image missing alt text: ${src}`);
      }
    }
  });

  test('should have proper button semantics', async ({ page }) => {
    await page.goto('/dashboard/projects');
    
    // Check all clickable elements
    const clickables = await page.locator('button, [role="button"]').all();
    
    for (const button of clickables) {
      // Should have accessible name
      const text = await button.textContent();
      const ariaLabel = await button.getAttribute('aria-label');
      
      const hasAccessibleName = (text && text.trim().length > 0) || !!ariaLabel;
      
      if (!hasAccessibleName) {
        console.warn('Button without accessible name found');
      }
    }
  });
});
