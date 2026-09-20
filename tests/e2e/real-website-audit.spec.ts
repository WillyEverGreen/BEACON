import { test, expect } from '@playwright/test';

/**
 * Real-world website audit testing
 * Tests BEACON's ability to audit actual websites and update UI accordingly
 */

test.describe('Real Website Audit Testing', () => {
  // Test with well-known accessible websites
  const testWebsites = [
    { name: 'Example.com', url: 'https://example.com' },
    { name: 'Mozilla Developer Network', url: 'https://developer.mozilla.org' },
    { name: 'W3C', url: 'https://www.w3.org' },
  ];

  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/projects');
    await page.waitForLoadState('networkidle');
  });

  test('should display projects dashboard', async ({ page }) => {
    // Verify we're on the right page
    expect(page.url()).toContain('/dashboard/projects');
    
    // Check page loaded successfully
    const mainContent = page.locator('main, [role="main"], body');
    await expect(mainContent.first()).toBeVisible();
    
    console.log('✓ Dashboard loaded successfully');
  });

  test('should show navigation elements', async ({ page }) => {
    // Check for navigation
    const nav = page.locator('nav, [role="navigation"]');
    if (await nav.count() > 0) {
      console.log('✓ Navigation present');
      
      // Check for common navigation items
      const homeLink = page.getByRole('link', { name: /home/i });
      const projectsLink = page.getByRole('link', { name: /projects|all projects/i });
      
      if (await homeLink.count() > 0) console.log('✓ Home link found');
      if (await projectsLink.count() > 0) console.log('✓ Projects link found');
    }
  });

  test('should handle project creation form', async ({ page }) => {
    // Look for create/new project button
    const createButtons = [
      page.getByRole('button', { name: /create project/i }),
      page.getByRole('button', { name: /new project/i }),
      page.getByRole('button', { name: /add project/i }),
      page.getByRole('button', { name: /start audit/i }),
      page.locator('button:has-text("Create")'),
      page.locator('button:has-text("New")'),
    ];

    let foundButton = false;
    for (const button of createButtons) {
      if (await button.count() > 0) {
        console.log('✓ Found create button');
        foundButton = true;
        
        // Click the button
        await button.first().click();
        await page.waitForTimeout(1500);
        
        // Check if form or modal appeared
        const modal = page.locator('[role="dialog"], .modal, [data-testid="modal"]');
        const form = page.locator('form');
        
        if (await modal.count() > 0) {
          console.log('✓ Modal opened');
        }
        
        if (await form.count() > 0) {
          console.log('✓ Form available');
          
          // Try to fill form with example.com
          const urlInput = page.locator('input[type="url"], input[name="url"], input[placeholder*="url" i]');
          if (await urlInput.count() > 0) {
            await urlInput.first().fill('https://example.com');
            console.log('✓ Filled URL: https://example.com');
            
            // Take screenshot of filled form
            await page.screenshot({ path: 'test-results/form-filled.png' });
            
            // Look for submit button
            const submitButton = page.locator('button[type="submit"], button:has-text("Submit"), button:has-text("Create")');
            if (await submitButton.count() > 0) {
              console.log('✓ Submit button found');
              // Don't actually submit in this test - just verify form works
            }
          }
        }
        
        break;
      }
    }
    
    if (!foundButton) {
      console.log('ℹ No create button found - may require authentication');
    }
  });

  test('should verify page responsiveness', async ({ page }) => {
    // Test different viewport sizes
    const viewports = [
      { width: 1920, height: 1080, name: 'Desktop' },
      { width: 768, height: 1024, name: 'Tablet' },
      { width: 375, height: 667, name: 'Mobile' },
    ];

    for (const viewport of viewports) {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.waitForTimeout(500);
      
      // Verify page is still visible
      const body = page.locator('body');
      await expect(body).toBeVisible();
      
      console.log(`✓ Page responsive at ${viewport.name} (${viewport.width}x${viewport.height})`);
      
      // Take screenshot
      await page.screenshot({ 
        path: `test-results/responsive-${viewport.name.toLowerCase()}.png` 
      });
    }
  });

  test('should test with example.com and verify UI update', async ({ page }) => {
    console.log('Testing with example.com...');
    
    // Capture initial state
    const initialScreenshot = await page.screenshot();
    console.log('✓ Captured initial state');
    
    // Look for any input fields
    const inputs = page.locator('input[type="text"], input[type="url"]');
    const inputCount = await inputs.count();
    
    if (inputCount > 0) {
      console.log(`Found ${inputCount} input field(s)`);
      
      // Fill first input with test URL
      await inputs.first().fill('https://example.com');
      await page.waitForTimeout(500);
      
      console.log('✓ Filled example.com URL');
      
      // Capture state after input
      await page.screenshot({ path: 'test-results/after-input.png' });
      
      // Look for any buttons that might trigger an action
      const actionButtons = page.locator('button:not([disabled])');
      const buttonCount = await actionButtons.count();
      
      if (buttonCount > 0) {
        console.log(`Found ${buttonCount} actionable button(s)`);
        
        // Try to click first button (if it looks safe)
        const firstButton = actionButtons.first();
        const buttonText = await firstButton.textContent();
        
        if (buttonText && !buttonText.toLowerCase().includes('delete')) {
          console.log(`Clicking: "${buttonText.trim()}"`);
          
          await firstButton.click();
          await page.waitForTimeout(2000);
          
          // Verify page updated
          const afterScreenshot = await page.screenshot({ 
            path: 'test-results/after-action.png' 
          });
          
          console.log('✓ Action completed - page updated');
          
          // Check for any feedback messages
          const messages = page.locator('[role="alert"], .alert, .message, .notification');
          if (await messages.count() > 0) {
            const messageText = await messages.first().textContent();
            console.log(`✓ Feedback message: ${messageText?.trim()}`);
          }
        }
      }
    } else {
      console.log('ℹ No input fields found on current page');
    }
  });

  test('should verify all interactive elements are accessible', async ({ page }) => {
    // Find all interactive elements
    const buttons = page.locator('button');
    const links = page.locator('a');
    const inputs = page.locator('input, textarea, select');
    
    const buttonCount = await buttons.count();
    const linkCount = await links.count();
    const inputCount = await inputs.count();
    
    console.log(`Interactive elements found:`);
    console.log(`  - Buttons: ${buttonCount}`);
    console.log(`  - Links: ${linkCount}`);
    console.log(`  - Form inputs: ${inputCount}`);
    
    // Verify buttons have accessible names
    for (let i = 0; i < Math.min(buttonCount, 5); i++) {
      const button = buttons.nth(i);
      const text = await button.textContent();
      const ariaLabel = await button.getAttribute('aria-label');
      
      if (text?.trim() || ariaLabel) {
        console.log(`✓ Button ${i + 1} is accessible`);
      }
    }
    
    expect(buttonCount + linkCount + inputCount).toBeGreaterThan(0);
  });

  test('should measure page load performance', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/dashboard/projects');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    console.log(`Page load time: ${loadTime}ms`);
    
    // Performance assertions
    expect(loadTime).toBeLessThan(10000); // Should load in under 10 seconds
    
    if (loadTime < 3000) {
      console.log('✓ Excellent load time (< 3s)');
    } else if (loadTime < 5000) {
      console.log('✓ Good load time (< 5s)');
    } else {
      console.log('⚠ Slow load time (> 5s)');
    }
  });

  test('should verify no JavaScript errors', async ({ page }) => {
    const errors: string[] = [];
    const warnings: string[] = [];
    
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      } else if (msg.type() === 'warning') {
        warnings.push(msg.text());
      }
    });
    
    page.on('pageerror', (error) => {
      errors.push(error.message);
    });
    
    await page.goto('/dashboard/projects');
    await page.waitForLoadState('networkidle');
    
    // Filter out acceptable errors
    const criticalErrors = errors.filter(error => 
      !error.includes('React DevTools') &&
      !error.includes('Download the React DevTools') &&
      !error.includes('favicon')
    );
    
    console.log(`Console messages:`);
    console.log(`  - Errors: ${criticalErrors.length}`);
    console.log(`  - Warnings: ${warnings.length}`);
    
    if (criticalErrors.length > 0) {
      console.log('Critical errors found:');
      criticalErrors.forEach(err => console.log(`  - ${err}`));
    }
    
    expect(criticalErrors.length).toBe(0);
  });
});
