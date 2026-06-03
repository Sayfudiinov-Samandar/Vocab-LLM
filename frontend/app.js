const API_BASE = '/api';

async function loadWords() {
    const list = document.getElementById('wordList');
    list.innerHTML = '<div class="loading">Loading your vocabulary...</div>';
    
    try {
        const res = await fetch(`${API_BASE}/words`);
        const words = await res.json();
        
        if (words.length === 0) {
            list.innerHTML = '<div class="loading">Your vocabulary is empty. Add your first word above!</div>';
            return;
        }
        
        list.innerHTML = words.map(word => `
            <div class="word-card" onclick="window.location.href='word.html?id=${word.id}'">
                <h2>${word.word} <span class="phonetic">${word.phonetic || ''}</span></h2>
                <div class="pos">${word.part_of_speech || ''}</div>
                <div class="meaning">${word.chinese_meaning || ''}</div>
                <div class="example">"${word.example_sentence}"</div>
                <div class="translation">${word.chinese_translation || ''}</div>
                <a href="${word.source_url}" target="_blank" class="source-link" onclick="event.stopPropagation()">
                    📰 ${word.source_name || 'Source'} ↗
                </a>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = '<div class="loading">Error loading words. Is the server running?</div>';
    }
}

async function addWord() {
    const input = document.getElementById('wordInput');
    const word = input.value.trim();
    if (!word) return;
    
    const loading = document.getElementById('loading');
    loading.classList.remove('hidden');
    input.disabled = true;
    
    try {
        const res = await fetch(`${API_BASE}/words`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ word: word, user_id: 1 })
        });
        
        const result = await res.json();
        
        if (result.status === 'exists') {
            alert(`'${word}' already exists in your vocabulary!`);
        } else {
            input.value = '';
            loadWords();
        }
    } catch (e) {
        alert('Error adding word. Check your API keys and try again.');
    } finally {
        loading.classList.add('hidden');
        input.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('wordInput');
    if (input) {
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') addWord();
        });
    }
    loadWords();
});