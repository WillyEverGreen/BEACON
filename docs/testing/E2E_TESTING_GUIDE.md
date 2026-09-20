# BEACON E2E Testing Guide

Comprehensive guide for running end-to-end tests with Playwright.

---

## Quick Start

### Run All Tests

```bash
# Headless mode (default)
npx playwright test

# With visible browser
npx playwright test --headed

# UI mode (interactive)
npx playwright test --ui

# Debug mode
npx playwright test --debug
```

### Using PowerShell Script

```powershell
# Run all tests
.\scripts\run_e2e_tests.ps1

# Run with visible browser
.\scripts\run_e2e_tests.ps1 -Headed

# Run in UI mode
.\scripts\run_e2e_tests.ps1 -UI

# Run specific browser
.\scripts\run_e2e_tests.ps1 -Project chromium

# Run specific test
.\scripts\run_e2e_tests.ps1 -Test homepage.spec.ts
```

---

## Test Suites

### 1. Homepage Tests (`homepage.spec.ts`)

Tests basic homepage functionality:
- ✅ Page loads successfully
- ✅ No console errors
- ✅ Responsive navigation
- ✅ Accessibility attributes

### 2. Dashboard Tests (`dashboard.spec.ts`)

Tests dashboard functionality:
- ✅ Navigation to dashboard
- ✅ Redirect to projects page
- ✅ Content display
- ✅ Authentication state handling

### 3. API Integration Tests (`api-integration.spec.ts`)

Tests API interactions:
- ✅ API request handling
- ✅ Error handling
- ✅ Loading states

### 4. Navigation Tests (`navigation.spec.ts`)

Tests navigation flow:
- ✅ Page-to-page navigation
- ✅ 404 handling
- ✅ Internal links
- ✅ Session persistence

### 5. Performance Tests (`performance.spec.ts`)

Tests performance metrics:
- ✅ Page load times
- ✅ Resource count
- ✅ Page size
- ✅ Core Web Vitals

### 6. Accessibility Tests (`accessibility.spec.ts`)

Tests accessibility compliance:
- ✅ Page structure
- ✅ Form labels
- ✅ Keyboard navigation
- ✅ Color contrast
- ✅ Image alt text
- ✅ Button semantics

---

## Setup

### First Time Setup

1. **Install Dependencies**
   ```bash
   npm install
   ```

2. **Install Playwright Browsers**
   ```bash
   npx playwright install
   ```

3. **Verify Installation**
   ```bash
   npx playwright test --list
   ```

### Environment Setup

The tests expect the frontend to be running on `http://localhost:3000`.

**Option 1: Auto-start (Default)**
- Tests automatically start `npm run dev` in frontend directory
- No manual action needed

**Option 2: Manual start**
```bash
cd frontend
npm run dev
```

Then run tests with:
```bash
npx playwright test
```

---

## Running Tests

### All Tests

```bash
# Run all tests in all browsers
npx playwright test

# Run in specific browser
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

### Specific Test File

```bash
# Run single test file
npx playwright test homepage.spec.ts

# Run test file in specific browser
npx playwright test homepage.spec.ts --project=chromium
```

### Specific Test Case

```bash
# Run specific test by name
npx playwright test -g "should load homepage"

# Run tests matching pattern
npx playwright test -g "navigation"
```

### Watch Mode

```bash
# Watch for changes and rerun
npx playwright test --watch
```

---

## Debugging Tests

### UI Mode (Recommended)

```bash
npx playwright test --ui
```

Features:
- Visual test runner
- Step-through debugging
- Time travel through test execution
- Watch mode

### Debug Mode

```bash
# Debug specific test
npx playwright test homepage.spec.ts --debug

# Debug in headed mode
npx playwright test --headed --debug
```

### Browser DevTools

```bash
# Open browser devtools during test
PWDEBUG=1 npx playwright test
```

### VS Code Debugging

Install the [Playwright Test for VSCode](https://marketplace.visualstudio.com/items?itemName=ms-playwright.playwright) extension for:
- Run tests from editor
- Set breakpoints
- Watch mode
- Test generation

---

## Test Reports

### HTML Report (Default)

```bash
# Run tests
npx playwright test

# View report
npx playwright show-report
```

Opens an interactive HTML report with:
- Test results
- Screenshots on failure
- Video recordings
- Trace viewer

### Other Reporters

```bash
# List reporter (terminal output)
npx playwright test --reporter=list

# JSON reporter
npx playwright test --reporter=json

# JUnit reporter (for CI)
npx playwright test --reporter=junit
```

---

## Configuration

### Browser Configuration

Edit `playwright.config.ts`:

```typescript
projects: [
  {
    name: 'chromium',
    use: { ...devices['Desktop Chrome'] },
  },
  {
    name: 'firefox',
    use: { ...devices['Desktop Firefox'] },
  },
  // Add more browsers/devices
]
```

### Test Settings

```typescript
use: {
  // Base URL
  baseURL: 'http://localhost:3000',
  
  // Screenshot on failure
  screenshot: 'only-on-failure',
  
  // Video on failure
  video: 'retain-on-failure',
  
  // Trace on retry
  trace: 'on-first-retry',
  
  // Slow down actions (for debugging)
  slowMo: 100,
}
```

### Timeouts

```typescript
// Global timeout
timeout: 30 * 1000, // 30 seconds

// Test timeout
testTimeout: 60 * 1000, // 60 seconds

// Expect timeout
expect: {
  timeout: 5000, // 5 seconds
}
```

---

## Best Practices

### 1. Use Proper Selectors

```typescript
// ✅ Good - semantic locators
await page.getByRole('button', { name: 'Submit' });
await page.getByText('Welcome');
await page.getByLabel('Email');

// ❌ Avoid - brittle selectors
await page.locator('.btn-primary');
await page.locator('#submit-btn');
```

### 2. Wait for States

```typescript
// Wait for network idle
await page.waitForLoadState('networkidle');

// Wait for specific element
await expect(page.getByText('Loaded')).toBeVisible();

// Wait for navigation
await page.waitForURL('/dashboard');
```

### 3. Handle Async Operations

```typescript
// Wait for API response
await page.waitForResponse(response => 
  response.url().includes('/api/audit')
);

// Wait for event
await page.waitForEvent('load');
```

### 4. Clean Up After Tests

```typescript
test.afterEach(async ({ page }) => {
  // Clear localStorage
  await page.evaluate(() => localStorage.clear());
  
  // Clear cookies
  await page.context().clearCookies();
});
```

### 5. Use Fixtures

```typescript
import { test as base } from '@playwright/test';

const test = base.extend({
  authenticatedPage: async ({ page }, use) => {
    // Set up authentication
    await page.goto('/login');
    await page.fill('[name="email"]', 'test@example.com');
    await page.fill('[name="password"]', 'password');
    await page.click('button[type="submit"]');
    
    await use(page);
  },
});

test('dashboard requires auth', async ({ authenticatedPage }) => {
  await authenticatedPage.goto('/dashboard');
  // Test with authenticated session
});
```

---

## CI/CD Integration

### GitHub Actions

Already configured in `.github/workflows/deploy.yml`:

```yaml
- name: Run E2E tests
  run: npx playwright test
  
- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: playwright-report/
```

### Running in CI

```bash
# CI mode (no retries, fail fast)
CI=1 npx playwright test
```

---

## Troubleshooting

### Tests Fail Locally

1. **Clear browser cache**
   ```bash
   npx playwright install --force
   ```

2. **Update dependencies**
   ```bash
   npm update @playwright/test
   ```

3. **Check frontend is running**
   ```bash
   curl http://localhost:3000
   ```

### Tests Timeout

1. **Increase timeout**
   ```typescript
   test.setTimeout(60000); // 60 seconds
   ```

2. **Check network speed**
   ```bash
   # Slow down network for testing
   npx playwright test --slow-mo=1000
   ```

3. **Wait for proper state**
   ```typescript
   await page.waitForLoadState('networkidle');
   ```

### Flaky Tests

1. **Add explicit waits**
   ```typescript
   await expect(element).toBeVisible();
   ```

2. **Use retry logic**
   ```typescript
   test.describe.configure({ retries: 2 });
   ```

3. **Stabilize selectors**
   ```typescript
   // Use data-testid for stability
   await page.locator('[data-testid="submit"]').click();
   ```

---

## Writing New Tests

### Test Template

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test.beforeEach(async ({ page }) => {
    // Setup before each test
    await page.goto('/');
  });
  
  test('should do something', async ({ page }) => {
    // Arrange
    const button = page.getByRole('button', { name: 'Click me' });
    
    // Act
    await button.click();
    
    // Assert
    await expect(page.getByText('Success')).toBeVisible();
  });
  
  test.afterEach(async ({ page }) => {
    // Cleanup after each test
  });
});
```

### Test Organization

```
tests/e2e/
├── homepage.spec.ts       # Homepage tests
├── dashboard.spec.ts      # Dashboard tests
├── api-integration.spec.ts # API tests
├── navigation.spec.ts     # Navigation tests
├── performance.spec.ts    # Performance tests
└── accessibility.spec.ts  # A11y tests
```

---

## Performance Testing

### Measure Load Time

```typescript
test('load time', async ({ page }) => {
  const start = Date.now();
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  const loadTime = Date.now() - start;
  
  expect(loadTime).toBeLessThan(3000); // 3 seconds
});
```

### Measure Core Web Vitals

```typescript
test('LCP', async ({ page }) => {
  await page.goto('/');
  
  const lcp = await page.evaluate(() => {
    return new Promise((resolve) => {
      new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        resolve(lastEntry.renderTime || lastEntry.loadTime);
      }).observe({ entryTypes: ['largest-contentful-paint'] });
    });
  });
  
  expect(lcp).toBeLessThan(2500); // Good LCP
});
```

---

## Resources

- [Playwright Documentation](https://playwright.dev/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Test Generator](https://playwright.dev/docs/codegen)
- [Trace Viewer](https://playwright.dev/docs/trace-viewer)
- [VS Code Extension](https://playwright.dev/docs/getting-started-vscode)

---

## Support

For issues or questions:
1. Check [Playwright Issues](https://github.com/microsoft/playwright/issues)
2. Review test output and traces
3. Use debug mode: `npx playwright test --debug`
4. Check `playwright-report/` for details

---

**Happy Testing! 🎭**
