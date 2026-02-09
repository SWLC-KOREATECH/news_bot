// ============== 전역 변수 ==============
let config = {
    keywords: [],
    receivers: [],
    settings: {
        similarity_threshold: 0.5,
        max_articles_per_keyword: 100
    }
};

let githubConfig = {
    owner: '',
    repo: '',
    token: ''
};

// 색상 팔레트
const COLOR_PALETTE = [
    '#3498db', '#e67e22', '#2ecc71', '#9b59b6', '#e74c3c', '#1abc9c',
    '#f39c12', '#34495e', '#16a085', '#d35400', '#8e44ad', '#c0392b',
    '#27ae60', '#2980b9', '#f1c40f', '#7f8c8d', '#2c3e50', '#95a5a6'
];

let selectedColorIndex = null;
let selectedColorValue = '#3498db';

// ============== 초기화 ==============
document.addEventListener('DOMContentLoaded', () => {
    initColorPalette();
    checkExistingSetup();
});

// 기존 설정 확인
function checkExistingSetup() {
    const saved = localStorage.getItem('newsbot_config');

    if (saved) {
        try {
            githubConfig = JSON.parse(saved);
            if (githubConfig.owner && githubConfig.repo && githubConfig.token) {
                // 기존 설정 있음 -> 바로 연결 시도
                connectAndLoadConfig();
                return;
            }
        } catch (e) {
            console.error('설정 파싱 실패:', e);
        }
    }

    // 설정 없음 -> 최초 설정 화면 표시
    showScreen('setup');
}

// 화면 전환
function showScreen(screenName) {
    document.getElementById('loadingScreen').style.display = 'none';
    document.getElementById('setupScreen').style.display = 'none';
    document.getElementById('mainScreen').style.display = 'none';

    if (screenName === 'loading') {
        document.getElementById('loadingScreen').style.display = 'flex';
    } else if (screenName === 'setup') {
        document.getElementById('setupScreen').style.display = 'block';
    } else if (screenName === 'main') {
        document.getElementById('mainScreen').style.display = 'block';
    }
}

// ============== 최초 설정 ==============
async function saveSetupAndConnect() {
    githubConfig.owner = document.getElementById('setupOwner').value.trim();
    githubConfig.repo = document.getElementById('setupRepo').value.trim();
    githubConfig.token = document.getElementById('setupToken').value.trim();

    if (!githubConfig.owner || !githubConfig.repo || !githubConfig.token) {
        alert('모든 항목을 입력해 주세요.');
        return;
    }

    // 로컬 스토리지에 저장
    localStorage.setItem('newsbot_config', JSON.stringify(githubConfig));

    // 연결 시도
    await connectAndLoadConfig();
}

// GitHub 연결 및 config 로드
async function connectAndLoadConfig() {
    showScreen('loading');

    try {
        const response = await fetch(
            `https://api.github.com/repos/${githubConfig.owner}/${githubConfig.repo}/contents/config.json`,
            {
                headers: {
                    'Authorization': `token ${githubConfig.token}`,
                    'Accept': 'application/vnd.github.v3+json'
                }
            }
        );

        if (response.ok) {
            const data = await response.json();
            const content = atob(data.content);
            config = JSON.parse(content);
            config._sha = data.sha;
        } else if (response.status === 404) {
            // config.json 없음 -> 기본값 사용
            config = {
                keywords: [
                    { name: '일학습병행', color: '#3498db', enabled: true },
                    { name: '직업훈련', color: '#e67e22', enabled: true },
                    { name: '고용노동부', color: '#7f8c8d', enabled: true },
                    { name: '한국산업인력공단', color: '#2c3e50', enabled: true }
                ],
                receivers: [],
                settings: { similarity_threshold: 0.5, max_articles_per_keyword: 100 }
            };
        } else if (response.status === 401) {
            throw new Error('토큰이 유효하지 않습니다. 다시 확인해 주세요.');
        } else {
            throw new Error(`GitHub 오류: ${response.status}`);
        }

        // UI 렌더링
        renderAll();
        showScreen('main');
        document.getElementById('userInfo').textContent = `@${githubConfig.owner}`;

    } catch (error) {
        alert(error.message);
        localStorage.removeItem('newsbot_config');
        showScreen('setup');
    }
}

// ============== 렌더링 ==============
function renderAll() {
    renderKeywords();
    renderReceivers();
    renderSettings();
}

function renderKeywords() {
    const container = document.getElementById('keywordsList');

    if (!config.keywords || config.keywords.length === 0) {
        container.innerHTML = '<div class="empty-state">등록된 키워드가 없습니다.</div>';
        return;
    }

    container.innerHTML = config.keywords.map((kw, index) => `
        <div class="keyword-item">
            <div class="keyword-color" style="background-color: ${kw.color}" 
                 onclick="openColorModal(${index})" title="색상 변경"></div>
            <input type="text" class="keyword-name" value="${kw.name}" 
                   onchange="updateKeyword(${index}, 'name', this.value)" 
                   placeholder="키워드 입력">
            <label class="toggle-switch">
                <input type="checkbox" ${kw.enabled ? 'checked' : ''} 
                       onchange="updateKeyword(${index}, 'enabled', this.checked)">
                <span class="toggle-slider"></span>
            </label>
            <button class="btn-delete" onclick="deleteKeyword(${index})">✕</button>
        </div>
    `).join('');
}

function renderReceivers() {
    const container = document.getElementById('receiversList');

    if (!config.receivers || config.receivers.length === 0) {
        container.innerHTML = '<div class="empty-state">추가 수신자가 없습니다.</div>';
        return;
    }

    container.innerHTML = config.receivers.map((recv, index) => `
        <div class="receiver-item">
            <span style="font-size: 1.1rem;">📧</span>
            <input type="email" class="receiver-email" value="${recv.email}" 
                   onchange="updateReceiver(${index}, 'email', this.value)" 
                   placeholder="email@example.com">
            <label class="toggle-switch">
                <input type="checkbox" ${recv.enabled ? 'checked' : ''} 
                       onchange="updateReceiver(${index}, 'enabled', this.checked)">
                <span class="toggle-slider"></span>
            </label>
            <button class="btn-delete" onclick="deleteReceiver(${index})">✕</button>
        </div>
    `).join('');
}

function renderSettings() {
    document.getElementById('similarityThreshold').value = config.settings?.similarity_threshold || 0.4;
    document.getElementById('maxArticles').value = config.settings?.max_articles_per_keyword || 100;
}

// ============== 키워드 관리 ==============
function addKeyword() {
    if (!config.keywords) config.keywords = [];
    config.keywords.push({
        name: '',
        color: COLOR_PALETTE[config.keywords.length % COLOR_PALETTE.length],
        enabled: true
    });
    renderKeywords();

    // 포커스
    setTimeout(() => {
        const inputs = document.querySelectorAll('.keyword-name');
        inputs[inputs.length - 1]?.focus();
    }, 50);
}

function updateKeyword(index, field, value) {
    if (config.keywords[index]) {
        config.keywords[index][field] = value;
    }
}

function deleteKeyword(index) {
    config.keywords.splice(index, 1);
    renderKeywords();
}

// ============== 수신자 관리 ==============
function addReceiver() {
    if (!config.receivers) config.receivers = [];
    config.receivers.push({ email: '', enabled: true });
    renderReceivers();

    setTimeout(() => {
        const inputs = document.querySelectorAll('.receiver-email');
        inputs[inputs.length - 1]?.focus();
    }, 50);
}

function updateReceiver(index, field, value) {
    if (config.receivers[index]) {
        config.receivers[index][field] = value;
    }
}

function deleteReceiver(index) {
    config.receivers.splice(index, 1);
    renderReceivers();
}

// ============== 고급 설정 ==============
function toggleAdvanced() {
    document.getElementById('advancedSection').classList.toggle('collapsed');
}

// ============== 색상 모달 ==============
function initColorPalette() {
    const palette = document.getElementById('colorPalette');
    if (!palette) return;

    palette.innerHTML = COLOR_PALETTE.map(color =>
        `<div class="color-option" style="background-color: ${color}" 
              onclick="selectColor('${color}')" data-color="${color}"></div>`
    ).join('');
}

function openColorModal(keywordIndex) {
    selectedColorIndex = keywordIndex;
    selectedColorValue = config.keywords[keywordIndex]?.color || '#3498db';

    document.querySelectorAll('.color-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.color === selectedColorValue);
    });

    document.getElementById('colorModal').classList.add('active');
}

function closeColorModal() {
    document.getElementById('colorModal').classList.remove('active');
}

function selectColor(color) {
    selectedColorValue = color;
    document.querySelectorAll('.color-option').forEach(el => {
        el.classList.toggle('selected', el.dataset.color === color);
    });
}

function applyColor() {
    if (selectedColorIndex !== null && config.keywords[selectedColorIndex]) {
        config.keywords[selectedColorIndex].color = selectedColorValue;
        renderKeywords();
    }
    closeColorModal();
}

// 모달 외부 클릭
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});

// ============== 설정 모달 ==============
function showSettings() {
    document.getElementById('modalOwner').value = githubConfig.owner;
    document.getElementById('modalRepo').value = githubConfig.repo;
    document.getElementById('modalToken').value = githubConfig.token;
    document.getElementById('settingsModal').classList.add('active');
}

function closeSettings() {
    document.getElementById('settingsModal').classList.remove('active');
}

function updateSettings() {
    githubConfig.owner = document.getElementById('modalOwner').value.trim();
    githubConfig.repo = document.getElementById('modalRepo').value.trim();
    githubConfig.token = document.getElementById('modalToken').value.trim();

    localStorage.setItem('newsbot_config', JSON.stringify(githubConfig));
    document.getElementById('userInfo').textContent = `@${githubConfig.owner}`;
    closeSettings();
    showStatus('설정이 저장되었습니다.', 'success');
}

function resetSettings() {
    if (confirm('설정을 초기화하시겠습니까?\n브라우저에 저장된 토큰이 삭제됩니다.')) {
        localStorage.removeItem('newsbot_config');
        closeSettings();
        showScreen('setup');
    }
}

// ============== 저장 ==============
function getConfigForSave() {
    config.settings = {
        similarity_threshold: parseFloat(document.getElementById('similarityThreshold').value) || 0.4,
        max_articles_per_keyword: parseInt(document.getElementById('maxArticles').value) || 100
    };

    // 빈 항목 필터링
    config.keywords = (config.keywords || []).filter(kw => kw.name?.trim());
    config.receivers = (config.receivers || []).filter(r => r.email?.trim());

    const saveConfig = { ...config };
    delete saveConfig._sha;
    return saveConfig;
}

async function saveToGitHub() {
    const btn = document.getElementById('saveBtn');
    btn.disabled = true;
    showStatus('저장 중...', 'loading');

    try {
        const saveConfig = getConfigForSave();
        const content = btoa(unescape(encodeURIComponent(JSON.stringify(saveConfig, null, 2))));

        const body = {
            message: `Update config - ${new Date().toLocaleString('ko-KR')}`,
            content: content
        };

        if (config._sha) {
            body.sha = config._sha;
        }

        const response = await fetch(
            `https://api.github.com/repos/${githubConfig.owner}/${githubConfig.repo}/contents/config.json`,
            {
                method: 'PUT',
                headers: {
                    'Authorization': `token ${githubConfig.token}`,
                    'Accept': 'application/vnd.github.v3+json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            }
        );

        if (response.ok) {
            const data = await response.json();
            config._sha = data.content.sha;
            showStatus('✅ 저장 완료!', 'success');
        } else {
            const error = await response.json();
            throw new Error(error.message);
        }
    } catch (error) {
        showStatus(`❌ 저장 실패: ${error.message}`, 'error');
    } finally {
        btn.disabled = false;
    }
}

function downloadConfig() {
    const saveConfig = getConfigForSave();
    const blob = new Blob([JSON.stringify(saveConfig, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = 'config.json';
    a.click();
    URL.revokeObjectURL(url);

    showStatus('파일이 다운로드되었습니다.', 'success');
}

// ============== 상태 표시 ==============
function showStatus(message, type) {
    const el = document.getElementById('saveStatus');
    el.textContent = message;
    el.className = 'save-status ' + type;

    if (type === 'success') {
        setTimeout(() => { el.className = 'save-status'; }, 4000);
    }
}
