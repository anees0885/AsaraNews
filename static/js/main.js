/* ═══════════════════════════════════
   Main Public JS – Gaav Asara News
   ═══════════════════════════════════ */

// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const mainNav = document.getElementById('mainNav');
    if (mobileBtn && mainNav) {
        mobileBtn.addEventListener('click', () => {
            mainNav.classList.toggle('show');
        });
        // Close on overlay click (outside sidebar)
        mainNav.addEventListener('click', (e) => {
            if (e.target === mainNav) {
                mainNav.classList.remove('show');
            }
        });
        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') mainNav.classList.remove('show');
        });
    }

    // Search suggestions
    const searchInput = document.getElementById('searchInput');
    const suggestionsBox = document.getElementById('searchSuggestions');
    let debounceTimer;

    if (searchInput && suggestionsBox) {
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            const q = this.value.trim();
            if (q.length < 2) {
                suggestionsBox.classList.remove('show');
                return;
            }
            debounceTimer = setTimeout(() => {
                fetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.suggestions && data.suggestions.length > 0) {
                            suggestionsBox.innerHTML = data.suggestions.map(s =>
                                `<a href="/news/${s.slug}" class="suggestion-item">${s.title}</a>`
                            ).join('');
                            suggestionsBox.classList.add('show');
                        } else {
                            suggestionsBox.classList.remove('show');
                        }
                    }).catch(() => suggestionsBox.classList.remove('show'));
            }, 300);
        });

        // Hide suggestions on click outside
        document.addEventListener('click', function(e) {
            if (!e.target.closest('#headerSearch')) {
                suggestionsBox.classList.remove('show');
            }
        });
    }

    // Auto-dismiss flash messages after 5 seconds
    document.querySelectorAll('.flash-msg').forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = '0';
            msg.style.transform = 'translateY(-10px)';
            setTimeout(() => msg.remove(), 300);
        }, 5000);
    });

    // Close dropdowns on click outside
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.action-dropdown')) {
            document.querySelectorAll('.dropdown-menu.show').forEach(m => m.classList.remove('show'));
        }
    });
});

// Poll voting
function votePoll(pollId, optionIndex) {
    const formData = new FormData();
    formData.append('option', optionIndex);

    fetch(`/news/poll/${pollId}/vote`, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
            return;
        }
        // Show results
        const widget = document.querySelector(`[data-poll-id="${pollId}"]`);
        if (!widget) return;

        const optionsDiv = widget.querySelector('.poll-options');
        const resultsDiv = widget.querySelector('.poll-results') || 
                          document.getElementById(`pollResults${pollId}`);

        if (optionsDiv) optionsDiv.style.display = 'none';
        if (resultsDiv) {
            resultsDiv.innerHTML = data.results.map(r =>
                `<div class="poll-result-bar">
                    <div class="poll-result-label"><span>${r.option}</span><span>${r.percentage}% (${r.count})</span></div>
                    <div class="poll-result-track"><div class="poll-result-fill" style="width:${r.percentage}%"></div></div>
                </div>`
            ).join('');
            resultsDiv.style.display = 'block';
        }

        const totalEl = document.getElementById(`pollTotal${pollId}`);
        if (totalEl) totalEl.textContent = data.total;
    })
    .catch(err => alert('Error voting. Please try again.'));
}

// Create button dropdown
const createBtn = document.getElementById('createBtn');
const createDropdown = document.getElementById('createDropdown');
if (createBtn && createDropdown) {
    createBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        createBtn.classList.toggle('active');
        createDropdown.classList.toggle('show');
    });
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.create-btn-wrap')) {
            createBtn.classList.remove('active');
            createDropdown.classList.remove('show');
        }
    });
}
