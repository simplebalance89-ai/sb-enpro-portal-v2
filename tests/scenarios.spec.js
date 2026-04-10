const { test, expect } = require('@playwright/test');

const SITE = 'https://enpro-fm-portal-v215-staging.onrender.com';

// Helper to login
async function login(page) {
    const loginDropdown = page.locator('select').first();
    if (await loginDropdown.isVisible({ timeout: 5000 }).catch(() => false)) {
        await loginDropdown.selectOption({ index: 1 });
        await page.fill('input[type="password"], input[type="tel"]', '0000');
        await page.click('button:has-text("Sign In")');
        await page.waitForSelector('.welcome', { timeout: 15000 });
    }
}

// Helper to send message and wait for content
async function sendAndWait(page, message) {
    await page.fill('#userInput', message);
    await page.press('#userInput', 'Enter');
    // Wait for any bot response to appear
    await page.waitForSelector('.msg.bot', { timeout: 30000 });
    // Wait a bit more for streaming to finish
    await page.waitForTimeout(3000);
    // Scroll to see everything
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
}

test.describe('10 Scenarios', () => {
    
    test('1. Compare HC9020 vs HC9021', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'compare HC9020FCN4Z vs HC9021FAS4Z');
        await page.screenshot({ path: 'test-results/01-compare.png', fullPage: true });
    });

    test('2. Brewery pregame', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'I have a meeting tomorrow for a brewery');
        await page.screenshot({ path: 'test-results/02-pregame-brewery.png', fullPage: true });
    });

    test('3. Data center pregame', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'meeting with data center HVAC operator');
        await page.screenshot({ path: 'test-results/03-pregame-dc.png', fullPage: true });
    });

    test('4. Part lookup CLR10295', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'CLR10295');
        await page.screenshot({ path: 'test-results/04-lookup.png', fullPage: true });
    });

    test('5. Chemical sulfuric acid', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'chemical compatibility sulfuric acid');
        await page.screenshot({ path: 'test-results/05-chemical.png', fullPage: true });
    });

    test('6. Search 10 micron filter', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, '10 micron filter cartridge');
        await page.screenshot({ path: 'test-results/06-search.png', fullPage: true });
    });

    test('7. Manufacturer Pall', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'manufacturer Pall');
        await page.screenshot({ path: 'test-results/07-manufacturer.png', fullPage: true });
    });

    test('8. Price check', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'price CLR130');
        await page.screenshot({ path: 'test-results/08-price.png', fullPage: true });
    });

    test('9. Compare CLR series', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'compare CLR130 vs CLR140');
        await page.screenshot({ path: 'test-results/09-compare-clr.png', fullPage: true });
    });

    test('10. Pharma pregame', async ({ page }) => {
        await page.goto(SITE);
        await login(page);
        await sendAndWait(page, 'customer meeting pharmaceutical filtration');
        await page.screenshot({ path: 'test-results/10-pregame-pharma.png', fullPage: true });
    });

});
