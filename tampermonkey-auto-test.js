// ==UserScript==
// @name         EnPro Auto Test Sequence
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Auto-run: lookup → pregame → compare
// @match        https://enpro-fm-portal*.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const PRE_GAMES = [
        'I have a meeting tomorrow for a brewery',
        'customer meeting data center HVAC operator',
        'pregame for pharmaceutical filtration',
        'meeting with wastewater treatment plant',
        'customer call food processing filters'
    ];

    const COMPARE_PAIRS = [
        ['HC9020FCN4Z', 'HC9021FAS4Z'],
        ['CLR130', 'CLR140'],
        ['12247', '12941']
    ];

    function wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function typeMessage(text) {
        const input = document.getElementById('userInput');
        if (!input) return;
        input.value = text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function sendMessage() {
        const input = document.getElementById('userInput');
        if (!input) return;
        const event = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter' });
        input.dispatchEvent(event);
    }

    async function runSequence() {
        console.log('🎬 STARTING TEST SEQUENCE');

        // Step 1: Part lookup
        console.log('Step 1: Part lookup CLR10295');
        typeMessage('CLR10295');
        await wait(500);
        sendMessage();
        await wait(5000);

        // Step 2: Random pregame
        const pregame = PRE_GAMES[Math.floor(Math.random() * PRE_GAMES.length)];
        console.log('Step 2: Pregame -', pregame);
        typeMessage(pregame);
        await wait(500);
        sendMessage();
        await wait(6000);

        // Step 3: Compare
        const pair = COMPARE_PAIRS[Math.floor(Math.random() * COMPARE_PAIRS.length)];
        const compareMsg = `compare ${pair[0]} vs ${pair[1]}`;
        console.log('Step 3: Compare -', compareMsg);
        typeMessage(compareMsg);
        await wait(500);
        sendMessage();
        await wait(5000);

        console.log('✅ SEQUENCE COMPLETE');
        btn.textContent = '🔄 Run Again';
        btn.disabled = false;
    }

    // Create button
    const btn = document.createElement('button');
    btn.textContent = '▶️ Run Test Sequence';
    btn.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;padding:15px 25px;background:#003366;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:14px;';
    btn.onclick = () => {
        btn.disabled = true;
        btn.textContent = '⏳ Running...';
        runSequence();
    };

    setTimeout(() => document.body.appendChild(btn), 2000);
    console.log('🔴 EnPro Auto Test - Click button to start');

})();
