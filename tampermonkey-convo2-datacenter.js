// ==UserScript==
// @name         EnPro Convo 2 - Data Center
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  4-turn conversation: data center pregame → requirements → suggest → check stock
// @match        https://enpro-fm-portal-v215-staging.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    var btn = document.createElement('button');
    btn.innerHTML = '▶️ Convo 2: Data Center';
    btn.style.cssText = 'position:fixed;top:140px;right:20px;z-index:9999;padding:12px 20px;background:#28a745;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;';
    
    btn.onclick = function() {
        btn.disabled = true;
        btn.innerHTML = 'Running...';
        console.log('🎬 CONVERSATION 2 START');
        
        // Turn 1: Pregame data center
        setTimeout(function() {
            console.log('TURN 1: Data center meeting');
            document.getElementById('userInput').value = 'meeting with data center HVAC operator about filtration';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T1/4: Pregame';
        }, 100);
        
        // Turn 2: Drill down on requirements
        setTimeout(function() {
            console.log('TURN 2: Air quality requirements');
            document.getElementById('userInput').value = 'they need MERV 14 or higher for their server rooms';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T2/4: Requirements';
        }, 8000);
        
        // Turn 3: Suggest specific parts
        setTimeout(function() {
            console.log('TURN 3: What do you recommend');
            document.getElementById('userInput').value = 'what 4 inch depth options do we have in MERV 14';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T3/4: Suggest';
        }, 16000);
        
        // Turn 4: Check stock
        setTimeout(function() {
            console.log('TURN 4: Stock check');
            document.getElementById('userInput').value = 'is CLR140 in stock';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            btn.innerHTML = 'T4/4: Stock';
        }, 24000);
        
        // Done
        setTimeout(function() {
            console.log('✅ CONVERSATION 2 COMPLETE');
            btn.innerHTML = '🔄 Run Again';
            btn.disabled = false;
        }, 32000);
    };
    
    setTimeout(function() {
        document.body.appendChild(btn);
        console.log('Conversation 2 ready');
    }, 2000);
    
})();
