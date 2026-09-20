# BEACON E2E Tests

End-to-end tests using Playwright for comprehensive browser testing.

## Quick Start

### Install Playwright

```bash
npm install
npx playwright install
```

### Run Tests

```bash
# Run all tests (headless)
npm run test:e2e

# Run with visible browser
npm run test:e2e:headed

# Run in interactive UI mode
npm run test:e2e:ui

# Run in debug mode
npm run test:e2e:debug

# Run specific browser
npm run test:e2e:chromium
npm run test:e2e:firefox

# View test report
npm run test:e2e:report
```

## Test Suites

| Test File | Description | Tests |
|-----------|-------------|-------|
| `homepage.spec.ts` | Homepage functionality | Page load, console errors, navigation |
| `dashboard.spec.ts` | Dashboard features | Navigation, routing, content display |
| `project-creation.spec.ts` | Project creation flow | Form submission, navigation, page state |
| `real-website-audit.spec.ts` | Live site audit testing | Multi-site audit runs, responsive checks |
| `api-integration.spec.ts` | API interactions | Request handling, errors, loading |
| `navigation.spec.ts` | Site navigation | Page flow, links, session |
| `performance.spec.ts` | Performance metrics | Load times, Core Web Vitals |
| `accessibility.spec.ts` | Accessibility | ARIA, keyboard nav, semantics |


## Test Structure

```typescript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test('should do something', async ({ page }) => {
    // Navigate
    await page.goto('/');
    
    // Interact
    await page.click('button');
    
    // Assert
    await expect(page.getByText('Success')).toBeVisible();
  });
});
```

## Running Specific Tests

```bash
# Run single file
npx playwright test homepage.spec.ts

# Run tests matching pattern
npx playwright test -g "should load"

# Run specific browser
npx playwright test --project=chromium

# Run in headed mode
npx playwright test --headed

# Run with debugging
npx playwright test --debug
```

## Debugging

### UI Mode (Recommended)
```bash
npm run test:e2e:ui
```

Features:
- Visual test runner
- Time-travel debugging
- Step through actions
- Watch mode

### Debug Mode
```bash
npm run test:e2e:debug
```

### PowerShell Script
```powershell
# Run all tests
.\scripts\run_e2e_tests.ps1

# Run with options
.\scripts\run_e2e_tests.ps1 -Headed
.\scripts\run_e2e_tests.ps1 -UI
.\scripts\run_e2e_tests.ps1 -Project chromium
.\scripts\run_e2e_tests.ps1 -Test homepage.spec.ts
```

## Test Reports

After running tests:

```bash
# View HTML report
npx playwright show-report
```

Report includes:
- ✅ Test results
- 📸 Screenshots (on failure)
- 🎥 Videos (on failure)
- 🔍 Trace viewer
- ⏱️ Timing information

## Configuration

Edit `playwright.config.ts` in project root:

```typescript
export default defineConfig({
  testDir: './tests/e2e',
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
});
```

## Writing Tests

### Best Practices

✅ **DO:**
- Use semantic selectors (`getByRole`, `getByText`, `getByLabel`)
- Wait for proper states (`waitForLoadState`, `toBeVisible`)
- Clean up after tests (localStorage, cookies)
- Write descriptive test names
- Keep tests independent

❌ **DON'T:**
- Use brittle CSS selectors (`.class`, `#id`)
- Use hard-coded waits (`setTimeout`)
- Make tests depend on each other
- Test implementation details
- Ignore flaky tests

### Example Test

```typescript
test('user can submit form', async ({ page }) => {
  // Navigate to page
  await page.goto('/dashboard/projects');
  
  // Fill form
  await page.getByLabel('Project Name').fill('Test Project');
  await page.getByLabel('URL').fill('https://example.com');
  
  // Submit
  await page.getByRole('button', { name: 'Create' }).click();
  
  // Verify success
  await expect(page.getByText('Project created')).toBeVisible();
});
```

## Troubleshooting

### Tests Fail to Start
```bash
# Reinstall browsers
npx playwright install --force

# Clear npm cache
npm cache clean --force
npm install
```

### Tests Timeout
```typescript
// Increase timeout in test
test.setTimeout(60000); // 60 seconds

// Or in config
timeout: 30 * 1000,
```

### Flaky Tests
```typescript
// Add retries
test.describe.configure({ retries: 2 });

// Use explicit waits
await expect(element).toBeVisible();

// Wait for network
await page.waitForLoadState('networkidle');
```

## CI/CD Integration

Tests automatically run in GitHub Actions:

```yaml
- name: Install Playwright
  run: npx playwright install --with-deps

- name: Run E2E tests
  run: npm run test:e2e

- name: Upload results
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: playwright-report/
```

## Resources

- 📚 [Full Testing Guide](../../docs/testing/E2E_TESTING_GUIDE.md)
- 🎭 [Playwright Docs](https://playwright.dev/)
- 🎓 [Playwright University](https://playwright.dev/docs/intro)
- 🛠️ [VS Code Extension](https://marketplace.visualstudio.com/items?itemName=ms-playwright.playwright)

## Test Coverage

Current test coverage:

- ✅ Homepage loading and navigation
- ✅ Dashboard routing and display
- ✅ API integration and error handling
- ✅ Navigation flow and links
- ✅ Performance metrics (load times, resources)
- ✅ Accessibility (ARIA, keyboard, semantics)

## Next Steps

1. Run tests locally: `npm run test:e2e:ui`
2. Review test results and traces
3. Add tests for new features
4. Update tests when UI changes
5. Keep tests passing in CI/CD

---

**Happy Testing! 🎭**
