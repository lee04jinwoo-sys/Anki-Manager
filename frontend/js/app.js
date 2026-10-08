// ==========================================================================
// Anki Manager Pro — Frontend Application Logic (Media Toolkit Theme)
// ==========================================================================

document.addEventListener('DOMContentLoaded', () => {

  // --- Toast Notification Helper ---
  const toastBox = document.getElementById('toast-box');
  const toastMsg = document.getElementById('toast-msg');
  let toastTimer = null;

  function showToast(message, duration = 3000) {
    if (!toastBox || !toastMsg) return;
    toastMsg.textContent = message;
    toastBox.classList.add('show');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastBox.classList.remove('show');
    }, duration);
  }

  // ==========================================================================
  // 1. Main Capsule Category Navigation
  // ==========================================================================
  const mainTabBtns = document.querySelectorAll('.main-tab-btn');
  const categorySections = document.querySelectorAll('.category-section');

  mainTabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      mainTabBtns.forEach(b => b.classList.remove('active'));
      categorySections.forEach(sec => sec.classList.remove('active'));

      btn.classList.add('active');
      const targetId = btn.getAttribute('data-target');
      const targetSec = document.getElementById(targetId);
      if (targetSec) {
        targetSec.classList.add('active');
      }

      if (targetId === 'cat-stats') {
        fetchStats();
      } else if (targetId === 'cat-leech') {
        fetchLeechCards();
      }
    });
  });

  // ==========================================================================
  // 2. Anki Connect Status Check & Sync Action
  // ==========================================================================
  const ankiStatusBtn = document.getElementById('anki-status-btn');
  const ankiStatusDot = document.getElementById('anki-status-dot');
  const ankiStatusText = document.getElementById('anki-status-text');
  const btnSyncAnki = document.getElementById('btn-sync-anki');

  async function checkAnkiStatus() {
    try {
      const res = await fetch('/api/status/anki');
      const data = await res.json();
      if (data.connected) {
        if (ankiStatusDot) ankiStatusDot.classList.add('connected');
        if (ankiStatusText) ankiStatusText.textContent = 'Anki 연결됨';
      } else {
        if (ankiStatusDot) ankiStatusDot.classList.remove('connected');
        if (ankiStatusText) ankiStatusText.textContent = 'Anki 연결 안됨';
      }
    } catch {
      if (ankiStatusDot) ankiStatusDot.classList.remove('connected');
      if (ankiStatusText) ankiStatusText.textContent = 'Anki 오프라인';
    }
  }

  checkAnkiStatus();
  setInterval(checkAnkiStatus, 5000);
  if (ankiStatusBtn) ankiStatusBtn.addEventListener('click', () => {
    checkAnkiStatus();
    showToast('Anki 연결 상태를 다시 확인했습니다.');
  });

  if (btnSyncAnki) {
    btnSyncAnki.addEventListener('click', async () => {
      showToast('Anki 동기화를 요청하는 중...');
      startGlobalLogPolling('Anki Web 동기화');
      try {
        const res = await fetch('/api/organize/sync', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          showToast('Anki 동기화가 완료되었습니다.');
        } else {
          showToast('동기화 오류: ' + (data.message || '실패'));
        }
      } catch (e) {
        showToast('동기화 명령 오류: ' + e.message);
      }
    });
  }

  // ==========================================================================
  // 3. Global Live Terminal Logs & Progress Engine (모든 탭 공통)
  // ==========================================================================
  const progressArea = document.getElementById('progress-area');
  const progressBarCard = document.getElementById('progress-bar-card');
  const progressStatus = document.getElementById('progress-status');
  const progressPct = document.getElementById('progress-pct');
  const progressFill = document.getElementById('progress-fill');
  const logConsoleOutput = document.getElementById('log-console-output');
  const clearLogsBtn = document.getElementById('clear-logs-btn');
  const toggleLogsBtn = document.getElementById('toggle-logs-btn');
  const closeLogsBtn = document.getElementById('close-logs-btn');

  let logPollInterval = null;
  let isLogsCollapsed = false;

  // Clear any stale logs on fresh load
  fetch('/api/workflow/clear-logs', { method: 'POST' }).catch(() => {});

  function appendLogs(logs) {
    if (!logConsoleOutput || !logs) return;
    logConsoleOutput.innerHTML = '';
    logs.forEach(log => {
      const entry = document.createElement('div');
      const lvl = (log.level || 'info').toLowerCase();
      entry.className = `log-entry log-${lvl}`;
      entry.innerHTML = `<span class="log-time">[${log.time || ''}]</span><span class="log-msg">${log.message}</span>`;
      logConsoleOutput.appendChild(entry);
    });
    logConsoleOutput.scrollTop = logConsoleOutput.scrollHeight;
  }

  function startGlobalLogPolling(initialStepName = "작업 진행 중...") {
    if (progressArea) progressArea.style.display = 'flex';
    if (progressBarCard) progressBarCard.style.display = 'block';
    if (progressStatus) progressStatus.textContent = initialStepName;
    if (progressPct) progressPct.textContent = '10%';
    if (progressFill) {
      progressFill.style.width = '10%';
      progressFill.style.backgroundColor = '';
    }

    if (logPollInterval) clearInterval(logPollInterval);
    logPollInterval = setInterval(pollWorkflowStatus, 500);
  }

  function stopGlobalLogPolling() {
    if (logPollInterval) {
      clearInterval(logPollInterval);
      logPollInterval = null;
    }
  }

  async function pollWorkflowStatus() {
    try {
      const res = await fetch('/api/workflow/status');
      const data = await res.json();

      if (progressFill && data.progress !== undefined) {
        progressFill.style.width = `${Math.max(data.progress, 5)}%`;
      }
      if (progressPct && data.progress !== undefined) {
        progressPct.textContent = `${data.progress}%`;
      }
      if (progressStatus && data.current_step) {
        progressStatus.textContent = data.current_step;
      }
      if (data.logs) {
        appendLogs(data.logs);
      }

      if (!data.is_running) {
        stopGlobalLogPolling();
        if (runWorkflowBtn) runWorkflowBtn.disabled = false;

        const hasCandidates = data.candidates && ((data.candidates.sentences && data.candidates.sentences.length > 0) || (data.candidates.vocab && data.candidates.vocab.length > 0));

        if (data.status === 'waiting_selection' || (hasCandidates && data.status !== 'committing' && data.status !== 'success')) {
          renderSelectorUI(data.candidates || {}, data.meta || {});
          if (progressStatus) progressStatus.textContent = '후보 선별 단계: 아래 목록에서 원하는 항목을 선택하세요.';
          showToast('학습 후보 추출 완료! 원하는 항목을 선택하세요.');
        } else if (data.status === 'success') {
          if (progressFill) {
            progressFill.style.width = '100%';
            progressFill.style.backgroundColor = 'var(--success)';
          }
          if (progressPct) progressPct.textContent = '100%';
          if (progressStatus) progressStatus.textContent = data.current_step || '모든 작업이 성공적으로 완료되었습니다.';
        } else if (data.status === 'error') {
          if (progressFill) progressFill.style.backgroundColor = 'var(--danger)';
          if (progressStatus) progressStatus.textContent = '작업 중 오류가 발생했습니다. 로그를 확인하세요.';
        }
      }
    } catch (e) {
      console.error("로그 폴링 에러:", e);
    }
  }

  if (clearLogsBtn) {
    clearLogsBtn.addEventListener('click', async () => {
      await fetch('/api/workflow/clear-logs', { method: 'POST' });
      if (logConsoleOutput) {
        logConsoleOutput.innerHTML = '<div class="log-entry log-info">[시스템] 로그가 초기화되었습니다.</div>';
      }
      if (progressBarCard) progressBarCard.style.display = 'none';
      if (selectorPanel) selectorPanel.style.display = 'none';
      showToast('실시간 로그가 초기화되었습니다.');
    });
  }

  if (toggleLogsBtn && logConsoleOutput) {
    toggleLogsBtn.addEventListener('click', () => {
      isLogsCollapsed = !isLogsCollapsed;
      if (isLogsCollapsed) {
        logConsoleOutput.style.display = 'none';
        toggleLogsBtn.textContent = '펼치기';
      } else {
        logConsoleOutput.style.display = 'flex';
        toggleLogsBtn.textContent = '접기';
      }
    });
  }

  if (closeLogsBtn && progressArea) {
    closeLogsBtn.addEventListener('click', () => {
      progressArea.style.display = 'none';
      stopGlobalLogPolling();
    });
  }

  // ==========================================================================
  // 4. Studio 1: Note Extraction & Direct-Click Source Buttons
  // ==========================================================================
  const sourceCardBtns = document.querySelectorAll('.source-card-btn');
  const inputDataGroup = document.getElementById('input-data-group');
  const inputDataLabel = document.getElementById('input-data-label');
  const inputData = document.getElementById('input-data');
  const autoModeCheckbox = document.getElementById('auto-mode-checkbox');
  const runWorkflowBtn = document.getElementById('run-workflow-btn');
  const runBtnText = document.getElementById('run-btn-text');

  // Selector DOM
  const selectorPanel = document.getElementById('selector-panel');
  const sentenceCountBadge = document.getElementById('sentence-count-badge');
  const vocabCountBadge = document.getElementById('vocab-count-badge');
  const sentencesSelectorList = document.getElementById('sentences-selector-list');
  const vocabSelectorList = document.getElementById('vocab-selector-list');
  const selectAllSentencesBtn = document.getElementById('select-all-sentences');
  const deselectAllSentencesBtn = document.getElementById('deselect-all-sentences');
  const selectAllVocabBtn = document.getElementById('select-all-vocab');
  const deselectAllVocabBtn = document.getElementById('deselect-all-vocab');
  const commitSelectionBtn = document.getElementById('commit-selection-btn');
  const cancelSelectionBtn = document.getElementById('cancel-selection-btn');
  const commitBtnText = document.getElementById('commit-btn-text');

  let currentExtractionMeta = {};
  let currentSource = "youtube"; // default

  function setDataSource(source) {
    currentSource = source;
    sourceCardBtns.forEach(btn => {
      if (btn.getAttribute('data-source') === source) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    if (source === 'obsidian' || source === 'github' || source === 'modern_family') {
      if (inputDataGroup) inputDataGroup.style.display = 'none';
    } else {
      if (inputDataGroup) inputDataGroup.style.display = 'flex';
      if (inputData) {
        if (source === 'youtube') {
          inputData.placeholder = 'YouTube 비디오 URL을 입력하세요...';
          if (inputDataLabel) inputDataLabel.textContent = '입력 (YouTube 비디오 URL)';
        } else if (source === 'knowledge') {
          inputData.placeholder = 'YouTube URL, 웹 문서 URL, 또는 원문 텍스트를 입력하세요...';
          if (inputDataLabel) inputDataLabel.textContent = '입력 (지식/교양 URL 또는 원문 텍스트)';
        } else if (source === 'situation') {
          inputData.placeholder = '학습하고 싶은 회화 상황을 입력하세요 (예: 비즈니스 미팅, 식당 예약)...';
          if (inputDataLabel) inputDataLabel.textContent = '입력 (회화 상황 키워드)';
        }
      }
    }
  }

  sourceCardBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const source = btn.getAttribute('data-source');
      setDataSource(source);
    });
  });

  if (autoModeCheckbox && runBtnText) {
    autoModeCheckbox.addEventListener('change', (e) => {
      runBtnText.textContent = e.target.checked ? "원클릭 즉시 실행" : "후보 추출 및 선별";
    });
  }

  function renderSelectorUI(candidates, meta) {
    currentExtractionMeta = meta || {};
    const sentences = candidates.sentences || [];
    const vocab = candidates.vocab || [];

    if (sentenceCountBadge) sentenceCountBadge.textContent = sentences.length;
    if (vocabCountBadge) vocabCountBadge.textContent = vocab.length;

    // Render Sentences
    if (sentencesSelectorList) {
      sentencesSelectorList.innerHTML = '';
      if (sentences.length === 0) {
        sentencesSelectorList.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 12px; text-align: center;">추출된 문장 후보가 없습니다.</div>';
      } else {
        sentences.forEach((s, idx) => {
          const item = document.createElement('div');
          item.className = 'selector-item';
          item.id = `s-item-${idx}`;
          const sentText = typeof s === 'string' ? s : (s.문장 || '');
          item.innerHTML = `
            <input type="checkbox" id="chk-s-${idx}" class="chk-sentence" checked style="width: 15px; height: 15px; cursor: pointer;">
            <input type="text" value="${sentText.replace(/"/g, '&quot;')}" class="selector-input input-sentence" style="flex: 1;">
            <button type="button" class="btn-del-item" title="삭제" onclick="document.getElementById('s-item-${idx}').remove(); window.updateCommitBtnCount();">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          `;
          sentencesSelectorList.appendChild(item);
        });
      }
    }

    // Render Vocab
    if (vocabSelectorList) {
      vocabSelectorList.innerHTML = '';
      if (vocab.length === 0) {
        vocabSelectorList.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 12px; text-align: center;">추출된 단어/Q&A 후보가 없습니다.</div>';
      } else {
        vocab.forEach((v, idx) => {
          const item = document.createElement('div');
          item.className = 'selector-item';
          item.id = `v-item-${idx}`;
          const wordText = typeof v === 'string' ? v : (v.단어 || '');
          const meanText = typeof v === 'string' ? '' : (v.뜻 || '');
          item.innerHTML = `
            <input type="checkbox" id="chk-v-${idx}" class="chk-vocab" checked style="width: 15px; height: 15px; cursor: pointer;">
            <div style="display: flex; gap: 8px; flex: 1;">
              <input type="text" value="${wordText.replace(/"/g, '&quot;')}" placeholder="단어/질문" class="selector-input input-vocab-word" style="flex: 1; font-weight: 600;">
              <input type="text" value="${meanText.replace(/"/g, '&quot;')}" placeholder="뜻/정답" class="selector-input input-vocab-meaning" style="flex: 1.2; color: var(--text-secondary);">
            </div>
            <button type="button" class="btn-del-item" title="삭제" onclick="document.getElementById('v-item-${idx}').remove(); window.updateCommitBtnCount();">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          `;
          vocabSelectorList.appendChild(item);
        });
      }
    }

    window.updateCommitBtnCount();
    if (selectorPanel) {
      selectorPanel.style.display = 'flex';
      setTimeout(() => {
        selectorPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    }
  }

  window.updateCommitBtnCount = function() {
    if (!commitBtnText) return;
    const sChecked = sentencesSelectorList ? sentencesSelectorList.querySelectorAll('.chk-sentence:checked').length : 0;
    const vChecked = vocabSelectorList ? vocabSelectorList.querySelectorAll('.chk-vocab:checked').length : 0;
    commitBtnText.textContent = `선택 항목 Anki 등록 및 AI 완성 (문장 ${sChecked}개, 단어/Q&A ${vChecked}개)`;
  };

  if (sentencesSelectorList) sentencesSelectorList.addEventListener('change', window.updateCommitBtnCount);
  if (vocabSelectorList) vocabSelectorList.addEventListener('change', window.updateCommitBtnCount);

  if (selectAllSentencesBtn) {
    selectAllSentencesBtn.addEventListener('click', () => {
      if (sentencesSelectorList) {
        sentencesSelectorList.querySelectorAll('.chk-sentence').forEach(cb => cb.checked = true);
        window.updateCommitBtnCount();
      }
    });
  }
  if (deselectAllSentencesBtn) {
    deselectAllSentencesBtn.addEventListener('click', () => {
      if (sentencesSelectorList) {
        sentencesSelectorList.querySelectorAll('.chk-sentence').forEach(cb => cb.checked = false);
        window.updateCommitBtnCount();
      }
    });
  }
  if (selectAllVocabBtn) {
    selectAllVocabBtn.addEventListener('click', () => {
      if (vocabSelectorList) {
        vocabSelectorList.querySelectorAll('.chk-vocab').forEach(cb => cb.checked = true);
        window.updateCommitBtnCount();
      }
    });
  }
  if (deselectAllVocabBtn) {
    deselectAllVocabBtn.addEventListener('click', () => {
      if (vocabSelectorList) {
        vocabSelectorList.querySelectorAll('.chk-vocab').forEach(cb => cb.checked = false);
        window.updateCommitBtnCount();
      }
    });
  }

  if (cancelSelectionBtn) {
    cancelSelectionBtn.addEventListener('click', () => {
      if (selectorPanel) selectorPanel.style.display = 'none';
      if (runWorkflowBtn) runWorkflowBtn.disabled = false;
      showToast('선별 작업이 취소되었습니다.');
    });
  }

  if (commitSelectionBtn) {
    commitSelectionBtn.addEventListener('click', async () => {
      const selectedSentences = [];
      if (sentencesSelectorList) {
        sentencesSelectorList.querySelectorAll('.selector-item').forEach(item => {
          const chk = item.querySelector('.chk-sentence');
          const inp = item.querySelector('.input-sentence');
          if (chk && chk.checked && inp && inp.value.trim()) {
            selectedSentences.push(inp.value.trim());
          }
        });
      }

      const selectedVocab = [];
      if (vocabSelectorList) {
        vocabSelectorList.querySelectorAll('.selector-item').forEach(item => {
          const chk = item.querySelector('.chk-vocab');
          const wInp = item.querySelector('.input-vocab-word');
          const mInp = item.querySelector('.input-vocab-meaning');
          if (chk && chk.checked && wInp && wInp.value.trim()) {
            selectedVocab.push({
              '단어': wInp.value.trim(),
              '뜻': mInp ? mInp.value.trim() : ''
            });
          }
        });
      }

      if (selectedSentences.length === 0 && selectedVocab.length === 0) {
        showToast('최소 1개 이상의 문장이나 단어를 선택해야 합니다.');
        return;
      }

      if (selectorPanel) selectorPanel.style.display = 'none';
      startGlobalLogPolling('선택 항목 AI 보강 및 Anki 등록 시작...');
      if (runWorkflowBtn) runWorkflowBtn.disabled = true;

      try {
        const res = await fetch('/api/workflow/commit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source: currentSource,
            meta: currentExtractionMeta,
            selected_sentences: selectedSentences,
            selected_vocab: selectedVocab
          })
        });
        const data = await res.json();
        if (data.status !== 'success') {
          throw new Error(data.message || '등록 처리 실패');
        }
      } catch (err) {
        if (progressStatus) progressStatus.textContent = '오류 발생: ' + err.message;
        if (progressFill) progressFill.style.backgroundColor = 'var(--danger)';
        if (runWorkflowBtn) runWorkflowBtn.disabled = false;
        showToast('등록 중 에러: ' + err.message);
      }
    });
  }

  if (runWorkflowBtn) {
    runWorkflowBtn.addEventListener('click', async () => {
      const source = currentSource || "youtube";
      const inputVal = inputData ? inputData.value : "";
      const isAuto = autoModeCheckbox ? autoModeCheckbox.checked : false;

      if (selectorPanel) selectorPanel.style.display = 'none';
      startGlobalLogPolling(isAuto ? `[${source}] 원클릭 자동 작업 시작...` : `[${source}] 학습 데이터 후보 추출 중...`);
      runWorkflowBtn.disabled = true;

      try {
        const endpoint = isAuto ? '/api/workflow/' : '/api/workflow/extract';
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source, input_data: inputVal })
        });
        const data = await response.json();

        if (data.status !== 'success') {
          throw new Error(data.message || '작업 시작 실패');
        }
      } catch (err) {
        if (progressStatus) progressStatus.textContent = '오류 발생: ' + err.message;
        if (progressFill) progressFill.style.backgroundColor = 'var(--danger)';
        runWorkflowBtn.disabled = false;
        showToast('오류 발생: ' + err.message);
      }
    });
  }

  // ==========================================================================
  // 5. Studio 2: Organize Batch Actions (실시간 글로벌 로그 연동)
  // ==========================================================================
  const organizeBtns = document.querySelectorAll('.btn-action');
  organizeBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const action = btn.getAttribute('data-action');
      const actionTitle = btn.querySelector('h3')?.textContent || '작업';
      showToast(`${actionTitle}을 실행하는 중...`);
      startGlobalLogPolling(`[노트 정리] ${actionTitle} 실행 중...`);

      try {
        const res = await fetch(`/api/organize/${action}`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          showToast(`✅ ${data.message || '작업을 시작했습니다.'}`);
        } else {
          showToast(`❌ ${data.message || '처리 중 오류가 발생했습니다.'}`);
        }
      } catch (err) {
        showToast(`❌ 오류 발생: ${err.message}`);
      }
    });
  });

  // ==========================================================================
  // 6. Studio 3: Leech Rescue Studio (스마트 망각 구제 & AI 진단 파이프라인)
  // ==========================================================================
  const btnFetchLeech = document.getElementById('btn-fetch-leech');
  const btnDiagnoseLeech = document.getElementById('btn-diagnose-leech');
  const btnApplyLeech = document.getElementById('btn-apply-leech');
  const leechLimitSelect = document.getElementById('leech-limit-select');
  const leechTbody = document.getElementById('leech-tbody');
  const leechTotalCountSpan = document.getElementById('leech-total-count');

  let currentLeechCandidates = [];
  let currentDiagnoses = [];

  async function fetchLeechCards() {
    if (!leechTbody) return;
    const limit = leechLimitSelect ? leechLimitSelect.value : 100;
    leechTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 32px;"><div class="spinner" style="margin: 0 auto 12px;"></div>상위 ${limit}개 망각 카드를 Anki에서 조회하는 중...</td></tr>`;
    if (btnDiagnoseLeech) btnDiagnoseLeech.style.display = 'none';
    if (btnApplyLeech) btnApplyLeech.style.display = 'none';

    try {
      const res = await fetch(`/api/leech/candidates?limit=${limit}`);
      const data = await res.json();

      if (data.status === 'success') {
        currentLeechCandidates = data.candidates || [];
        if (leechTotalCountSpan) {
          leechTotalCountSpan.textContent = (data.total_remaining || 0).toLocaleString();
        }

        if (currentLeechCandidates.length === 0) {
          leechTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--success); padding: 32px; font-weight: 600;">🎉 현재 구제 대상 망각(Leech) 카드가 없습니다! 모든 카드가 건강한 상태입니다.</td></tr>`;
          return;
        }

        renderCandidatesTable(currentLeechCandidates);
        if (btnDiagnoseLeech) {
          btnDiagnoseLeech.style.display = 'inline-flex';
          btnDiagnoseLeech.textContent = `🤖 Gemini AI 심층 진단 (${currentLeechCandidates.length}개)`;
        }
      } else {
        leechTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--danger); padding: 24px;">조회 실패: ${data.message || '오류 발생'}</td></tr>`;
      }
    } catch (err) {
      leechTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--danger); padding: 24px;">네트워크 오류: ${err.message}</td></tr>`;
    }
  }

  function renderCandidatesTable(candidates) {
    if (!leechTbody) return;
    leechTbody.innerHTML = '';

    candidates.forEach((c, idx) => {
      const tr = document.createElement('tr');
      tr.id = `leech-row-${c.id}`;
      tr.innerHTML = `
        <td style="font-weight: 700; color: var(--text-primary); font-size: 14px;">${c.word}</td>
        <td style="text-align: right; font-family: var(--font-mono); font-size: 12px;">
          <span style="color: #ef4444; font-weight: 700;">${c.lapses}회</span>
          <span style="color: var(--text-muted); margin: 0 2px;">/</span>
          <span style="color: var(--warning);">${c.ease}%</span>
        </td>
        <td style="color: var(--text-secondary); font-size: 13px;">${c.meaning || '<span style="color:var(--text-muted);">(뜻 없음)</span>'}</td>
        <td style="color: var(--text-muted); font-size: 12px;">
          <span class="panel-badge" style="background: rgba(148, 163, 184, 0.15); color: #94a3b8;">진단 대기</span>
        </td>
        <td style="color: var(--text-muted); font-size: 12px;">
          ${c.explain ? c.explain.slice(0, 80) + '...' : '(상세 설명 없음)'}
        </td>
      `;
      leechTbody.appendChild(tr);
    });
  }

  async function runLeechDiagnosis() {
    if (!currentLeechCandidates || currentLeechCandidates.length === 0) {
      showToast('⚠️ 먼저 망각 카드를 조회해 주세요.');
      return;
    }

    if (btnDiagnoseLeech) {
      btnDiagnoseLeech.disabled = true;
      btnDiagnoseLeech.innerHTML = `<div class="spinner" style="width:14px; height:14px; border-width:2px; display:inline-block; margin-right:6px;"></div> AI 진단 분석 중...`;
    }
    showToast(`🤖 Gemini AI가 ${currentLeechCandidates.length}개 망각 단어를 정밀 진단 중입니다...`);

    try {
      const res = await fetch('/api/leech/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ candidates: currentLeechCandidates })
      });
      const data = await res.json();

      if (data.status === 'success' && data.diagnoses) {
        currentDiagnoses = data.diagnoses;
        renderDiagnosesTable(currentDiagnoses);
        showToast(`✅ ${currentDiagnoses.length}개 단어 맞춤 진단 완료! 내용을 검토하고 적용하세요.`);
        if (btnApplyLeech) {
          btnApplyLeech.style.display = 'inline-flex';
          btnApplyLeech.textContent = `🚀 ${currentDiagnoses.length}개 처방 조치 일괄 적용`;
        }
      } else {
        showToast(`❌ 진단 실패: ${data.message || '알 수 없는 오류'}`);
      }
    } catch (err) {
      showToast(`❌ 진단 오류: ${err.message}`);
    } finally {
      if (btnDiagnoseLeech) {
        btnDiagnoseLeech.disabled = false;
        btnDiagnoseLeech.innerHTML = `🤖 Gemini AI 심층 진단 다시 실행`;
      }
    }
  }

  function renderDiagnosesTable(diagnoses) {
    if (!leechTbody) return;
    leechTbody.innerHTML = '';

    const actionColors = {
      'revamp_idiom': { bg: 'rgba(168, 85, 247, 0.15)', text: '#c084fc', border: 'rgba(168, 85, 247, 0.3)', label: '🟣 이디엄/청크 재포장' },
      'revamp_collocation': { bg: 'rgba(59, 130, 246, 0.15)', text: '#60a5fa', border: 'rgba(59, 130, 246, 0.3)', label: '🔵 콜로케이션 보강' },
      'sentence': { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: 'rgba(16, 185, 129, 0.3)', label: '🟢 문장 승격' },
      'delete': { bg: 'rgba(239, 68, 68, 0.15)', text: '#f87171', border: 'rgba(239, 68, 68, 0.3)', label: '🔴 영구 삭제' },
      'reset_only': { bg: 'rgba(148, 163, 184, 0.15)', text: '#94a3b8', border: 'rgba(148, 163, 184, 0.3)', label: '⚪ 스케줄만 초기화' }
    };

    diagnoses.forEach((d, idx) => {
      const orig = currentLeechCandidates.find(c => c.id === d.id) || {};
      const cfg = actionColors[d.action] || actionColors['revamp_collocation'];

      const tr = document.createElement('tr');
      tr.id = `diag-row-${d.id}`;

      let previewHtml = '';
      if (d.action === 'revamp_idiom') {
        previewHtml = `
          <div style="font-size: 13px; margin-bottom: 4px;">
            <strong style="color: #c084fc;">개편 표기:</strong> <span class="editable-field" style="color: #f3f4f6; font-weight: 700;">${d.target_word}</span>
            <span style="color: var(--text-muted); margin: 0 4px;">➜</span>
            <span style="color: var(--text-primary);">${d.target_meaning}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">💡 ${d.reason}</div>
        `;
      } else if (d.action === 'revamp_collocation') {
        previewHtml = `
          <div style="font-size: 13px; margin-bottom: 4px;">
            <strong style="color: #60a5fa;">보강 뜻:</strong> <span>${d.target_meaning}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">💡 ${d.reason}</div>
        `;
      } else if (d.action === 'sentence') {
        previewHtml = `
          <div style="font-size: 13px; margin-bottom: 4px;">
            <strong style="color: #34d399;">신규 예문:</strong> <span style="color: #f3f4f6;">${d.sentence_en}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-secondary); margin-bottom: 4px;">번역: ${d.sentence_ko}</div>
          <div style="font-size: 11px; color: var(--text-muted);">💡 ${d.reason}</div>
        `;
      } else if (d.action === 'delete') {
        previewHtml = `
          <div style="font-size: 12px; color: #f87171; line-height: 1.4;">⚠️ <strong>삭제 예정:</strong> ${d.reason}</div>
        `;
      } else {
        previewHtml = `<div style="font-size: 12px; color: var(--text-muted);">${d.reason}</div>`;
      }

      tr.innerHTML = `
        <td style="font-weight: 700; color: var(--text-primary); font-size: 14px;">${d.word}</td>
        <td style="text-align: right; font-family: var(--font-mono); font-size: 12px;">
          <span style="color: #ef4444; font-weight: 700;">${orig.lapses || 0}회</span>
          <span style="color: var(--text-muted); margin: 0 2px;">/</span>
          <span style="color: var(--warning);">${orig.ease || 130}%</span>
        </td>
        <td style="color: var(--text-secondary); font-size: 13px;">${orig.meaning || '-'}</td>
        <td>
          <select class="diag-action-select" data-id="${d.id}" style="padding: 5px 8px; border-radius: 6px; background: ${cfg.bg}; color: ${cfg.text}; border: 1px solid ${cfg.border}; font-size: 12px; font-weight: 700; cursor: pointer;">
            <option value="revamp_idiom" ${d.action === 'revamp_idiom' ? 'selected' : ''}>🟣 이디엄/청크 재포장</option>
            <option value="revamp_collocation" ${d.action === 'revamp_collocation' ? 'selected' : ''}>🔵 콜로케이션 보강</option>
            <option value="sentence" ${d.action === 'sentence' ? 'selected' : ''}>🟢 문장 승격</option>
            <option value="delete" ${d.action === 'delete' ? 'selected' : ''}>🔴 영구 삭제</option>
            <option value="reset_only" ${d.action === 'reset_only' ? 'selected' : ''}>⚪ 스케줄만 초기화</option>
          </select>
        </td>
        <td>${previewHtml}</td>
      `;

      leechTbody.appendChild(tr);
    });

    // Handle user manual dropdown changes
    document.querySelectorAll('.diag-action-select').forEach(sel => {
      sel.addEventListener('change', (e) => {
        const nid = parseInt(e.target.getAttribute('data-id'), 10);
        const newAct = e.target.value;
        const item = currentDiagnoses.find(x => x.id === nid);
        if (item) {
          item.action = newAct;
          const cfg = actionColors[newAct] || actionColors['revamp_collocation'];
          e.target.style.background = cfg.bg;
          e.target.style.color = cfg.text;
          e.target.style.borderColor = cfg.border;
        }
      });
    });
  }

  async function applyLeechActions() {
    if (!currentDiagnoses || currentDiagnoses.length === 0) {
      showToast('⚠️ 적용할 진단 내역이 없습니다.');
      return;
    }

    const confirmMsg = `총 ${currentDiagnoses.length}개의 카드에 대한 처방(이디엄 개편, 콜로케이션 보강, 문장 승격, 삭제 및 Ease 250% 리셋)을 Anki에 일괄 적용하시겠습니까?`;
    if (!confirm(confirmMsg)) return;

    if (btnApplyLeech) {
      btnApplyLeech.disabled = true;
      btnApplyLeech.innerHTML = `<div class="spinner" style="width:14px; height:14px; border-width:2px; display:inline-block; margin-right:6px;"></div> Anki 적용 중...`;
    }
    showToast('🚀 Anki에 카드 처방을 일괄 반영하고 있습니다...');

    try {
      const res = await fetch('/api/leech/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actions: currentDiagnoses })
      });
      const data = await res.json();

      if (data.status === 'success') {
        showToast(`🎉 ${data.message}`);
        currentDiagnoses = [];
        currentLeechCandidates = [];
        // Refresh remaining leech count and next batch
        fetchLeechCards();
      } else {
        showToast(`❌ 적용 실패: ${data.message || '오류 발생'}`);
      }
    } catch (err) {
      showToast(`❌ 적용 오류: ${err.message}`);
    } finally {
      if (btnApplyLeech) {
        btnApplyLeech.disabled = false;
        btnApplyLeech.innerHTML = `🚀 처방 조치 일괄 적용`;
      }
    }
  }

  if (btnFetchLeech) btnFetchLeech.addEventListener('click', fetchLeechCards);
  if (btnDiagnoseLeech) btnDiagnoseLeech.addEventListener('click', runLeechDiagnosis);
  if (btnApplyLeech) btnApplyLeech.addEventListener('click', applyLeechActions);
  if (leechLimitSelect) leechLimitSelect.addEventListener('change', fetchLeechCards);

  // ==========================================================================
  // 7. Studio 4: Card Design Management Studio (실시간 글로벌 로그 연동)
  // ==========================================================================
  const designBtns = document.querySelectorAll('.btn-design-action');
  const designResultStatus = document.getElementById('design-result-status');

  designBtns.forEach(btn => {
    btn.addEventListener('click', async () => {
      const action = btn.getAttribute('data-action');
      const actionTitle = btn.querySelector('h3')?.textContent || '디자인 작업';
      
      showToast(`${actionTitle} 실행 중...`);
      startGlobalLogPolling(`[카드 디자인] ${actionTitle} 실행 중...`);

      try {
        const res = await fetch(`/api/design/${action}`, { method: 'POST' });
        const data = await res.json();

        if (data.status === 'success') {
          if (designResultStatus) {
            designResultStatus.innerHTML = `<div class="log-entry log-success">[성공] ${data.message}</div>`;
          }
          showToast(`✅ ${data.message}`);
        } else {
          if (designResultStatus) {
            designResultStatus.innerHTML = `<div class="log-entry log-error">[오류] ${data.message}</div>`;
          }
          showToast(`❌ ${data.message}`);
        }
      } catch (err) {
        if (designResultStatus) {
          designResultStatus.innerHTML = `<div class="log-entry log-error">[통신 오류] ${err.message}</div>`;
        }
        showToast(`❌ 통신 오류: ${err.message}`);
      }
    });
  });

  // ==========================================================================
  // 8. Studio 5: Deck Analytics & Progress Studio
  // ==========================================================================
  const refreshStatsBtn = document.getElementById('refresh-stats-btn');
  const statsTbody = document.getElementById('stats-tbody');
  const metricTotalCards = document.getElementById('metric-total-cards');
  const metricDueCards = document.getElementById('metric-due-cards');
  const metricNewCards = document.getElementById('metric-new-cards');
  const metricLeechCards = document.getElementById('metric-leech-cards');

  async function fetchStats() {
    if (!statsTbody) return;
    statsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 24px;">통계 데이터를 불러오는 중...</td></tr>`;
    try {
      const res = await fetch('/api/stats/');
      const json = await res.json();

      if (json.status === 'success' && json.data) {
        statsTbody.innerHTML = '';
        let totalCount = 0;
        let dueCount = 0;
        let newCount = 0;

        json.data.forEach(d => {
          if (d.name === '[Root]' || d.name === 'listening') return;
          totalCount += (d.total || 0);
          dueCount += (d.due || 0);
          newCount += (d.new || 0);

          statsTbody.innerHTML += `
            <tr>
              <td style="font-weight: 600; color: var(--text-primary);">${d.name}</td>
              <td class="numeric" style="color: var(--text-secondary);">${d.total || 0}</td>
              <td class="numeric" style="color: var(--success); font-weight: 600;">${d.new || 0}</td>
              <td class="numeric" style="color: #60a5fa; font-weight: 600;">${d.due || 0}</td>
              <td class="numeric" style="color: var(--text-primary);">${d.reviews_today || 0}</td>
              <td class="numeric" style="color: var(--warning);">${d.exhaust_days || '∞'}일</td>
            </tr>
          `;
        });

        if (metricTotalCards) metricTotalCards.textContent = totalCount.toLocaleString();
        if (metricDueCards) metricDueCards.textContent = dueCount.toLocaleString();
        if (metricNewCards) metricNewCards.textContent = newCount.toLocaleString();
        if (metricLeechCards) metricLeechCards.textContent = (json.leech_count || 0).toLocaleString();

      } else {
        statsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger); padding: 24px;">${json.message || 'Anki 오프라인 상태'}</td></tr>`;
      }
    } catch (e) {
      statsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--danger); padding: 24px;">통계를 불러오지 못했습니다 (${e.message}).</td></tr>`;
    }
  }

  if (refreshStatsBtn) refreshStatsBtn.addEventListener('click', () => {
    fetchStats();
    showToast('통계 데이터를 새로고침했습니다.');
  });

});
