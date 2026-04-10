// ==UserScript==
// @name         EnPro Auto Test
// @namespace    http://tampermonkey.net/
// @version      1.0
// @match        https://enpro-fm-portal-v215-staging.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    setTimeout(function() {
        var btn = document.createElement('button');
        btn.innerHTML = 'Run Test';
        btn.style.position = 'fixed';
        btn.style.top = '80px';
        btn.style.right = '20px';
        btn.style.zIndex = '9999';
        btn.style.padding = '15px';
        btn.style.background = '#003366';
        btn.style.color = 'white';
        document.body.appendChild(btn);
        
        btn.onclick = function() {
            // Step 1
            document.getElementById('userInput').value = 'CLR10295';
            document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            
            // Step 2
            setTimeout(function() {
                document.getElementById('userInput').value = 'brewery meeting';
                document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            }, 6000);
            
            // Step 3
            setTimeout(function() {
                document.getElementById('userInput').value = 'compare HC9020FCN4Z vs HC9021FAS4Z';
                document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
            }, 12000);
        };
    }, 2000);
})();
