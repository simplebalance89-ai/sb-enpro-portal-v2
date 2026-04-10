// ==UserScript==
// @name         EnPro Convo 1 - Brewery
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  4-turn conversation: pregame brewery → specs → compare → close
// @match        https://enpro-fm-portal-v215-staging.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    var btn = document.createElement('button');
    btn.innerHTML = '▶️ Convo 1: Brewery';
    btn.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;padding:12px 20px;background:#0066CC;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;';
    
    btn.onclick = function() {
        btn.disabled = true;
        btn.innerHTML = 'Running...';
        console.log('🎬 CONVERSATION 1 START');
        
        // Turn 1: Pregame
        setTimeout(function() {
            console.log('TURN 1: Pregame brewery');
            document.getElementById('userInput').value = 'I have a brewery customer meeting tomorrow';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T1/4: Pregame';
        }, 100);
        
        // Turn 2: Follow-up on specs (as if responding to pregame)
        setTimeout(function() {
            console.log('TURN 2: Ask about current specs');
            document.getElementById('userInput').value = 'They are using 5 micron right now but getting inconsistent batches';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T2/4: Specs';
        }, 8000);
        
        // Turn 3: Compare options
        setTimeout(function() {
            console.log('TURN 3: Compare recommendations');
            document.getElementById('userInput').value = 'compare 12247 vs HTS1P2PP-H';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T3/4: Compare';
        }, 16000);
        
        // Turn 4: Close question
        setTimeout(function() {
            console.log('TURN 4: Closing question');
            document.getElementById('userInput').value = 'what is the lead time for the Pall option';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T4/4: Close';
        }, 24000);
        
        // Done
        setTimeout(function() {
            console.log('✅ CONVERSATION 1 COMPLETE');
            btn.innerHTML = '🔄 Run Again';
            btn.disabled = false;
        }, 32000);
    };
    
    setTimeout(function() {
        document.body.appendChild(btn);
        console.log('Conversation 1 ready');
    }, 2000);
    
})();
