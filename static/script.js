document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('url-input');
    const analyzeBtn = document.getElementById('analyze-btn');
    const loadingEl = document.getElementById('loading');
    const errorEl = document.getElementById('error-message');
    const resultsSection = document.getElementById('results');

    analyzeBtn.addEventListener('click', handleAnalyze);
    urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleAnalyze();
    });

    async function handleAnalyze() {
        const url = urlInput.value.trim();
        if (!url) return;

        // Reset UI
        errorEl.classList.add('hidden');
        resultsSection.classList.add('hidden');
        loadingEl.classList.remove('hidden');
        analyzeBtn.disabled = true;

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || '分析時發生錯誤');
            }

            renderResults(result.data);
            resultsSection.classList.remove('hidden');

        } catch (err) {
            errorEl.textContent = err.message;
            errorEl.classList.remove('hidden');
        } finally {
            loadingEl.classList.add('hidden');
            analyzeBtn.disabled = false;
        }
    }

    function renderResults(data) {
        const { place_info, metrics, highlights, rating_distribution, explanations, advice, trend_data } = data;

        let html = `
            <div class="card">
                <h2>🏬 ${place_info.title || '地標資訊'}</h2>
                <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">${place_info.address || ''}</p>
                
                <div class="metrics-grid">
                    <div class="metric-box" style="opacity: 0.8;">
                        <div class="metric-value" style="color: var(--text-secondary);">${metrics.google_original_rating || '-'}</div>
                        <div class="metric-label">Google 原始星等</div>
                    </div>
                    <div class="metric-box" style="border: 1px solid rgba(59, 130, 246, 0.5); background: rgba(59, 130, 246, 0.1);">
                        <div class="metric-value" style="color: var(--accent);">${metrics.real_avg.toFixed(1)}</div>
                        <div class="metric-label">真實星等</div>
                    </div>
                    <div class="metric-box">
                        <div class="metric-value">${metrics.evaluated_reviews_count}</div>
                        <div class="metric-label">過濾後評論數</div>
                    </div>
                </div>

                <div class="explanation-box">
                    ${explanations.map(text => `<p class="explanation-text">${text}</p>`).join('')}
                </div>
            </div>

            <div class="card">
                <h2>📊 真實星等分佈</h2>
                <div class="distribution-chart">
        `;

        // Star distribution
        let maxCount = 0;
        if (rating_distribution) {
            maxCount = Math.max(...Object.values(rating_distribution));
        }

        ['5', '4', '3', '2', '1'].forEach(star => {
            const count = rating_distribution ? (rating_distribution[star] || 0) : 0;
            const percentage = maxCount === 0 ? 0 : (count / maxCount) * 100;

            html += `
                <div class="stars-bar">
                    <div class="stars-label"><span class="star-num">${star}</span> <span class="star-icon">★</span></div>
                    <div class="stars-track">
                        <div class="stars-fill" style="width: 0%" data-width="${percentage}%"></div>
                    </div>
                    <div class="stars-count">${count}</div>
                </div>
            `;
        });

        html += `
                </div>
            </div>

            <div class="card" id="trend-card">
                <h2>📈 有效評論趨勢 (月)</h2>
                <div style="position: relative; height: 300px; width: 100%;">
                    <canvas id="trend-chart"></canvas>
                </div>
            </div>
            
            <div class="card">
                <h2>✨ 正負評價特徵提取</h2>
        `;

        if (highlights.has_pos) {
            html += `
                <div class="highlight-box">
                    <div class="highlight-title">✅ 最大亮點：${highlights.top_pos_cat}</div>
                    <p class="explanation-text">消費者最常提到的好評字眼：</p>
                    <div class="tags">
                        ${highlights.top_pos_keywords.map(kw => `<span class="tag">${kw}</span>`).join('')}
                    </div>
                </div>
            `;
        } else {
            html += `<p class="explanation-text">✅ 最大亮點：真實評論中並無特別突出的好評項目。</p>`;
        }

        if (highlights.has_neg) {
            html += `
                <div class="highlight-box negative">
                    <div class="highlight-title">⚠️ 最大隱憂：${highlights.top_neg_cat}</div>
                    <p class="explanation-text">遭到抱怨最多次的災情字眼：</p>
                    <div class="tags">
                        ${highlights.top_neg_keywords.map(kw => `<span class="tag">${kw}</span>`).join('')}
                    </div>
                </div>
            `;
        } else {
            html += `<p class="explanation-text" style="margin-top: 1rem;">⚠️ 最大隱憂：目前的真實消費者中，並未反應出任何嚴重的客訴雷區。</p>`;
        }

        html += `
            </div>

            <div class="card">
                <h2>💡 情境導向行動建議</h2>
                <ul class="advice-list">
                    ${advice.map(text => `<li>${text.replace('▶ ', '')}</li>`).join('')}
                </ul>
            </div>
        `;

        resultsSection.innerHTML = html;

        // Animate the bars
        setTimeout(() => {
            document.querySelectorAll('.stars-fill').forEach(bar => {
                bar.style.width = bar.getAttribute('data-width');
            });
        }, 100);

        // Render trend chart if data is available
        if (trend_data && trend_data.length > 0) {
            const ctx = document.getElementById('trend-chart').getContext('2d');

            Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
            Chart.defaults.font.family = "'Inter', 'Noto Sans TC', sans-serif";

            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: trend_data.map(d => d.month),
                    datasets: [
                        {
                            type: 'line',
                            label: '平均星等',
                            data: trend_data.map(d => d.avg_rating),
                            borderColor: '#8b5cf6',
                            backgroundColor: '#8b5cf6',
                            borderWidth: 2,
                            tension: 0.3,
                            yAxisID: 'y',
                            pointBackgroundColor: '#1e293b',
                            pointBorderColor: '#8b5cf6',
                            pointBorderWidth: 2,
                            pointRadius: 4
                        },
                        {
                            type: 'bar',
                            label: '評論數量',
                            data: trend_data.map(d => d.review_count),
                            backgroundColor: 'rgba(59, 130, 246, 0.2)',
                            borderColor: 'rgba(59, 130, 246, 0.5)',
                            borderWidth: 1,
                            borderRadius: 4,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        y: {
                            type: 'linear', display: true, position: 'left', min: 1, max: 5,
                            title: { display: true, text: '平均星等 (★)' },
                            grid: { color: 'rgba(255, 255, 255, 0.1)' }
                        },
                        y1: {
                            type: 'linear', display: true, position: 'right',
                            title: { display: true, text: '評論數量 (則)' },
                            grid: { drawOnChartArea: false }
                        },
                        x: { grid: { display: false } }
                    },
                    plugins: { legend: { position: 'top' } }
                }
            });
        }
    }


});
