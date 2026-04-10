const { test, expect } = require('@playwright/test');

const SITE = 'https://enpro-fm-portal-v215-staging.onrender.com';

test('Compare Debug', async ({ page, request }) => {
    await page.goto(SITE);
    
    // Handle login
    const loginDropdown = page.locator('select').first();
    if (await loginDropdown.isVisible({ timeout: 5000 }).catch(() => false)) {
        await loginDropdown.selectOption({ index: 1 });
        await page.fill('input[type="password"], input[type="tel"]', '0000');
        await page.click('button:has-text("Sign In")');
        await page.waitForSelector('.welcome', { timeout: 15000 });
    }
    
    // Get cookies for auth
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map(c => `${c.name}=${c.value}`).join('; ');
    
    // Call API directly (non-streaming)
    const apiResponse = await request.post(`${SITE}/api/chat`, {
        headers: { 'Cookie': cookieHeader },
        data: { 
            message: 'compare HC9020FCN4Z vs HC9021FAS4Z',
            session_id: 'test-' + Date.now()
        }
    });
    
    const data = await apiResponse.json();
    
    console.log('=== API RESPONSE ===');
    console.log('Intent:', data.intent);
    console.log('Has products:', !!data.products);
    console.log('Product count:', data.products?.length);
    console.log('Products:', data.products?.map(p => p.Part_Number || p.part_number));
    console.log('Response preview:', data.response?.substring(0, 200));
    
    // Now do the UI test
    await page.fill('#userInput', 'compare HC9020FCN4Z vs HC9021FAS4Z');
    await page.press('#userInput', 'Enter');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'test-results/compare-debug.png', fullPage: true });
});
