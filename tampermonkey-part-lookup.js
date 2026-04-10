// ==UserScript==
// @name         EnPro Part Lookup Tests
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  5 part number lookup scenarios
// @match        https://enpro-fm-portal.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    var lookups = [
        { name: 'CLR140', part: 'CLR140XK' },
        { name: 'HC9020', part: 'HC9020FCN4Z' },
        { name: 'UE210', part: 'UE210AT20Z' },
        { name: 'PRS10', part: 'PRS10-40' },
        { name: 'HFU660', part: 'HFU660U220ZH13' }
    ];
    
    var container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.top = '300px';
    container.style.right = '20px';
    container.style.zIndex = '9999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '8px';
    
    var label = document.createElement('div');
    label.innerHTML = 'Part Lookup';
    label.style.background = '#006600';
    label.style.color = 'white';
    label.style.padding = '8px 12px';
    label.style.borderRadius = '6px';
    label.style.fontSize = '12px';
    label.style.fontWeight = 'bold';
    label.style.textAlign = 'center';
    container.appendChild(label);
    
    lookups.forEach(function(item) {
        var btn = document.createElement('button');
        btn.innerHTML = item.name;
        btn.style.padding = '10px 16px';
        btn.style.background = '#009900';
        btn.style.color = 'white';
        btn.style.border = 'none';
        btn.style.borderRadius = '6px';
        btn.style.cursor = 'pointer';
        btn.style.fontSize = '11px';
        
        btn.onclick = function() {
            btn.disabled = true;
            btn.innerHTML = 'Looking up...';
            btn.style.background = '#999';
            
            setTimeout(function() {
                var input = document.getElementById('userInput');
                if (input) {
                    input.value = item.part;
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
                }
                btn.innerHTML = 'Done';
            }, 100);
            
            setTimeout(function() {
                btn.innerHTML = item.name;
                btn.disabled = false;
                btn.style.background = '#009900';
            }, 4000);
        };
        
        container.appendChild(btn);
    });
    
    setTimeout(function() {
        document.body.appendChild(container);
    }, 2000);
    
})();
