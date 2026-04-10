const { test, expect } = require('@playwright/test');

const SITE = 'https://enpro-fm-portal-v215-staging.onrender.com';

test('Compare HC9020FCN4Z vs HC9021FAS4Z', async ({ page }) => {
    await page.goto(SITE);
    
    // Handle login if presented
    const loginDropdown = page.locator('select').first();
    if (await loginDropdown.isVisible({ timeout: 5000 }).catch(() => false)) {
        await loginDropdown.selectOption({ index: 1 }); // Select first user
        await page.fill('input[type="password"], input[type="tel"]', '0000');
        await page.click('button:has-text("Sign In")');
        await page.waitForSelector('.welcome', { timeout: 15000 });
    }
    
    await page.waitForSelector('.welcome', { timeout: 15000 });
    
    // Type compare query and press Enter
    await page.fill('#userInput', 'compare HC9020FCN4Z vs HC9021FAS4Z');
    await page.press('#userInput', 'Enter');
    
    // Wait for response
    await page.waitForSelector('.msg.bot', { timeout: 30000 });
    await page.waitForTimeout(4000); // Let everything render including follow-up
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    
    // Screenshot of the compare result
    await page.screenshot({ path: 'test-results/compare-hc9020-vs-hc9021.png', fullPage: true });
    
    // Also screenshot just the chat area
    const chatArea = page.locator('.chat-area');
    await chatArea.screenshot({ path: 'test-results/compare-chat-area.png' });
});
