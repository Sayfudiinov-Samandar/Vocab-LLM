const API_BASE = '/api';
let autoplayEnabled = false;
let allWords = [];

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function parseJsonList(value) {
    try {
        const parsed = JSON.parse(value || '[]');
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

async function readApiResponse(res) {
    const text = await res.text();
    try {
        return text ? JSON.parse(text) : {};
    } catch {
        return {
            detail: res.ok ? text : 'Server returned an unexpected error. Check the backend terminal for details.'
        };
    }
}

function toggleMenu() {
    document.getElementById('navLinks')?.classList.toggle('open');
}

function getTagsFromInput() {
    return (document.getElementById('tagInput')?.value || '')
        .split(',')
        .map(tag => tag.trim())
        .filter(Boolean);
}

function speak(text) {
    if (!('speechSynthesis' in window)) {
        alert('Audio is not supported in this browser.');
        return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 0.92;
    window.speechSynthesis.speak(utterance);
}

function toggleAutoplay() {
    autoplayEnabled = !autoplayEnabled;
    const button = document.getElementById('autoplayBtn');
    if (button) button.textContent = autoplayEnabled ? 'Auto-play On' : 'Auto-play Off';
}

async function loadStats() {
    const statsEl = document.getElementById('stats');
    if (!statsEl) return;

    try {
        const res = await fetch(`${API_BASE}/stats`);
        const stats = await res.json();
        statsEl.innerHTML = `
            <div><strong>${stats.total_words}</strong><span>Words</span></div>
            <div><strong>${stats.due_reviews}</strong><span>Due today</span></div>
            <div><strong>${stats.reviews_today}</strong><span>Reviews</span></div>
            <div><strong>${stats.maturing_words}</strong><span>Maturing</span></div>
        `;
    } catch {
        statsEl.innerHTML = '';
    }
}

async function loadHistoryPreview() {
    const preview = document.getElementById('historyPreview');
    if (!preview) return;

    try {
        const res = await fetch(`${API_BASE}/learning/records?limit=5`);
        const records = await res.json();
        if (!records.length) {
            preview.innerHTML = '<p>No activity yet. Add your first word with the agent.</p>';
            return;
        }
        preview.innerHTML = records.map(record => `
            <div class="history-item">
                <strong>${escapeHtml(record.event_type)}</strong>
                <span>${escapeHtml(record.word_text || '')}</span>
                <span>${escapeHtml(record.created_at || '')}</span>
            </div>
        `).join('');
    } catch {
        preview.innerHTML = '<p>History is unavailable right now.</p>';
    }
}

function filteredWords(words) {
    const filter = document.getElementById('filterSelect')?.value || '';
    if (filter === 'favorite') return words.filter(word => Number(word.favorite) === 1);
    if (filter === 'hard') return words.filter(word => Number(word.difficulty || 2) >= 4);
    if (filter === 'fallback') return words.filter(word => word.source_type === 'ai_fallback');
    return words;
}

function renderLatestWord(words) {
    const latest = document.getElementById('latestWordCard');
    if (!latest) return;

    if (!Array.isArray(words) || !words.length) {
        latest.innerHTML = `
            <div class="empty-latest-card">
                <strong>No words yet</strong>
                <span>Run the agent on the left to create your first vocabulary card.</span>
            </div>
        `;
        return;
    }

    const word = words[0];
    const tags = parseJsonList(word.tags);
    latest.innerHTML = `
        <article class="word-card latest-preview-card" onclick="window.location.href='word.html?id=${word.id}'">
            <div class="card-topline">
                <div>
                    <h3>${escapeHtml(word.word)} <span class="phonetic">${escapeHtml(word.phonetic || '')}</span></h3>
                    <div class="meta-row">
                        <span>${escapeHtml(word.part_of_speech || 'word')}</span>
                        <span>Level ${escapeHtml(word.difficulty || 2)}</span>
                    </div>
                </div>
            </div>
            <p class="meaning">${escapeHtml(word.chinese_meaning || '')}</p>
            <p class="english-definition">${escapeHtml(word.english_definition || '')}</p>
            <p class="example">"${escapeHtml(word.example_sentence || '')}"</p>
            <div class="tag-row">${tags.slice(0, 4).map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}</div>
            <span class="source-link">Open details</span>
        </article>
    `;
}

function renderWords(words) {
    const list = document.getElementById('wordList');
    const visibleWords = filteredWords(words);

    if (!visibleWords.length) {
        list.innerHTML = '<div class="empty-state">No matching words yet. Try another filter or run the agent.</div>';
        return;
    }

    list.innerHTML = visibleWords.map(word => {
        const tags = parseJsonList(word.tags);
        const audioText = encodeURIComponent(`${word.word}. ${word.example_sentence}`);
        const source = word.source_url
            ? `<a href="${escapeHtml(word.source_url)}" target="_blank" class="source-link" onclick="event.stopPropagation()">Source: ${escapeHtml(word.source_name || 'Source')}</a>`
            : `<span class="source-warning">AI fallback example</span>`;
        return `
            <article class="word-card" onclick="window.location.href='word.html?id=${word.id}'">
                <div class="card-topline">
                    <div>
                        <h3>${escapeHtml(word.word)} <span class="phonetic">${escapeHtml(word.phonetic || '')}</span></h3>
                        <div class="meta-row">
                            <span>${escapeHtml(word.part_of_speech || 'word')}</span>
                            <span>Level ${escapeHtml(word.difficulty || 2)}</span>
                            ${Number(word.favorite) === 1 ? '<span>Favorite</span>' : ''}
                        </div>
                    </div>
                    <button class="small-button" title="Play pronunciation and example" onclick="event.stopPropagation(); speak(decodeURIComponent('${audioText}'))">Audio</button>
                </div>
                <p class="meaning">${escapeHtml(word.chinese_meaning || '')}</p>
                <p class="english-definition">${escapeHtml(word.english_definition || '')}</p>
                <p class="example">"${escapeHtml(word.example_sentence)}"</p>
                <p class="translation">${escapeHtml(word.chinese_translation || '')}</p>
                <div class="tag-row">${tags.map(tag => `<span>${escapeHtml(tag)}</span>`).join('')}</div>
                <div class="card-footer">${source}</div>
            </article>
        `;
    }).join('');

    if (autoplayEnabled && visibleWords[0]) {
        speak(`${visibleWords[0].word}. ${visibleWords[0].example_sentence}`);
    }
}

async function loadWords() {
    const list = document.getElementById('wordList');
    const search = document.getElementById('searchInput')?.value.trim() || '';
    const query = search ? `?q=${encodeURIComponent(search)}` : '';
    list.innerHTML = '<div class="agent-loading"><span></span>Loading vocabulary...</div>';

    try {
        const res = await fetch(`${API_BASE}/words${query}`);
        allWords = await readApiResponse(res);
        await loadStats();
        renderLatestWord(Array.isArray(allWords) ? allWords : []);
        renderWords(Array.isArray(allWords) ? allWords : []);
    } catch {
        list.innerHTML = '<div class="empty-state">Error loading words. Is the server running?</div>';
    }
}

async function addWord() {
    const input = document.getElementById('wordInput');
    const tagInput = document.getElementById('tagInput');
    const word = input.value.trim();
    if (!word) return;

    const loading = document.getElementById('loading');
    loading.classList.remove('hidden');
    input.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/agent/example-search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ word, user_id: 1, tags: getTagsFromInput() })
        });
        const result = await readApiResponse(res);
        if (!res.ok) throw new Error(result.detail || 'Error adding word.');
        input.value = '';
        if (tagInput) tagInput.value = '';
        await loadWords();
        await loadHistoryPreview();
    } catch (error) {
        alert(error.message || 'Error adding word. Check API keys and try again.');
    } finally {
        loading.classList.add('hidden');
        input.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('wordInput');
    const search = document.getElementById('searchInput');
    if (input) {
        input.addEventListener('keypress', event => {
            if (event.key === 'Enter') addWord();
        });
    }
    if (search) {
        search.addEventListener('input', () => loadWords());
    }
    loadWords();
    loadHistoryPreview();
});
