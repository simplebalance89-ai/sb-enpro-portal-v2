// ==UserScript==
// @name         EnPro Test Scenarios v2
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  5 test scenarios for conversation flow
// @match        https://enpro-fm-portal.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    var scenarios = [
        {
            name: 'Brewery - Purity/Yield',
            steps: [
                'brewery customer meeting tomorrow',
                'purity per batch and yield',
                'they are using depth sheets',
                'what about final filtration'
            ]
        },
        {
            name: 'Paint Booth - Overspray',
            steps: [
                'paint spray booth customer meeting',
                'overspray buildup',
                'compare the two options',
                'what is the price difference'
            ]
        },
        {
            name: 'Pharma - Endotoxin',
            steps: [
                'pharmaceutical sterile filtration meeting',
                'endotoxin removal',
                'what membranes do you recommend',
                'compare PES vs PTFE'
            ]
        },
        {
            name: 'Hydraulic - 10 Micron',
            steps: [
                'hydraulic oil filtration customer',
                '10 micron particles damaging pumps',
                'Pall or competitor',
                'what is the beta rating'
            ]
        },
        {
            name: 'Water - NSF 61',
            steps: [
                'municipal water treatment meeting',
                'NSF 61 certification required',
                'what is the flow rate',
                'compare Ultipleat vs Marksman'
            ]
        }
    ];
    
    var container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.top = '80px';
    container.style.right = '20px';
    container.style.zIndex = '9999';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '8px';
    
    var label = document.createElement('div');
    label.innerHTML = 'Test Scenarios';
    label.style.background = '#003366';
    label.style.color = 'white';
    label.style.padding = '8px 12px';
    label.style.borderRadius = '6px';
    label.style.fontSize = '12px';
    label.style.fontWeight = 'bold';
    label.style.textAlign = 'center';
    container.appendChild(label);
    
    scenarios.forEach(function(scenario, idx) {
        var btn = document.createElement('button');
        btn.innerHTML = scenario.name;
        btn.style.padding = '10px 16px';
        btn.style.background = '#0066CC';
        btn.style.color = 'white';
        btn.style.border = 'none';
        btn.style.borderRadius = '6px';
        btn.style.cursor = 'pointer';
        btn.style.fontSize = '11px';
        
        btn.onclick = function() {
            btn.disabled = true;
            btn.innerHTML = 'Running...';
            btn.style.background = '#999';
            
            var delay = 100;
            scenario.steps.forEach(function(step, stepIdx) {
                setTimeout(function() {
                    var input = document.getElementById('userInput');
                    if (input) {
                        input.value = step;
                        input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
                    }
                    btn.innerHTML = 'T' + (stepIdx + 1) + '/' + scenario.steps.length;
                }, delay);
                delay = delay + 8000;
            });
            
            setTimeout(function() {
                btn.innerHTML = scenario.name;
                btn.disabled = false;
                btn.style.background = '#0066CC';
            }, delay + 2000);
        };
        
        container.appendChild(btn);
    });
    
    setTimeout(function() {
        document.body.appendChild(container);
    }, 2000);
    
})();
