// ==UserScript==
// @name         EnPro Compare Tests
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  5 compare scenarios
// @match        https://enpro-fm-portal.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    var compares = [
        { name: 'CLR140 vs CLR130', query: 'compare CLR140XK vs CLR130' },
        { name: 'HC9020 vs HC9021', query: 'compare HC9020FCN4Z vs HC9021FAS4Z' },
        { name: 'UE210 vs UE219', query: 'compare UE210AT20Z vs UE219AT20Z' },
        { name: 'PRS10 vs PRS5', query: 'compare PRS10-40 vs PRS5-40' },
        { name: 'Ultipleat vs Marksman', query: 'compare Ultipleat HF vs Marksman' }
    ];
    
    var container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.top = '300px';
    container.style.right = '120px';
    container.style.zIndex = '9999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '8px';
    
    var label = document.createElement('div');
    label.innerHTML = 'Compare';
    label.style.background = '#CC6600';
    label.style.color = 'white';
    label.style.padding = '8px 12px';
    label.style.borderRadius = '6px';
    label.style.fontSize = '12px';
    label.style.fontWeight = 'bold';
    label.style.textAlign = 'center';
    container.appendChild(label);
    
    compares.forEach(function(item) {
        var btn = document.createElement('button');
        btn.innerHTML = item.name;
        btn.style.padding = '10px 16px';
        btn.style.background = '#FF8800';
        btn.style.color = 'white';
        btn.style.border = 'none';
        btn.style.borderRadius = '6px';
        btn.style.cursor = 'pointer';
        btn.style.fontSize = '11px';
        
        btn.onclick = function() {
            btn.disabled = true;
            btn.innerHTML = 'Comparing...';
            btn.style.background = '#999';
            
            setTimeout(function() {
                var input = document.getElementById('userInput');
                if (input) {
                    input.value = item.query;
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
                }
                btn.innerHTML = 'Done';
            }, 100);
            
            setTimeout(function() {
                btn.innerHTML = item.name;
                btn.disabled = false;
                btn.style.background = '#FF8800';
            }, 6000);
        };
        
        container.appendChild(btn);
    });
    
    setTimeout(function() {
        document.body.appendChild(container);
    }, 2000);
    
})();
