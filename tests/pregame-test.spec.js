const { test, expect } = require('@playwright/test');

const SITE = 'https://enpro-fm-portal-v215-staging.onrender.com';

test('Pregame brewery meeting', async ({ page, request }) => {
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
    
    // Get cookies for auth
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map(c => `${c.name}=${c.value}`).join('; ');
    
    // Call API directly
    const apiResponse = await request.post(`${SITE}/api/chat`, {
        headers: { 'Cookie': cookieHeader },
        data: { 
            message: 'I have a customer and a meeting tomorrow for a brewery',
            session_id: 'test-' + Date.now()
        }
    });
    
    const data = await apiResponse.json();
    
    console.log('=== PREGAME TEST ===');
    console.log('Intent:', data.intent);
    console.log('Structured:', data.structured);
    console.log('Headline:', data.headline);
    console.log('Follow-up:', data.follow_up);
    console.log('Picks:', JSON.stringify(data.picks, null, 2));
    console.log('Body:', data.body);
    console.log('Response:', data.response);
});
