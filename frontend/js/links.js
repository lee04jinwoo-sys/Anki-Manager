/**
 * Anki Manager - 단어 ↔ 문장 연결 관리 스크립트
 */

const LinkManagerUI = (function() {
  let state = {
    items: [],
    selectedIds: new Set(),
    total: 0,
    limit: 50,
    offset: 0,
    maxLinks: null,
    search: '',
    isLoading: false
  };

  function init() {
    bindEvents();
    loadStats();
    loadVocab();
  }

  function bindEvents() {
    // 서브 뷰 토글
    const tileBtn = document.getElementById('btn-open-link-manager');
    const panel = document.getElementById('link-manager-panel');
    if (tileBtn && panel) {
      tileBtn.addEventListener('click', () => {
        const isHidden = panel.style.display === 'none' || !panel.style.display;
        panel.style.display = isHidden ? 'block' : 'none';
        if (isHidden) {
          loadStats();
          loadVocab();
          panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    }

    // 전체 재스캔 버튼
    const scanBtn = document.getElementById('lm-scan-btn');
    if (scanBtn) {
      scanBtn.addEventListener('click', scanAndRebuild);
    }

    // 템플릿 적용 버튼
    const applyTplBtn = document.getElementById('lm-apply-template-btn');
    if (applyTplBtn) {
      applyTplBtn.addEventListener('click', applyCardTemplates);
    }

    // 검색창 엔터 및 디바운스
    const searchInput = document.getElementById('lm-search-input');
    if (searchInput) {
      let timer = null;
      searchInput.addEventListener('input', (e) => {
        clearTimeout(timer);
        timer = setTimeout(() => {
          state.search = e.target.value.trim();
          state.offset = 0;
          loadVocab();
        }, 300);
      });
    }

    // 필터 버튼들 (전체, 0개만, 1개 이하)
    document.querySelectorAll('.lm-filter-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.lm-filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const filterVal = btn.getAttribute('data-filter');
        if (filterVal === '0') state.maxLinks = 0;
        else if (filterVal === '1') state.maxLinks = 1;
        else state.maxLinks = null;
        state.offset = 0;
        loadVocab();
      });
    });

    // 전체 선택 / 해제
    const selectAllBtn = document.getElementById('lm-select-all-btn');
    if (selectAllBtn) {
      selectAllBtn.addEventListener('click', () => {
        state.items.forEach(item => state.selectedIds.add(item.note_id));
        updateSelectionUI();
      });
    }

    const deselectAllBtn = document.getElementById('lm-deselect-all-btn');
    if (deselectAllBtn) {
      deselectAllBtn.addEventListener('click', () => {
        state.selectedIds.clear();
        updateSelectionUI();
      });
    }

    // 최다 오답 20개 뽑기
    const leechPickBtn = document.getElementById('lm-leech-pick-btn');
    if (leechPickBtn) {
      leechPickBtn.addEventListener('click', pickLeechUnlinked);
    }

    // 랜덤 20개 뽑기
    const randomPickBtn = document.getElementById('lm-random-pick-btn');
    if (randomPickBtn) {
      randomPickBtn.addEventListener('click', pickRandomUnlinked);
    }

    // 0개 연결만 선택
    const selectZeroBtn = document.getElementById('lm-select-zero-btn');
    if (selectZeroBtn) {
      selectZeroBtn.addEventListener('click', () => {
        state.selectedIds.clear();
        state.items.forEach(item => {
          if (item.link_count === 0) state.selectedIds.add(item.note_id);
        });
        updateSelectionUI();
      });
    }

    // 일괄 생성 버튼
    const batchBtn = document.getElementById('lm-batch-gen-btn');
    if (batchBtn) {
      batchBtn.addEventListener('click', executeBatchGeneration);
    }
  }

  async function pickLeechUnlinked() {
    const btn = document.getElementById('lm-leech-pick-btn');
    const originText = btn ? btn.innerHTML : '';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner" style="display:inline-block; width:12px; height:12px; border:2px solid #f87171; border-top-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; vertical-align:middle; margin-right:4px;"></span> 추출 중...`;
    }

    try {
      const res = await fetch('/api/links/leech?count=20');
      if (!res.ok) throw new Error("최다 오답 단어 추출 실패");
      const data = await res.json();
      if (!data.items || data.items.length === 0) {
        alert("현재 미연결(0개) 오답 단어가 없습니다! 🎉");
        return;
      }
      state.items = data.items;
      state.total = data.items.length;
      state.selectedIds.clear();
      data.items.forEach(item => state.selectedIds.add(item.note_id));
      renderTable();
      updateSelectionUI();
    } catch (e) {
      alert("최다 오답 단어 추출 실패: " + e.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originText;
      }
    }
  }

  async function pickRandomUnlinked() {
    const btn = document.getElementById('lm-random-pick-btn');
    const originText = btn ? btn.innerHTML : '';
    if (btn) {
      btn.disabled = true;
      btn.innerHTML = `<span class="spinner" style="display:inline-block; width:12px; height:12px; border:2px solid #c084fc; border-top-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; vertical-align:middle; margin-right:4px;"></span> 뽑는 중...`;
    }

    try {
      const res = await fetch('/api/links/random?count=20');
      if (!res.ok) throw new Error("랜덤 추출 실패");
      const data = await res.json();
      if (!data.items || data.items.length === 0) {
        alert("현재 미연결(0개) 단어가 없습니다! 🎉");
        return;
      }
      state.items = data.items;
      state.total = data.items.length;
      state.selectedIds.clear();
      data.items.forEach(item => state.selectedIds.add(item.note_id));
      renderTable();
      updateSelectionUI();
    } catch (e) {
      alert("랜덤 단어 추출 실패: " + e.message);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originText;
      }
    }
  }

  async function loadStats() {
    try {
      const res = await fetch('/api/links/stats');
      if (!res.ok) return;
      const data = await res.json();
      
      const badge = document.getElementById('unlinked-count-badge');
      if (badge) badge.innerText = `미연결: ${data.unlinked_vocab}개`;

      const statTotalV = document.getElementById('lm-stat-total-vocab');
      if (statTotalV) statTotalV.innerText = data.total_vocab;

      const statTotalL = document.getElementById('lm-stat-total-links');
      if (statTotalL) statTotalL.innerText = data.total_links;

      const statUnlinked = document.getElementById('lm-stat-unlinked');
      if (statUnlinked) statUnlinked.innerText = data.unlinked_vocab;
    } catch (e) {
      console.error("통계 로드 실패:", e);
    }
  }

  async function loadVocab() {
    const listBody = document.getElementById('lm-vocab-tbody');
    if (!listBody) return;

    listBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 24px; color: var(--text-muted);">단어 목록을 불러오는 중...</td></tr>`;

    let url = `/api/links/vocab?limit=${state.limit}&offset=${state.offset}`;
    if (state.maxLinks !== null) url += `&max_links=${state.maxLinks}`;
    if (state.search) url += `&search=${encodeURIComponent(state.search)}`;

    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("단어 목록 조회 오류");
      const data = await res.json();
      state.items = data.items;
      state.total = data.total;
      renderTable();
      updateSelectionUI();
    } catch (e) {
      listBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 24px; color: var(--danger);">오류 발생: ${e.message}</td></tr>`;
    }
  }

  function renderTable() {
    const listBody = document.getElementById('lm-vocab-tbody');
    if (!listBody) return;

    if (state.items.length === 0) {
      listBody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 32px; color: var(--text-muted);">해당 조건의 단어가 없습니다. [전체 자동 재스캔]을 눌러보세요!</td></tr>`;
      return;
    }

    listBody.innerHTML = state.items.map(item => {
      const isChecked = state.selectedIds.has(item.note_id) ? 'checked' : '';
      let badgeStyle = 'background: rgba(34, 197, 94, 0.15); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.3);';
      if (item.link_count === 0) {
        badgeStyle = 'background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3); font-weight: 700;';
      } else if (item.link_count === 1) {
        badgeStyle = 'background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);';
      }

      const lapseBadge = (item.lapses !== undefined && item.lapses !== null && item.lapses > 0)
        ? `<span style="display: inline-block; margin-left: 6px; padding: 2px 7px; border-radius: 999px; font-size: 11px; background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); font-weight: 700;">오답 ${item.lapses}회</span>`
        : '';

      return `
        <tr data-id="${item.note_id}" style="border-bottom: 1px solid var(--border);">
          <td style="padding: 10px 14px; width: 40px; text-align: center;">
            <input type="checkbox" class="lm-row-cb" data-id="${item.note_id}" ${isChecked} style="cursor: pointer; width: 16px; height: 16px; accent-color: var(--accent);">
          </td>
          <td style="padding: 10px 14px; font-weight: 600; color: var(--text-primary); font-size: 14px;">
            ${escapeHtml(item.word)}
            ${lapseBadge}
          </td>
          <td style="padding: 10px 14px; width: 70px;">
            <span style="font-size: 11px; padding: 2px 6px; border-radius: 4px; background: var(--bg-surface-hover); color: var(--text-secondary);">${escapeHtml(item.pos || '-')}</span>
          </td>
          <td style="padding: 10px 14px; color: var(--text-secondary); font-size: 13px;">
            ${escapeHtml(item.meaning || '-')}
          </td>
          <td style="padding: 10px 14px; width: 120px; text-align: center;">
            <span style="display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; ${badgeStyle}">
              ${item.link_count}개 연결
            </span>
          </td>
        </tr>
      `;
    }).join('');

    // 행 클릭 및 체크박스 이벤트 바인딩
    listBody.querySelectorAll('.lm-row-cb').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const id = parseInt(e.target.getAttribute('data-id'));
        if (e.target.checked) state.selectedIds.add(id);
        else state.selectedIds.delete(id);
        updateSelectionUI();
      });
    });
  }

  function updateSelectionUI() {
    const countEl = document.getElementById('lm-selected-count');
    if (countEl) countEl.innerText = state.selectedIds.size;

    const btn = document.getElementById('lm-batch-gen-btn');
    if (btn) {
      btn.disabled = state.selectedIds.size === 0;
      btn.style.opacity = state.selectedIds.size === 0 ? '0.5' : '1';
    }

    // 체크박스 상태 동기화
    document.querySelectorAll('.lm-row-cb').forEach(cb => {
      const id = parseInt(cb.getAttribute('data-id'));
      cb.checked = state.selectedIds.has(id);
    });
  }

  async function scanAndRebuild() {
    const btn = document.getElementById('lm-scan-btn');
    if (!btn) return;
    const originText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" style="display:inline-block; width:14px; height:14px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; vertical-align:middle; margin-right:6px;"></span> 스캔 중...`;

    try {
      const res = await fetch('/api/links/scan', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "스캔 실패");

      alert(`✅ 스캔 완료!\n총 단어: ${data.data.total_vocab}개\n총 문장: ${data.data.total_sentences}개\n연결 완료: ${data.data.total_links}건\n(미연결 단어: ${data.data.unlinked_vocab_count}개)`);
      state.selectedIds.clear();
      await loadStats();
      await loadVocab();
    } catch (e) {
      alert("❌ 스캔 실패: " + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = originText;
    }
  }

  async function applyCardTemplates() {
    if (!confirm("Anki 카드의 뒷면에 연결 정보를 띄우는 스크립트를 적용하시겠습니까?\n\n* 혹시 모를 상황에 대비하여 현재 원본 템플릿은 data/template_backups/ 폴더에 안전하게 자동 백업됩니다.")) {
      return;
    }

    const btn = document.getElementById('lm-apply-template-btn');
    if (!btn) return;
    const originText = btn.innerHTML;
    btn.disabled = true;
    btn.innerText = "백업 및 적용 중...";

    try {
      const res = await fetch('/api/links/apply-templates', { method: 'POST' });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "적용 실패");

      alert(`✅ 성공!\n${data.message}\n백업 파일:\n${data.backup_file}`);
    } catch (e) {
      alert("❌ 템플릿 적용 실패: " + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = originText;
    }
  }

  async function executeBatchGeneration() {
    if (state.selectedIds.size === 0) return;

    const selectedWords = state.items.filter(item => state.selectedIds.has(item.note_id));
    const count = selectedWords.length;

    const genAudio = document.getElementById('lm-tts-option-cb')?.checked ?? true;

    if (!confirm(`선택한 ${count}개 단어로 Gemini AI 실생활 문장 카드를 일괄 생성하시겠습니까?\n\n- 생성된 문장은 Anki English Sentence 덱에 자동 등록됩니다.\n- 원어민 TTS 음성 생성: ${genAudio ? '켜짐' : '꺼짐'}`)) {
      return;
    }

    const btn = document.getElementById('lm-batch-gen-btn');
    const originText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner" style="display:inline-block; width:14px; height:14px; border:2px solid #fff; border-top-color:transparent; border-radius:50%; animation:spin 0.6s linear infinite; vertical-align:middle; margin-right:6px;"></span> AI 문장 생성 중 (${count}개)...`;

    try {
      const res = await fetch('/api/links/batch-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          words: selectedWords,
          generate_audio: genAudio
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "생성 실패");

      alert(`🎉 문장 ${data.created_count}개 일괄 생성 및 등록 완료!\n\n자동으로 Anki에 등록되고 링크가 연결되었습니다.`);
      state.selectedIds.clear();
      await loadStats();
      await loadVocab();
    } catch (e) {
      alert("❌ 생성 실패: " + e.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = originText;
    }
  }

  function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/[&<>"']/g, function(m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
  }

  return { init };
})();

document.addEventListener('DOMContentLoaded', () => {
  LinkManagerUI.init();
});
