const { test, expect } = require('@playwright/test');

const SITE = 'https://enpro-fm-portal-v215-staging.onrender.com';

test('Pregame brewery UI test', async ({ page }) => {
    await page.goto(SITE);
    
    // Handle login if presented
    const loginDropdown = page.locator('select').first();
    if (await loginDropdown.isVisible({ timeout: 5000 }).catch(() => false)) {
        await loginDropdown.selectOption({ index: 1 });
        await page.fill('input[type="password"], input[type="tel"]', '0000');
        await page.click('button:has-text("Sign In")');
        await page.waitForSelector('.welcome', { timeout: 15000 });
    }
    
    await page.waitForSelector('.welcome', { timeout: 15000 });
    
    // Type pregame query
    await page.fill('#userInput', 'I have a customer and a meeting tomorrow for a brewery');
    await page.press('#userInput', 'Enter');
    
    // Wait for response
    await page.waitForSelector('.msg.bot', { timeout: 30000 });
    await page.waitForTimeout(4000);
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    
    // Screenshot
    await page.screenshot({ path: 'test-results/pregame-brewery-ui.png', fullPage: true });
});
