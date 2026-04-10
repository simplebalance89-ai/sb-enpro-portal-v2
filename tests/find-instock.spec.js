const { test, expect } = require('@playwright/test');

const SITE = 'https://enpro-fm-portal-v215-staging.onrender.com';

test('Find 5 in-stock parts', async ({ page, request }) => {
    await page.goto(SITE);
    
    // Login
    const loginDropdown = page.locator('select').first();
    if (await loginDropdown.isVisible({ timeout: 5000 }).catch(() => false)) {
        await loginDropdown.selectOption({ index: 1 });
        await page.fill('input[type="password"]', '0000');
        await page.click('button:has-text("Sign In")');
        await page.waitForSelector('.welcome', { timeout: 15000 });
    }
    
    const cookies = await page.context().cookies();
    const cookieHeader = cookies.map(c => `${c.name}=${c.value}`).join('; ');
    
    // Search for parts and check stock
    const searchTerms = ['filter', 'cartridge', 'element', 'CLR', 'HC90'];
    let foundInStock = [];
    
    for (const term of searchTerms) {
        if (foundInStock.length >= 5) break;
        
        const res = await request.post(`${SITE}/api/search`, {
            headers: { 'Cookie': cookieHeader },
            data: { 
                query: term,
                max_results: 10,
                in_stock_only: true
            }
        });
        
        const data = await res.json();
        if (data.results) {
            for (const p of data.results) {
                if (foundInStock.length >= 5) break;
                const stock = p.Total_Stock || p.total_stock || 0;
                if (stock > 0) {
                    foundInStock.push({
                        pn: p.Part_Number || p.part_number,
                        stock: stock,
                        desc: p.Description || p.description
                    });
                }
            }
        }
    }
    
    console.log('\n=== IN STOCK PARTS ===');
    foundInStock.forEach(p => {
        console.log(`${p.pn}: ${p.stock} units - ${p.desc?.substring(0, 40)}`);
    });
});
