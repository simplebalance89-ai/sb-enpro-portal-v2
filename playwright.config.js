const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
    testDir: './tests',
    timeout: 60000,
    retries: 0,
    use: {
        baseURL: 'https://enpro-fm-portal-v215-staging.onrender.com',
        screenshot: 'on',
        video: 'on',
        trace: 'on',
    },
    reporter: [['html', { open: 'never' }], ['list']],
    projects: [
        {
            name: 'chromium',
            use: { browserName: 'chromium', viewport: { width: 1280, height: 900 } },
        },
    ],
    outputDir: './test-results',
});
