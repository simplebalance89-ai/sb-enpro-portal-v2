/**
 * Enpro Filtration Mastermind - UI v3.0
 * Addresses Andrew's review: Kill commands, natural input, mobile-first, 3 products max
 * 
 * Changes from v2:
 * - NO command suggestions
 * - NO "400 products found"
 * - Max 3 product cards with reasoning
 * - Voice-first mobile layout
 * - Context pills showing memory
 * - Pregame as briefing script
 */

(function () {
    'use strict';

    // ═══════════════════════════════════════════════════════════════════════════════
    // CONFIG
    // ═══════════════════════════════════════════════════════════════════════════════
    const API_BASE = window.ENPRO_API_BASE || '';
    const SESSION_KEY = 'enpro_v3_session';
    
    // ═══════════════════════════════════════════════════════════════════════════════
    // STATE
    // ═══════════════════════════════════════════════════════════════════════════════
    let sessionId = localStorage.getItem(SESSION_KEY);
    if (!sessionId) {
        sessionId = 'sess_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem(SESSION_KEY, sessionId);
    }
    
    let currentContext = {
        industry: null,
        customer: null,
        lastTopic: null,
        recentParts: []
    };
    
    let isRecording = false;
    let mediaRecorder = null;

    // ═══════════════════════════════════════════════════════════════════════════════
    // DOM ELEMENTS
    // ═══════════════════════════════════════════════════════════════════════════════
    const chatHistory = document.getElementById('chatHistory');
    const contextBar = document.getElementById('contextBar');
    const textInput = document.getElementById('textInput');
    const sendBtn = document.getElementById('sendBtn');
    const micBtn = document.getElementById('micBtn');
    const typingIndicator = document.getElementById('typingIndicator');

    // ═══════════════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════════════
    function init() {
        // Welcome message (conversational, no commands)
        appendMessage({
            type: 'assistant',
            content: "Hey! I'm your filtration assistant. Ask me about parts, applications, or prepping for a customer meeting. What are you working on?",
            showContext: false
        });
        
        // Event listeners
        sendBtn.addEventListener('click', handleSend);
        textInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });
        
        // Voice button (hold to speak)
        micBtn.addEventListener('mousedown', startRecording);
        micBtn.addEventListener('mouseup', stopRecording);
        micBtn.addEventListener('mouseleave', stopRecording);
        
        // Touch events for mobile
        micBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
        micBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); });
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // MESSAGE HANDLING (Natural Input - No Commands)
    // ═══════════════════════════════════════════════════════════════════════════════
    async function handleSend() {
        const text = textInput.value.trim();
        if (!text) return;
        
        // Clear input
        textInput.value = '';
        
        // Show user message
        appendMessage({
            type: 'user',
            content: text
        });
        
        // Send to backend (NO intent, NO commands - just raw text)
        await sendToBackend(text);
    }

    async function sendToBackend(message) {
        showTyping(true);
        
        try {
            const response = await fetch(`${API_BASE}/api/v3/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,  // Just the text - backend figures it out
                    session_id: sessionId
                })
            });
            
            if (!response.ok) throw new Error('Network response was not ok');
            
            const data = await response.json();
            
            // Render based on response type
            if (data.response_type === 'briefing') {
                renderBriefingScript(data);
            } else if (data.picks && data.picks.length > 0) {
                renderRecommendations(data);
            } else {
                renderMessage(data);
            }
            
            // Update context
            if (data.context_update) {
                updateContext(data.context_update);
            }
            
            // Speak response if voice mode
            if (isRecording) {
                speakResponse(data.response || data.headline);
            }
            
        } catch (error) {
            console.error('Error:', error);
            appendMessage({
                type: 'assistant',
                content: "Hmm, having trouble connecting. Can you try again?",
                isError: true
            });
        } finally {
            showTyping(false);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // RENDER: Recommendations (Max 3, No Counts)
    // ═══════════════════════════════════════════════════════════════════════════════
    function renderRecommendations(data) {
        const container = document.createElement('div');
        container.className = 'recommendation-container';
        
        // Headline (Andrew: Lead with the verdict)
        if (data.headline) {
            const headline = document.createElement('div');
            headline.className = 'recommendation-headline';
            headline.textContent = data.headline;
            container.appendChild(headline);
        }
        
        // Product cards (max 3, with reasoning - NOT raw data)
        const cardsContainer = document.createElement('div');
        cardsContainer.className = 'product-cards';
        
        (data.picks || []).slice(0, 3).forEach((pick, index) => {
            const card = document.createElement('div');
            card.className = 'product-card-v3';
            card.style.borderLeftColor = getRankColor(index);
            
            card.innerHTML = `
                <div class="card-rank">${index + 1}</div>
                <div class="card-content">
                    <div class="part-number">${pick.part_number}</div>
                    <div class="part-reason">${pick.reason}</div>
                    <div class="part-specs">${pick.specs || ''}</div>
                </div>
                <button class="card-action" onclick="addToQuote('${pick.part_number}')">
                    Add to Quote
                </button>
            `;
            
            cardsContainer.appendChild(card);
        });
        
        container.appendChild(cardsContainer);
        
        // ONE follow-up question button (NOT a list of options)
        const followUp = data.follow_up_question || data.follow_up;
        if (followUp) {
            const followUpBtn = document.createElement('button');
            followUpBtn.className = 'follow-up-btn';
            followUpBtn.textContent = followUp;
            followUpBtn.onclick = () => {
                textInput.value = followUp;
                handleSend();
            };
            container.appendChild(followUpBtn);
        }
        
        chatHistory.appendChild(container);
        scrollToBottom();
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // RENDER: Briefing Script (Pregame as Sales Script)
    // ═══════════════════════════════════════════════════════════════════════════════
    function renderBriefingScript(data) {
        const container = document.createElement('div');
        container.className = 'briefing-container';
        
        container.innerHTML = `
            <div class="briefing-header">
                <span class="briefing-icon">📋</span>
                Meeting Brief: ${data.customer_name || 'Customer'}
            </div>
            
            ${data.opening_line ? `
                <div class="briefing-section">
                    <div class="section-label">Opening Line</div>
                    <div class="script-box">
                        "${data.opening_line}"
                    </div>
                    <button class="speak-btn" onclick="speakText('${escapeHtml(data.opening_line)}')">
                        🔊 Read Aloud
                    </button>
                </div>
            ` : ''}
            
            ${data.picks && data.picks.length > 0 ? `
                <div class="briefing-section">
                    <div class="section-label">Recommendations</div>
                    ${data.picks.map(pick => `
                        <div class="briefing-pick">
                            <strong>${pick.part_number}</strong>
                            <p>${pick.reasoning}</p>
                        </div>
                    `).join('')}
                </div>
            ` : ''}
            
            ${data.follow_up_question ? `
                <div class="briefing-section highlight">
                    <div class="section-label">Ask This</div>
                    <div class="question-box">
                        "${data.follow_up_question}"
                    </div>
                </div>
            ` : ''}
            
            ${data.avoid_topic ? `
                <div class="briefing-section warning">
                    <div class="section-label">⚠️ Avoid</div>
                    <p>${data.avoid_topic}</p>
                </div>
            ` : ''}
        `;
        
        chatHistory.appendChild(container);
        scrollToBottom();
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // RENDER: Simple Message
    // ═══════════════════════════════════════════════════════════════════════════════
    function renderMessage(data) {
        appendMessage({
            type: 'assistant',
            content: data.response || data.to_user || 'Got it.',
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // CONTEXT PILLS (Memory Visualization)
    // ═══════════════════════════════════════════════════════════════════════════════
    function updateContext(contextUpdate) {
        // Merge new context
        if (contextUpdate.industry) currentContext.industry = contextUpdate.industry;
        if (contextUpdate.customer) currentContext.customer = contextUpdate.customer;
        if (contextUpdate.topic) currentContext.lastTopic = contextUpdate.topic;
        if (contextUpdate.part_number) {
            currentContext.recentParts.unshift(contextUpdate.part_number);
            currentContext.recentParts = currentContext.recentParts.slice(0, 3);
        }
        
        // Render pills
        renderContextPills();
    }

    function renderContextPills() {
        const pills = [];
        
        if (currentContext.industry) {
            pills.push({ icon: '🏭', text: currentContext.industry });
        }
        if (currentContext.customer) {
            pills.push({ icon: '👤', text: currentContext.customer });
        }
        if (currentContext.lastTopic) {
            pills.push({ icon: '💬', text: currentContext.lastTopic });
        }
        if (currentContext.recentParts.length > 0) {
            pills.push({ icon: '🔧', text: currentContext.recentParts[0] });
        }
        
        if (pills.length === 0) {
            contextBar.innerHTML = '<span class="context-placeholder">New conversation</span>';
            return;
        }
        
        contextBar.innerHTML = pills.map(p => 
            `<span class="context-pill">${p.icon} ${p.text}</span>`
        ).join('');
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // VOICE HANDLING (Hold to Speak)
    // ═══════════════════════════════════════════════════════════════════════════════
    async function startRecording() {
        if (isRecording) return;
        
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            
            const chunks = [];
            mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
            
            mediaRecorder.onstop = async () => {
                const blob = new Blob(chunks, { type: 'audio/webm' });
                await sendVoiceMessage(blob);
            };
            
            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add('recording');
            micBtn.innerHTML = '<span>🔴 Recording...</span>';
            
        } catch (err) {
            console.error('Mic access error:', err);
            alert('Please allow microphone access for voice input');
        }
    }

    function stopRecording() {
        if (!isRecording || !mediaRecorder) return;
        
        mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('recording');
        micBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
            </svg>
            <span>Hold to speak</span>
        `;
    }

    async function sendVoiceMessage(audioBlob) {
        showTyping(true);
        
        const formData = new FormData();
        formData.append('audio', audioBlob);
        formData.append('session_id', sessionId);
        
        try {
            const response = await fetch(`${API_BASE}/api/voice-search`, {
                method: 'POST',
                body: formData
            });
            if (!response.ok) throw new Error('Network response was not ok');

            const data = await response.json();
            
            // Show what was heard
            appendMessage({
                type: 'user',
                content: data.transcript || data.heard || '(voice input)',
                isVoice: true
            });
            
            // Show response
            if (data.picks && data.picks.length > 0) {
                renderRecommendations(data);
            } else {
                appendMessage({
                    type: 'assistant',
                    content: data.response || data.to_user || "Couldn't process that voice request."
                });
            }
            
        } catch (error) {
            console.error('Voice error:', error);
            appendMessage({
                type: 'assistant',
                content: "Couldn't understand that. Can you try again?",
                isError: true
            });
        } finally {
            showTyping(false);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════════
    // TEXT TO SPEECH
    // ═══════════════════════════════════════════════════════════════════════════════
    function speakResponse(text) {
        if (!window.speechSynthesis) return;
        
        // Cancel any ongoing speech
        window.speechSynthesis.cancel();
        
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.1;
        utterance.pitch = 1;
        
        window.speechSynthesis.speak(utterance);
    }

    // Make available globally
    window.speakText = speakResponse;

    // ═══════════════════════════════════════════════════════════════════════════════
    // UTILITIES
    // ═══════════════════════════════════════════════════════════════════════════════
    function appendMessage({ type, content, isError, isVoice, showContext = true }) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message message-${type}${isError ? ' message-error' : ''}${isVoice ? ' message-voice' : ''}`;
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.textContent = content;
        
        msgDiv.appendChild(bubble);
        chatHistory.appendChild(msgDiv);
        
        if (showContext) {
            scrollToBottom();
        }
    }

    function showTyping(show) {
        typingIndicator.style.display = show ? 'flex' : 'none';
    }

    function scrollToBottom() {
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }

    function getRankColor(index) {
        const colors = ['#0078d4', '#106ebe', '#005a9e'];
        return colors[index] || '#0078d4';
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Quote functionality (placeholder)
    window.addToQuote = function(partNumber) {
        // Implement quote adding
        console.log('Adding to quote:', partNumber);
        
        // Visual feedback
        const btn = event.target;
        btn.textContent = '✓ Added';
        btn.disabled = true;
        setTimeout(() => {
            btn.textContent = 'Add to Quote';
            btn.disabled = false;
        }, 2000);
    };

    // Initialize
    init();
})();
