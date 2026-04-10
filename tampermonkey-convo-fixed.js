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
            name: 'Brewery',
            step1: 'brewery customer meeting tomorrow',
            step2: 'purity per batch and yield',
            step3: 'they are using depth sheets',
            step4: 'what about final filtration'
        },
        {
            name: 'Paint Booth',
            step1: 'paint spray booth customer meeting',
            step2: 'overspray buildup',
            step3: 'compare the two options',
            step4: 'what is the price difference'
        },
        {
            name: 'Pharma',
            step1: 'pharmaceutical sterile filtration meeting',
            step2: 'endotoxin removal',
            step3: 'what membranes do you recommend',
            step4: 'compare PES vs PTFE'
        },
        {
            name: 'Hydraulic',
            step1: 'hydraulic oil filtration customer',
            step2: '10 micron particles damaging pumps',
            step3: 'Pall or competitor',
            step4: 'what is the beta rating'
        },
        {
            name: 'Water',
            step1: 'municipal water treatment meeting',
            step2: 'NSF 61 certification required',
            step3: 'what is the flow rate',
            step4: 'compare Ultipleat vs Marksman'
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
    
    scenarios.forEach(function(scenario) {
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
            
            setTimeout(function() {
                var input = document.getElementById('userInput');
                if (input) {
                    input.value = scenario.step1;
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
                }
                btn.innerHTML = 'T1/4';
            }, 100);
            
            setTimeout(function() {
                var input = document.getElementById('userInput');
                if (input) {
                    input.value = scenario.step2;
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
                }
                btn.innerHTML = 'T2/4';
            }, 8000);
            
            setTimeout(function() {
                var input = document.getElementById('userInput');
                if (input) {
                    input.value = scenario.step3;
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
                }
                btn.innerHTML = 'T3/4';
            }, 16000);
            
            setTimeout(function() {
                var input = document.getElementById('userInput');
                if (input) {
                    input.value = scenario.step4;
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
                }
                btn.innerHTML = 'T4/4';
            }, 24000);
            
            setTimeout(function() {
                btn.innerHTML = scenario.name;
                btn.disabled = false;
                btn.style.background = '#0066CC';
            }, 32000);
        };
        
        container.appendChild(btn);
    });
    
    setTimeout(function() {
        document.body.appendChild(container);
    }, 2000);
    
})();
