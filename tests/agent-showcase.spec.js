// Agent showcase — runs real scenarios through the live UI, captures
// video + screenshots of every interaction so you can actually SEE the
// agent work, not just read pass/fail numbers.

const { test, expect } = require('@playwright/test');

const LIVE_URL = 'https://enpro-fm-mastermind-gctii.orangeglacier-52c78cce.eastus.azurecontainerapps.io/';

// Helper: type into the chat input and send the message
async function sendMessage(page, text) {
    const input = page.locator('#userInput');
    await input.click();
    await input.fill(text);
    await page.keyboard.press('Enter');
    // Wait for the bot to finish responding (typing indicator gone)
    await page.waitForTimeout(500);
    await page.waitForFunction(
        () => {
            const typing = document.querySelector('#typingIndicator, .typing');
            if (!typing) return true;
            const style = window.getComputedStyle(typing);
            return style.display === 'none' || !typing.classList.contains('active');
        },
        { timeout: 45000 }
    ).catch(() => {});
    // Small settle delay for render
    await page.waitForTimeout(1500);
}

// Helper: wait for a bot message to appear after the user's
async function waitForBotResponse(page, previousCount) {
    await page.waitForFunction(
        (prev) => document.querySelectorAll('.msg.bot, .bot-msg').length > prev,
        previousCount,
        { timeout: 60000 }
    ).catch(() => {});
}

test.describe('Enpro Agent Showcase', () => {
    test.setTimeout(180000);

    test('01 - Part lookup: CLR510', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');
        await page.screenshot({ path: 'test-results/01-initial.png', fullPage: true });

        await sendMessage(page, 'lookup CLR510');
        await page.screenshot({ path: 'test-results/01-clr510-result.png', fullPage: true });
    });

    test('02 - Manufacturer search: Pall', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');
        await sendMessage(page, 'manufacturer Pall');
        await page.screenshot({ path: 'test-results/02-pall-result.png', fullPage: true });
    });

    test('03 - Chemical compatibility: sulfuric acid', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');
        await sendMessage(page, 'chemical compatibility of sulfuric acid');
        await page.screenshot({ path: 'test-results/03-sulfuric-acid.png', fullPage: true });
    });

    test('04 - Brewery pregame meeting', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');
        await sendMessage(page, 'I have a brewery customer meeting tomorrow, recommend some in stock part numbers and questions to ask him');
        await page.screenshot({ path: 'test-results/04-brewery-pregame.png', fullPage: true });
    });

    test('05 - Multi-turn context: Pall → prices → stock → compare', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');

        await sendMessage(page, 'manufacturer Pall 10 micron');
        await page.screenshot({ path: 'test-results/05a-pall-search.png', fullPage: true });

        await sendMessage(page, 'what are the prices on those?');
        await page.screenshot({ path: 'test-results/05b-prices-follow-up.png', fullPage: true });

        await sendMessage(page, 'which of those are in stock?');
        await page.screenshot({ path: 'test-results/05c-stock-follow-up.png', fullPage: true });

        await sendMessage(page, 'compare the first two');
        await page.screenshot({ path: 'test-results/05d-compare.png', fullPage: true });
    });

    test('06 - CLR510 → substitute flow', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');

        await sendMessage(page, 'part number CLR510');
        await page.screenshot({ path: 'test-results/06a-clr510-lookup.png', fullPage: true });

        await sendMessage(page, 'is it in stock');
        await page.screenshot({ path: 'test-results/06b-stock-check.png', fullPage: true });

        await sendMessage(page, 'find me a substitute');
        await page.screenshot({ path: 'test-results/06c-substitute.png', fullPage: true });
    });

    test('07 - In-stock query: brewery', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');
        await sendMessage(page, 'what brewery filters are in stock');
        await page.screenshot({ path: 'test-results/07-in-stock-brewery.png', fullPage: true });
    });

    test('08 - Edge case: 500F hydrogen service (escalation)', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');
        await sendMessage(page, 'I need a filter for 500F hydrogen service');
        await page.screenshot({ path: 'test-results/08-escalation.png', fullPage: true });
    });

    test('09 - Out of scope', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');
        await sendMessage(page, "what's the weather today");
        await page.screenshot({ path: 'test-results/09-out-of-scope.png', fullPage: true });
    });

    test('10 - Full brewery conversation (4 turns)', async ({ page }) => {
        await page.goto(LIVE_URL);
        await page.waitForLoadState('networkidle');

        await sendMessage(page, 'I run a brewery');
        await page.screenshot({ path: 'test-results/10a-brewery-intro.png', fullPage: true });

        await sendMessage(page, 'what filters do I need for yeast carryover');
        await page.screenshot({ path: 'test-results/10b-yeast.png', fullPage: true });

        await sendMessage(page, 'are any of those in stock in Houston');
        await page.screenshot({ path: 'test-results/10c-houston-stock.png', fullPage: true });

        await sendMessage(page, 'what questions should I ask before my meeting');
        await page.screenshot({ path: 'test-results/10d-meeting-prep.png', fullPage: true });
    });
});
