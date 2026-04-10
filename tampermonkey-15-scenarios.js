// ==UserScript==
// @name         EnPro 15 Scenarios
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  15 test scenarios - 5 lookups, 5 pregames, 5 compares
// @match        https://enpro-fm-portal-v215-staging.onrender.com/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    // 5 Part number lookups
    var lookups = [
        'CLR10295',
        'HC9020FCN4Z', 
        '12247',
        'CLR130',
        '12941'
    ];
    
    // 5 Customer pregames
    var pregames = [
        'I have a meeting tomorrow for a brewery customer',
        'customer meeting data center HVAC operator next week',
        'pregame for pharmaceutical filtration customer call',
        'meeting with wastewater treatment plant manager',
        'customer call food processing filtration needs'
    ];
    
    // 5 Compare pairs
    var compares = [
        'compare HC9020FCN4Z vs HC9021FAS4Z',
        'compare CLR130 vs CLR140',
        'compare 12247 vs 12941',
        'compare HC9020 vs CLR130',
        'compare 12247 vs HC9021FAS4Z'
    ];
    
    var current = 0;
    var allScenarios = [];
    
    // Build scenario list: lookup 1, pregame 1, compare 1, lookup 2, pregame 2...
    for (var i = 0; i < 5; i++) {
        allScenarios.push({type: 'LOOKUP', text: lookups[i]});
        allScenarios.push({type: 'PREGAME', text: pregames[i]});
        allScenarios.push({type: 'COMPARE', text: compares[i]});
    }
    
    function runScenario(index) {
        if (index >= allScenarios.length) {
            console.log('✅ ALL 15 SCENARIOS COMPLETE');
            btn.innerHTML = '🔄 Run Again';
            btn.disabled = false;
            return;
        }
        
        var scenario = allScenarios[index];
        current = index + 1;
        
        console.log('Step ' + current + '/15: ' + scenario.type + ' - ' + scenario.text);
        btn.innerHTML = current + '/15: ' + scenario.type;
        
        document.getElementById('userInput').value = scenario.text;
        document.getElementById('userInput').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter'}));
        
        // Wait 7 seconds between scenarios
        setTimeout(function() {
            runScenario(index + 1);
        }, 7000);
    }
    
    // Create button
    var btn = document.createElement('button');
    btn.innerHTML = '▶️ Run 15 Scenarios';
    btn.style.cssText = 'position:fixed;top:80px;right:20px;z-index:9999;padding:15px 25px;background:#003366;color:white;border:none;border-radius:8px;cursor:pointer;font-weight:bold;font-size:14px;';
    
    btn.onclick = function() {
        btn.disabled = true;
        console.log('🎬 STARTING 15 SCENARIOS');
        runScenario(0);
    };
    
    setTimeout(function() {
        document.body.appendChild(btn);
        console.log('15 Scenarios ready - click button to run');
    }, 2000);
    
})();
