const { test, expect } = require('@playwright/test');

const SITE = 'https://enpro-fm-portal-v215-staging.onrender.com';

test('Find in stock parts', async ({ page, request }) => {
    await page.goto(SITE);
    
    const loginDropdown = page.locator('select').first();
    if (await loginDropdown.isVisible({ timeout: 5000 }).catch(() => false)) {
        await loginDropdown.selectOption({ index: 1 });
        await page.fill('input[type="password"], input[type="tel"]', '0000');
        await page.click('button:has-text("Sign In")');
        await page.waitForSelector('.welcome', { timeout: 15000 });
    }
    await page.waitForSelector('.welcome', { timeout: 15000 });
    
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map(c => `${c.name}=${c.value}`).join('; ');
    
    // Search for in-stock filters
    const res = await request.post(`${SITE}/api/search`, {
        headers: { 'Cookie': cookieHeader },
        data: { query: 'Pall', max_results: 20, in_stock_only: false }
    });
    
    const data = await res.json();
    
    console.log('\n=== IN STOCK PARTS ===');
    if (data.results) {
        data.results.slice(0, 10).forEach(p => {
            const pn = p.Part_Number || p.part_number || 'N/A';
            const stock = p.Total_Stock || p.total_stock || 0;
            console.log(`${pn}: ${stock} units`);
        });
    }
});
