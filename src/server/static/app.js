/* ================================================================
   Seattle Regulatory RAG -- Chat UI Client Logic
   ================================================================
   SSE streaming chat with Phase 4 wire format:
     event: status|sources|premise_flag|token|usage|session_id|done
     data: <payload>

   Confidence badges injected after [CITATION] chips. Clicking a chip
   expands the matching chunk in the sidebar.
   ================================================================ */

document.addEventListener('DOMContentLoaded', () => {

    // -- Section 1: DOM References ------------------------------------
    const chatArea          = document.getElementById('chatArea');
    const chatInput         = document.getElementById('chatInput');
    const sendBtn           = document.getElementById('sendBtn');
    const clearChat         = document.getElementById('clearChat');
    const welcome           = document.getElementById('welcome');

    const sourcesList       = document.getElementById('sourcesList');
    const relationshipPanel = document.getElementById('relationshipPanel');
    const rightSidebar      = document.getElementById('rightSidebar');

    const agencyFilterPanel = document.getElementById('agencyFilterPanel');
    const agencyCheckboxes  = document.getElementById('agencyCheckboxes');
    const applyAgencyFilter = document.getElementById('applyAgencyFilter');


    const docViewer         = document.getElementById('docViewer');
    const docViewerTitle    = document.getElementById('docViewerTitle');
    const docViewerClose    = document.getElementById('docViewerClose');
    const docViewerFrame    = document.getElementById('docViewerFrame');

    const auditToggle      = document.getElementById('auditToggle');
    const auditPanel       = document.getElementById('auditPanel');
    const auditPanelClose  = document.getElementById('auditPanelClose');
    const auditWaterfall   = document.getElementById('auditWaterfall');
    const auditTotalTime   = document.getElementById('auditTotalTime');

    const accessModalOverlay = document.getElementById('accessModalOverlay');

    // Two-step auth modal elements (D-21)
    const authStep1          = document.getElementById('authStep1');
    const accessKeyInput     = document.getElementById('accessKeyInput');
    const authStep1Error     = document.getElementById('authStep1Error');
    const accessKeySubmit    = document.getElementById('accessKeySubmit');

    const authStep2          = document.getElementById('authStep2');
    const registerName       = document.getElementById('registerName');
    const registerEmail      = document.getElementById('registerEmail');
    const registerBtn        = document.getElementById('registerBtn');
    const loginEmail         = document.getElementById('loginEmail');
    const loginBtn           = document.getElementById('loginBtn');
    const authStep2Error     = document.getElementById('authStep2Error');

    const authStepAudit      = document.getElementById('authStepAudit');
    const auditKeyInput      = document.getElementById('auditKeyInput');
    const authStepAuditError = document.getElementById('authStepAuditError');
    const auditKeySubmit     = document.getElementById('auditKeySubmit');

    // Conversation sidebar (D-22, D-23)
    const conversationSidebar = document.getElementById('conversationSidebar');
    const conversationList    = document.getElementById('conversationList');
    const newChatBtn          = document.getElementById('newChatBtn');
    const sidebarToggleBtn    = document.getElementById('sidebarToggleBtn');

    // -- Section 2: State Variables -----------------------------------
    let isStreaming = false;
    let sessionId = null;
    let currentConversationId = null;  // D-18: replaces sessionId for persistence
    let currentUser = null;            // D-07: { user_id, name, email } from JWT
    let currentSources = [];           // from latest sources event
    let agencyFilter = null;           // null = no filter (default)
    let premiseFlag = null;            // from premise_flag event
    let answerGenCounter = 0;          // tracks current answer generation (for stale response discard)
    let currentBubble = null;          // reference to the current assistant bubble

    let auditMode = false;             // whether audit panel is active

    // -- Section 2b: API Fetch Wrapper (D-07) --------------------------
    function apiFetch(url, options = {}) {
        const headers = { ...(options.headers || {}) };
        const accessKey = sessionStorage.getItem('chat_key');
        if (accessKey) headers['X-Access-Key'] = accessKey;
        const jwt = sessionStorage.getItem('jwt');
        if (jwt) headers['Authorization'] = 'Bearer ' + jwt;
        return fetch(url, { ...options, headers });
    }

    // -- Section 3: Configuration -------------------------------------
    const VALID_AGENCIES = [
        'WAC', 'RCW', 'SMC', 'Seattle DIR', 'IBC-WA',
        'SPU', 'WA Court Opinions', 'Governor Orders'
    ];

    const QUESTION_POOL = [
        'What are the setback requirements for single-family homes in Seattle?',
        'How does the WAC implement the Growth Management Act for comprehensive plans?',
        'What are the parking minimums for commercial buildings in Seattle?',
        'Can Seattle set stricter building energy codes than the state IBC?',
        'What permits does SPU require for side sewer connections?',
    ];

    // -- Section 3b: Two-Step Auth Flow (D-21, D-07) ------------------

    function showAuthModal(step) {
        // step: 'access' | 'identity' | 'audit'
        authStep1.style.display = step === 'access' ? 'block' : 'none';
        authStep2.style.display = step === 'identity' ? 'block' : 'none';
        authStepAudit.style.display = step === 'audit' ? 'block' : 'none';
        authStep1Error.style.display = 'none';
        authStep2Error.style.display = 'none';
        authStepAuditError.style.display = 'none';
        accessModalOverlay.style.display = 'flex';
        if (step === 'access') accessKeyInput.focus();
        else if (step === 'identity') registerName.focus();
        else if (step === 'audit') auditKeyInput.focus();
    }

    function hideAuthModal() {
        accessModalOverlay.style.display = 'none';
    }

    // Step 1: Team access key validation
    accessKeySubmit.addEventListener('click', async function() {
        var key = accessKeyInput.value.trim();
        if (!key) return;
        try {
            var resp = await fetch('/api/validate-key', {
                method: 'POST',
                headers: { 'X-Access-Key': key }
            });
            if (resp.ok) {
                sessionStorage.setItem('chat_key', key);
                var jwt = sessionStorage.getItem('jwt');
                if (jwt) {
                    var meResp = await apiFetch('/api/auth/me');
                    if (meResp.ok) {
                        currentUser = await meResp.json();
                        hideAuthModal();
                        onAuthComplete();
                        return;
                    }
                    sessionStorage.removeItem('jwt');
                }
                showAuthModal('identity');
            } else {
                authStep1Error.style.display = 'block';
            }
        } catch(e) {
            authStep1Error.style.display = 'block';
        }
    });

    accessKeyInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') accessKeySubmit.click();
    });

    // Step 2: Register
    registerBtn.addEventListener('click', async function() {
        var name = registerName.value.trim();
        var email = registerEmail.value.trim();
        if (!name || !email) return;
        authStep2Error.style.display = 'none';
        try {
            var resp = await apiFetch('/api/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, email: email }),
            });
            if (resp.ok) {
                var data = await resp.json();
                sessionStorage.setItem('jwt', data.token);
                currentUser = data.user;
                hideAuthModal();
                onAuthComplete();
            } else if (resp.status === 409) {
                var loginResp = await apiFetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email }),
                });
                if (loginResp.ok) {
                    var loginData = await loginResp.json();
                    sessionStorage.setItem('jwt', loginData.token);
                    currentUser = loginData.user;
                    hideAuthModal();
                    onAuthComplete();
                } else {
                    authStep2Error.textContent = 'Login failed. Try again.';
                    authStep2Error.style.display = 'block';
                }
            } else {
                authStep2Error.textContent = 'Registration failed. Try again.';
                authStep2Error.style.display = 'block';
            }
        } catch(e) {
            authStep2Error.textContent = 'Network error. Try again.';
            authStep2Error.style.display = 'block';
        }
    });

    registerEmail.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') registerBtn.click();
    });

    // Step 2: Login
    loginBtn.addEventListener('click', async function() {
        var email = loginEmail.value.trim();
        if (!email) return;
        authStep2Error.style.display = 'none';
        try {
            var resp = await apiFetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email: email }),
            });
            if (resp.ok) {
                var data = await resp.json();
                sessionStorage.setItem('jwt', data.token);
                currentUser = data.user;
                hideAuthModal();
                onAuthComplete();
            } else if (resp.status === 404) {
                authStep2Error.textContent = 'User not found. Register first.';
                authStep2Error.style.display = 'block';
            } else {
                authStep2Error.textContent = 'Login failed. Try again.';
                authStep2Error.style.display = 'block';
            }
        } catch(e) {
            authStep2Error.textContent = 'Network error. Try again.';
            authStep2Error.style.display = 'block';
        }
    });

    loginEmail.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') loginBtn.click();
    });

    // Audit key step
    auditKeySubmit.addEventListener('click', async function() {
        var key = auditKeyInput.value.trim();
        if (!key) return;
        try {
            var resp = await apiFetch('/api/validate-audit-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ audit_key: key }),
            });
            if (resp.ok) {
                sessionStorage.setItem('audit_key', key);
                hideAuthModal();
                openAuditPanel();
            } else {
                authStepAuditError.style.display = 'block';
            }
        } catch(e) {
            authStepAuditError.style.display = 'block';
        }
    });

    auditKeyInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') auditKeySubmit.click();
    });

    function onAuthComplete() {
        loadConversations();
        updateUserBadge();
        // Deferred audit check: only prompt for audit key after full auth
        checkAuditAvailable();
    }

    function updateUserBadge() {
        var existing = document.querySelector('.user-badge');
        if (existing) existing.remove();
        if (!currentUser) return;
        var badge = document.createElement('span');
        badge.className = 'user-badge';
        var dot = document.createElement('span');
        dot.className = 'user-badge-dot';
        badge.appendChild(dot);
        badge.appendChild(document.createTextNode(currentUser.name || currentUser.email));
        var headerActions = document.querySelector('.header-actions');
        if (headerActions) headerActions.prepend(badge);
    }

    // On page load: check existing auth state
    (async function initAuth() {
        var chatKey = sessionStorage.getItem('chat_key');
        var jwt = sessionStorage.getItem('jwt');
        if (!chatKey) {
            showAuthModal('access');
            return;
        }
        if (jwt) {
            try {
                var resp = await apiFetch('/api/auth/me');
                if (resp.ok) {
                    currentUser = await resp.json();
                    onAuthComplete();
                    return;
                }
            } catch(e) { /* fall through */ }
            sessionStorage.removeItem('jwt');
        }
        showAuthModal('identity');
    })();

    // Check if audit is available, auto-open if ?audit=true.
    // Only called from onAuthComplete() so chat_key is guaranteed set.
    async function checkAuditAvailable() {
        try {
            const resp = await apiFetch('/api/audit-check');
            const data = await resp.json();
            if (data.enabled && auditToggle) {
                auditToggle.style.display = '';
                if (new URLSearchParams(window.location.search).get('audit') === 'true') {
                    const auditKey = sessionStorage.getItem('audit_key');
                    if (auditKey) {
                        openAuditPanel();
                    } else {
                        showAuthModal('audit');
                    }
                }
            }
        } catch(e) { /* audit not available */ }
    }
    // NOTE: checkAuditAvailable() is now called from onAuthComplete() only,
    // so the audit modal never appears before team key auth is complete.

    // -- Section 3c: Audit Panel Toggle ----------------------------------
    function openAuditPanel() {
        auditMode = true;
        auditPanel.style.display = 'flex';
        document.querySelector('.app-layout').classList.add('audit-open');
    }

    function closeAuditPanel() {
        auditMode = false;
        auditPanel.style.display = 'none';
        document.querySelector('.app-layout').classList.remove('audit-open');
    }

    if (auditToggle) {
        auditToggle.addEventListener('click', function() {
            if (auditMode) {
                closeAuditPanel();
            } else {
                const auditKey = sessionStorage.getItem('audit_key');
                if (!auditKey) {
                    showAuthModal('audit');
                    return;
                }
                openAuditPanel();
            }
        });
    }

    if (auditPanelClose) {
        auditPanelClose.addEventListener('click', closeAuditPanel);
    }

    // -- Section 3.5: Citation chip -> sidebar expand ------------------
    // Delegated handler: clicking any [CITATION] chip in an answer expands
    // the matching sidebar item by simulating a click on its header (which
    // reuses the existing collapse-others / expand-this / load-relationships
    // logic at renderSourcesSidebar(...)).
    function expandSidebarItemForCitation(citation) {
        if (!citation || !sourcesList) return;
        const items = sourcesList.querySelectorAll('.sidebar-source-item');
        for (var i = 0; i < items.length; i++) {
            if ((items[i].dataset.citation || '') === citation) {
                items[i].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                if (!items[i].classList.contains('expanded')) {
                    var header = items[i].querySelector('.sidebar-source-header');
                    if (header) header.click();
                }
                return;
            }
        }
        // No match: hallucinated citation. Silent no-op.
    }

    if (chatArea) {
        chatArea.addEventListener('click', function(e) {
            var chip = e.target.closest('.citation-ref');
            if (!chip) return;
            expandSidebarItemForCitation(chip.dataset.citation || '');
        });
        chatArea.addEventListener('keydown', function(e) {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            var chip = e.target.closest('.citation-ref');
            if (!chip) return;
            e.preventDefault();
            expandSidebarItemForCitation(chip.dataset.citation || '');
        });
    }

    // -- Section 4: Sources Sidebar & Relationships --------------------

    function renderSourcesSidebar(sources) {
        if (!sources || sources.length === 0) {
            sourcesList.innerHTML = '<p class="sidebar-empty-state">No sources retrieved</p>';
            return;
        }

        const CHEVRON_SVG = '<svg class="sidebar-source-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>';

        sourcesList.innerHTML = '';
        sources.forEach(function(source, i) {
            const item = document.createElement('div');
            item.className = 'sidebar-source-item';
            item.dataset.chunkId = source.chunk_id || '';
            item.dataset.citation = source.citation || '';

            // Confidence ratio vs top source for badge color
            const maxScore = sources[0].score || 1;
            const ratio = maxScore > 0 ? (source.score || 0) / maxScore : 0;
            const confClass = ratio >= 0.7 ? 'confidence-high' : ratio >= 0.4 ? 'confidence-medium' : 'confidence-low';
            const confTitle = ratio >= 0.7 ? 'High' : ratio >= 0.4 ? 'Medium' : 'Low';

            const fullText = source.text_excerpt || '';
            const previewText = fullText.slice(0, 300);
            const hasMore = fullText.length > 300;

            var methodBadges = '';
            var srcs = source.retrieval_sources || [];
            if (srcs.indexOf('conflict_expand') !== -1) methodBadges += '<span class="source-method-badge method-conflict">C</span>';
            if (srcs.indexOf('graph_expand') !== -1) methodBadges += '<span class="source-method-badge method-graph-expand">G+</span>';
            ['vector','bm25','graph'].forEach(function(m) {
                if (srcs.indexOf(m) !== -1) methodBadges += '<span class="source-method-badge method-' + m + '">' + (m === 'vector' ? 'V' : m === 'bm25' ? 'B' : 'G') + '</span>';
            });

            item.innerHTML =
                '<div class="sidebar-source-header">' +
                    '<span class="sidebar-source-num">' + (i + 1) + '</span>' +
                    '<span class="sidebar-source-citation" title="' + escapeHtml(source.section_title || '') + '">' +
                        escapeHtml(source.citation || source.agency || 'Unknown') +
                    '</span>' +
                    '<span class="sidebar-source-badge">' + escapeHtml(source.agency || '') + '</span>' +
                    '<span class="confidence-pill ' + confClass + '" title="' + confTitle + ' confidence"></span>' +
                    methodBadges +
                    CHEVRON_SVG +
                '</div>' +
                '<div class="sidebar-source-excerpt" data-full-text="' + escapeHtml(fullText) + '">' +
                    escapeHtml(previewText) + (hasMore ? '...' : '') +
                '</div>' +
                '<div class="sidebar-source-actions">' +
                    '<button class="sidebar-source-view-btn" data-agency="' + escapeHtml(source.agency || '') + '" data-citation="' + escapeHtml(source.citation || '') + '">View chunk</button>' +
                '</div>';

            // Toggle expand/collapse on header click
            item.querySelector('.sidebar-source-header').addEventListener('click', function() {
                const wasExpanded = item.classList.contains('expanded');
                // Collapse all and reset excerpts to preview
                sourcesList.querySelectorAll('.sidebar-source-item.expanded').forEach(function(el) {
                    el.classList.remove('expanded');
                    var exc = el.querySelector('.sidebar-source-excerpt');
                    if (exc) {
                        var ft = exc.getAttribute('data-full-text') || '';
                        var pv = ft.slice(0, 300);
                        exc.textContent = ft.length > 300 ? pv + '...' : pv;
                    }
                });
                if (!wasExpanded) {
                    item.classList.add('expanded');
                    // Show full text
                    var excerptEl = item.querySelector('.sidebar-source-excerpt');
                    if (excerptEl) {
                        excerptEl.textContent = excerptEl.getAttribute('data-full-text') || '';
                    }
                    // Load relationships for this source
                    if (source.chunk_id) fetchRelationships(source.chunk_id);
                }
            });

            // "View chunk" button — show full text in alert
            item.querySelector('.sidebar-source-view-btn').addEventListener('click', function(e) {
                e.stopPropagation();
                alert('[' + (source.citation || source.agency) + ']\n\n' + (fullText || '(no text)'));
            });

            sourcesList.appendChild(item);
        });

        // Auto-expand first item, show full text, and load its relationships
        var first = sourcesList.querySelector('.sidebar-source-item');
        if (first) {
            first.classList.add('expanded');
            var excerptEl = first.querySelector('.sidebar-source-excerpt');
            if (excerptEl) {
                excerptEl.textContent = excerptEl.getAttribute('data-full-text') || '';
            }
        }
    }

    function fetchRelationships(chunkId) {
        if (!chunkId) return;
        relationshipPanel.innerHTML = '<p class="relationship-loading">Loading\u2026</p>';

        apiFetch('/api/relationships/' + encodeURIComponent(chunkId))
            .then(function(r) { return r.json(); })
            .then(function(data) {
                var groups = [
                    { key: 'cites',       label: 'Cites' },
                    { key: 'cited_by',    label: 'Cited by' },
                    { key: 'implements',  label: 'Implements' },
                    { key: 'subject_to',  label: 'Subject to' },
                ];
                var html = '';
                var hasAny = false;
                groups.forEach(function(g) {
                    var items = data[g.key] || [];
                    if (items.length === 0) return;
                    hasAny = true;
                    html += '<div class="relationship-group"><div class="relationship-group-title">' +
                        escapeHtml(g.label) + '</div>';
                    items.forEach(function(item) {
                        html += '<div class="relationship-item">' + escapeHtml(item.citation || item.chunk_id) + '</div>';
                    });
                    html += '</div>';
                });
                relationshipPanel.innerHTML = hasAny ? html : '<p class="sidebar-empty-state">No relationships found</p>';
            })
            .catch(function() {
                relationshipPanel.innerHTML = '<p class="sidebar-empty-state">Could not load relationships</p>';
            });
    }

    // -- Section 5: Agency Filter Setup (D-03) ------------------------
    const isDebug = new URLSearchParams(window.location.search).get('debug') === 'true';
    if (isDebug && agencyFilterPanel) {
        agencyFilterPanel.style.display = 'block';
        VALID_AGENCIES.forEach(agency => {
            const label = document.createElement('label');
            label.innerHTML = '<input type="checkbox" value="' + escapeHtml(agency) + '" checked> ' + escapeHtml(agency);
            agencyCheckboxes.appendChild(label);
        });
    }

    if (applyAgencyFilter) {
        applyAgencyFilter.addEventListener('click', () => {
            const checked = Array.from(agencyCheckboxes.querySelectorAll('input[type="checkbox"]:checked'))
                .map(cb => cb.value);
            // If all are checked, set to null (no filter)
            agencyFilter = (checked.length === VALID_AGENCIES.length) ? null : checked;
        });
    }

    // -- Section 5b: Conversation Sidebar (D-22, D-23) -----------------

    async function loadConversations() {
        if (!conversationList) return;
        conversationList.textContent = '';
        var loading = document.createElement('div');
        loading.className = 'conv-loading';
        loading.textContent = 'Loading...';
        conversationList.appendChild(loading);

        try {
            var resp = await apiFetch('/api/conversations');
            if (!resp.ok) {
                if (resp.status === 401) {
                    sessionStorage.removeItem('jwt');
                    showAuthModal('identity');
                    return;
                }
                throw new Error('Failed to load conversations');
            }
            var conversations = await resp.json();
            renderConversationList(conversations);
        } catch(e) {
            conversationList.textContent = '';
            var empty = document.createElement('div');
            empty.className = 'conv-empty-state';
            empty.textContent = 'Could not load conversations';
            conversationList.appendChild(empty);
        }
    }

    function renderConversationList(conversations) {
        conversationList.textContent = '';
        if (!conversations || conversations.length === 0) {
            var empty = document.createElement('div');
            empty.className = 'conv-empty-state';
            empty.textContent = 'No conversations yet. Start chatting!';
            conversationList.appendChild(empty);
            return;
        }

        // Group by date: Today, Yesterday, This Week, Older (D-23)
        var now = new Date();
        var todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        var yesterdayStart = new Date(todayStart.getTime() - 86400000);
        var weekStart = new Date(todayStart.getTime() - 6 * 86400000);

        var groups = { 'Today': [], 'Yesterday': [], 'This Week': [], 'Older': [] };

        conversations.forEach(function(conv) {
            var d = new Date(conv.updated_at);
            if (d >= todayStart) groups['Today'].push(conv);
            else if (d >= yesterdayStart) groups['Yesterday'].push(conv);
            else if (d >= weekStart) groups['This Week'].push(conv);
            else groups['Older'].push(conv);
        });

        var groupOrder = ['Today', 'Yesterday', 'This Week', 'Older'];
        groupOrder.forEach(function(groupName) {
            var items = groups[groupName];
            if (items.length === 0) return;

            var groupEl = document.createElement('div');
            groupEl.className = 'conv-date-group';

            var header = document.createElement('div');
            header.className = 'conv-date-header';
            header.textContent = groupName;
            groupEl.appendChild(header);

            items.forEach(function(conv) {
                var item = document.createElement('div');
                item.className = 'conv-item';
                if (conv.id === currentConversationId) item.classList.add('active');
                item.dataset.convId = conv.id;

                var titleEl = document.createElement('div');
                titleEl.className = 'conv-item-title';
                titleEl.textContent = conv.title || 'Untitled';
                item.appendChild(titleEl);

                var timeEl = document.createElement('div');
                timeEl.className = 'conv-item-time';
                timeEl.textContent = relativeTime(conv.updated_at);
                item.appendChild(timeEl);

                var deleteBtn = document.createElement('button');
                deleteBtn.className = 'conv-item-delete';
                deleteBtn.textContent = '\u00d7';
                deleteBtn.title = 'Delete conversation';
                deleteBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    deleteConversation(conv.id);
                });
                item.appendChild(deleteBtn);

                item.addEventListener('click', function() {
                    loadConversation(conv.id);
                });

                groupEl.appendChild(item);
            });

            conversationList.appendChild(groupEl);
        });
    }

    async function loadConversation(convId) {
        currentConversationId = convId;
        // Clear chat area
        chatArea.querySelectorAll('.message').forEach(function(msg) { msg.remove(); });
        welcome.style.display = 'none';
        currentSources = [];
        premiseFlag = null;
        currentBubble = null;

        // Update active state in sidebar
        conversationList.querySelectorAll('.conv-item').forEach(function(el) {
            el.classList.toggle('active', el.dataset.convId === convId);
        });

        try {
            var resp = await apiFetch('/api/conversations/' + encodeURIComponent(convId));
            if (!resp.ok) throw new Error('Failed to load conversation');
            var data = await resp.json();

            // Render each message
            var msgs = data.messages || [];
            msgs.forEach(function(msg) {
                if (msg.role === 'user') {
                    addUserMessage(msg.content);
                } else if (msg.role === 'assistant') {
                    renderHistoricalAssistantMessage(msg);
                }
            });

            // Restore sources from last assistant message with sources
            for (var i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].role === 'assistant' && msgs[i].sources_json) {
                    try {
                        var restoredSources = JSON.parse(msgs[i].sources_json);
                        if (restoredSources && restoredSources.length > 0) {
                            currentSources = restoredSources;
                            renderSourcesSidebar(restoredSources);
                        }
                    } catch(e) {}
                    break;
                }
            }

            scrollToBottom();
        } catch(e) {
            var errorDiv = document.createElement('div');
            errorDiv.className = 'message message-assistant';
            var bubble = document.createElement('div');
            bubble.className = 'message-bubble error-message';
            bubble.textContent = 'Failed to load conversation.';
            errorDiv.appendChild(bubble);
            chatArea.appendChild(errorDiv);
        }
    }

    function renderHistoricalAssistantMessage(msg) {
        var msgEl = document.createElement('div');
        msgEl.className = 'message message-assistant';

        var avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = 'AI';

        var contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        var bubble = document.createElement('div');
        bubble.className = 'message-bubble reveal';

        // Parse markdown safely using DOMPurify
        var rawHtml = '';
        try {
            rawHtml = marked.parse(msg.content || '', { breaks: true });
        } catch(e) {
            rawHtml = escapeHtml(msg.content || '');
        }
        bubble.innerHTML = DOMPurify.sanitize(rawHtml);

        contentDiv.appendChild(bubble);

        // Add pipeline icon for trace replay (D-25)
        if (msg.trace_id) {
            var actions = document.createElement('div');
            actions.className = 'message-actions';
            var pipelineBtn = document.createElement('button');
            pipelineBtn.className = 'pipeline-icon-btn';
            pipelineBtn.title = 'View pipeline trace';
            pipelineBtn.dataset.messageId = msg.id || '';
            var svgNs = 'http://www.w3.org/2000/svg';
            var svg = document.createElementNS(svgNs, 'svg');
            svg.setAttribute('width', '12');
            svg.setAttribute('height', '12');
            svg.setAttribute('viewBox', '0 0 24 24');
            svg.setAttribute('fill', 'none');
            svg.setAttribute('stroke', 'currentColor');
            svg.setAttribute('stroke-width', '2');
            var path = document.createElementNS(svgNs, 'path');
            path.setAttribute('d', 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2');
            svg.appendChild(path);
            var check = document.createElementNS(svgNs, 'path');
            check.setAttribute('d', 'M9 14l2 2 4-4');
            svg.appendChild(check);
            pipelineBtn.appendChild(svg);
            pipelineBtn.appendChild(document.createTextNode(' Trace'));
            pipelineBtn.addEventListener('click', function() {
                // Restore this message's sources in the sidebar
                if (msg.sources_json) {
                    try {
                        var msgSources = JSON.parse(msg.sources_json);
                        if (msgSources && msgSources.length > 0) {
                            currentSources = msgSources;
                            renderSourcesSidebar(msgSources);
                        }
                    } catch(e) {}
                }
                loadTraceForMessage(msg.id);
            });
            actions.appendChild(pipelineBtn);
            contentDiv.appendChild(actions);
        }

        msgEl.appendChild(avatar);
        msgEl.appendChild(contentDiv);
        chatArea.appendChild(msgEl);
    }

    async function loadTraceForMessage(messageId) {
        if (!messageId) return;
        try {
            // Open audit panel if not already open
            if (!auditMode) openAuditPanel();
            var resp = await apiFetch('/api/messages/' + encodeURIComponent(messageId) + '/trace');
            if (!resp.ok) throw new Error('Failed to load trace');
            var traceData = await resp.json();
            if (window.AuditPanel && window.AuditPanel.replayTrace) {
                window.AuditPanel.replayTrace(traceData);
            }
        } catch(e) {
            // Show error in audit panel
            if (window.AuditPanel) {
                window.AuditPanel.reset();
                var wf = document.getElementById('auditWaterfall');
                if (wf) {
                    var errEl = document.createElement('div');
                    errEl.className = 'audit-historical-header';
                    errEl.textContent = 'Trace not available for this message';
                    wf.appendChild(errEl);
                }
            }
        }
    }

    async function deleteConversation(convId) {
        try {
            var resp = await apiFetch('/api/conversations/' + encodeURIComponent(convId), {
                method: 'DELETE'
            });
            if (resp.ok) {
                if (currentConversationId === convId) {
                    currentConversationId = null;
                    clearConversation();
                }
                loadConversations();
            }
        } catch(e) { /* ignore */ }
    }

    // Build and append a pipeline trace button into a container.
    // Returns the button element. If msgId is provided, wires up the click handler immediately.
    function addTraceButton(container, msgId) {
        var btn = document.createElement('button');
        btn.className = 'pipeline-icon-btn';
        btn.title = 'View pipeline trace';
        var svgNs = 'http://www.w3.org/2000/svg';
        var svg = document.createElementNS(svgNs, 'svg');
        svg.setAttribute('width', '12'); svg.setAttribute('height', '12');
        svg.setAttribute('viewBox', '0 0 24 24'); svg.setAttribute('fill', 'none');
        svg.setAttribute('stroke', 'currentColor'); svg.setAttribute('stroke-width', '2');
        var p1 = document.createElementNS(svgNs, 'path');
        p1.setAttribute('d', 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2');
        svg.appendChild(p1);
        var p2 = document.createElementNS(svgNs, 'path');
        p2.setAttribute('d', 'M9 14l2 2 4-4');
        svg.appendChild(p2);
        btn.appendChild(svg);
        btn.appendChild(document.createTextNode(' Trace'));
        if (msgId) {
            btn.addEventListener('click', function() { loadTraceForMessage(msgId); });
        }
        container.appendChild(btn);
        return btn;
    }

    function handleConversationEvent(data) {
        // D-19: Update currentConversationId from server event
        try {
            var parsed = typeof data === 'string' ? JSON.parse(data) : data;
            if (parsed.conversation_id) {
                currentConversationId = parsed.conversation_id;
            }
            // Wire up or add trace button with message_id (D-25)
            if (parsed.message_id) {
                // Primary: use currentBubble's parent. Fallback: last assistant message-content in DOM.
                var contentDiv = currentBubble ? currentBubble.parentElement : null;
                if (!contentDiv) {
                    var msgs = chatArea.querySelectorAll('.message-assistant .message-content');
                    if (msgs.length > 0) contentDiv = msgs[msgs.length - 1];
                }
                if (contentDiv) {
                    var existingActions = contentDiv.querySelector('.message-actions');
                    if (existingActions) {
                        // Placeholder button was added on 'done' — enable and wire up click handler
                        var existingBtn = existingActions.querySelector('.pipeline-icon-btn');
                        if (existingBtn && existingBtn.disabled) {
                            existingBtn.disabled = false;
                            (function(msgId) {
                                existingBtn.addEventListener('click', function() { loadTraceForMessage(msgId); });
                            })(parsed.message_id);
                        }
                    } else {
                        // Placeholder wasn't created (e.g., not in audit mode) — add full button now
                        var actions = document.createElement('div');
                        actions.className = 'message-actions';
                        addTraceButton(actions, parsed.message_id);
                        contentDiv.appendChild(actions);
                    }
                }
            }
            // Refresh sidebar to show new/updated conversation
            loadConversations();
        } catch(e) {
            console.error('handleConversationEvent error:', e, data);
        }
    }

    function startNewChat() {
        currentConversationId = null;
        clearConversation();
        // Deselect active item in sidebar
        conversationList.querySelectorAll('.conv-item.active').forEach(function(el) {
            el.classList.remove('active');
        });
    }

    // Sidebar toggle (single button in header)
    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener('click', function() {
            var collapsed = conversationSidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebar_collapsed', collapsed ? '1' : '0');
        });
    }
    // Restore collapse state across sessions
    if (localStorage.getItem('sidebar_collapsed') === '1') {
        conversationSidebar.classList.add('collapsed');
    }

    if (newChatBtn) {
        newChatBtn.addEventListener('click', startNewChat);
    }

    // -- Section 6: Core SSE Streaming Function -----------------------

    async function streamChat(query) {
        const genId = ++answerGenCounter;  // for stale response detection

        // Reset state
        currentSources = [];
        premiseFlag = null;

        // Clear sidebar panels for new query
        sourcesList.innerHTML = '<p class="sidebar-empty-state">Loading sources...</p>';
        relationshipPanel.innerHTML = '<p class="sidebar-empty-state">No relationships found</p>';

        // Reset audit panel
        if (window.AuditPanel) window.AuditPanel.reset();

        // Build request body (D-18: conversation_id replaces session_id for persistence)
        const body = { query: query };
        if (sessionId) body.session_id = sessionId;
        if (currentConversationId) body.conversation_id = currentConversationId;
        if (agencyFilter) body.agency_filter = agencyFilter;
        if (auditMode) {
            body.audit_mode = true;
            body.audit_key = sessionStorage.getItem('audit_key') || '';
        }

        const response = await apiFetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            throw new Error('Server error: ' + response.status);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = 'message';
        let tokenBuffer = '';  // accumulate all token data

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('event: ')) {
                    currentEvent = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    const rawData = line.slice(6);
                    // Token data is JSON-encoded in app.py to preserve embedded
                    // newlines across SSE framing. Decode here; all other event
                    // types are plain text or already-serialized JSON sent raw.
                    let data;
                    if (currentEvent === 'token') {
                        try { data = JSON.parse(rawData); } catch(e) { data = rawData; }
                    } else {
                        data = rawData;
                    }
                    if (genId !== answerGenCounter) return;  // stale

                    // CRITICAL: accumulate token data BEFORE calling handler
                    // so handleSSEEvent (and revealFinalAnswer on 'done') sees
                    // the complete buffer including the current token.
                    if (currentEvent === 'token') {
                        tokenBuffer += data;
                    }
                    handleSSEEvent(currentEvent, data, tokenBuffer, genId);
                    currentEvent = 'message';  // reset to default after data line
                }
            }
        }

        // Handle any remaining buffer
        if (buffer.trim()) {
            if (buffer.startsWith('event: ')) {
                currentEvent = buffer.slice(7).trim();
            } else if (buffer.startsWith('data: ')) {
                const rawData = buffer.slice(6);
                let data;
                if (currentEvent === 'token') {
                    try { data = JSON.parse(rawData); } catch(e) { data = rawData; }
                } else {
                    data = rawData;
                }
                if (currentEvent === 'token') {
                    tokenBuffer += data;
                }
                handleSSEEvent(currentEvent, data, tokenBuffer, genId);
            }
        }

        return tokenBuffer;
    }

    // -- Section 7: SSE Event Handler ---------------------------------

    function handleSSEEvent(eventType, data, tokenBuffer, genId) {
        switch (eventType) {
            case 'status':
                updateThinkingLabel(data);
                break;
            case 'sources':
                currentSources = JSON.parse(data);
                renderSourcesSidebar(currentSources);
                break;
            case 'premise_flag':
                premiseFlag = JSON.parse(data);
                break;
            case 'token':
                // tokenBuffer already includes this token (accumulated by caller before this call)
                updateStreamingPreview(tokenBuffer);
                break;
            case 'usage':
                // Store for debug display if needed
                if (window.AuditPanel) window.AuditPanel.handleEvent('usage', data);
                break;
            case 'session_id':
                sessionId = data.trim();
                break;
            case 'conversation':
                handleConversationEvent(data);
                break;
            case 'audit_classify':
            case 'audit_premise':
            case 'audit_decompose':
            case 'audit_retrieve':
            case 'audit_rerank':
            case 'audit_graph_expand':
            case 'audit_conflict_expand':
            case 'audit_budget':
            case 'audit_synthesis_context':
            case 'audit_llm_io':
            case 'audit_error':
                if (window.AuditPanel) {
                    window.AuditPanel.handleEvent(eventType, data);
                }
                break;
            case 'done':
                if (window.AuditPanel) window.AuditPanel.handleEvent('done', data);
                revealFinalAnswer(tokenBuffer, genId);
                // Add placeholder trace button immediately so it's visible when audit panel opens.
                // Click handler + enable wired in handleConversationEvent when message_id arrives.
                if (currentBubble) {
                    var _contentDiv = currentBubble.parentElement;
                    if (_contentDiv && !_contentDiv.querySelector('.message-actions')) {
                        var _actions = document.createElement('div');
                        _actions.className = 'message-actions';
                        var _btn = addTraceButton(_actions, null);
                        _btn.disabled = true;
                        _contentDiv.appendChild(_actions);
                    }
                }
                break;
        }
    }

    // -- Section 8: Message Rendering ---------------------------------

    function addUserMessage(text) {
        const msg = document.createElement('div');
        msg.className = 'message message-user';

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = 'U';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = escapeHtml(text);

        contentDiv.appendChild(bubble);
        msg.appendChild(avatar);
        msg.appendChild(contentDiv);
        chatArea.appendChild(msg);
        scrollToBottom();
    }

    function createAssistantBubble() {
        const msg = document.createElement('div');
        msg.className = 'message message-assistant';

        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = 'AI';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = thinkingHTML();

        // Start elapsed timer
        const startTime = Date.now();
        const thinkingTimer = setInterval(() => {
            const el = bubble.querySelector('.thinking-elapsed');
            if (el) {
                const secs = Math.floor((Date.now() - startTime) / 1000);
                el.textContent = secs + 's';
            }
        }, 1000);
        bubble.dataset.thinkingTimer = thinkingTimer;

        // Streaming preview toggle
        const streamingPreview = bubble.querySelector('.streaming-preview');
        const expandBtn = bubble.querySelector('.thinking-expand-btn');
        if (expandBtn && streamingPreview) {
            let isPreviewOpen = false;
            expandBtn.addEventListener('click', () => {
                isPreviewOpen = !isPreviewOpen;
                streamingPreview.classList.toggle('open', isPreviewOpen);
                expandBtn.classList.toggle('rotated', isPreviewOpen);
            });
        }

        contentDiv.appendChild(bubble);
        msg.appendChild(avatar);
        msg.appendChild(contentDiv);
        chatArea.appendChild(msg);
        scrollToBottom();

        currentBubble = bubble;
        return bubble;
    }

    function updateThinkingLabel(text) {
        if (!currentBubble) return;
        const label = currentBubble.querySelector('.thinking-label');
        if (label) {
            label.textContent = text;
        }
    }

    function updateStreamingPreview(text) {
        if (!currentBubble) return;
        const preview = currentBubble.querySelector('.streaming-preview');
        if (preview && preview.classList.contains('open')) {
            preview.textContent = text;
            preview.scrollTop = preview.scrollHeight;
        }
    }

    function revealFinalAnswer(fullText, genId) {
        if (!currentBubble) return;
        if (genId !== answerGenCounter) return;  // stale

        // Clear thinking timer
        const timerId = currentBubble.dataset.thinkingTimer;
        if (timerId) clearInterval(parseInt(timerId));

        // Parse markdown
        let html = DOMPurify.sanitize(marked.parse(fullText, { breaks: true }));

        // Inject citation-ref spans: [CITATION] -> styled, clickable chip.
        // Anchored on agency prefix so the regex doesn't eat markdown links
        // ([click here](url)) or footnote markers ([1]).
        html = html.replace(
            /\[((?:SMC|RCW|WAC|DIR|DR|IBC-WA|SPU|EO|Court|No\.|State\s+v\.)[^\[\]]*)\]/g,
            '<span class="citation-ref" data-citation="$1" role="button" tabindex="0" title="Show source chunk">$1</span>'
        );

        // Inject confidence badges
        html = injectConfidenceBadges(html, currentSources);

        // If premise flag, prepend warning banner
        if (premiseFlag) {
            const warning = createPremiseWarning(premiseFlag);
            currentBubble.innerHTML = '';
            currentBubble.appendChild(warning);
            const answerDiv = document.createElement('div');
            answerDiv.innerHTML = html;
            currentBubble.appendChild(answerDiv);
        } else {
            currentBubble.innerHTML = html;
        }

        // Enhance source blockquotes
        enhanceSourceQuotes(currentBubble);

        // Reveal animation
        void currentBubble.offsetWidth;  // force reflow
        currentBubble.classList.add('reveal');

        // Auto-populate relationship panel with first source
        if (currentSources.length > 0 && currentSources[0].chunk_id) {
            fetchRelationships(currentSources[0].chunk_id);
        }

        // Re-enable send
        isStreaming = false;
        sendBtn.disabled = false;

        scrollToBottom();
    }

    function renderMarkdown(text) {
        if (!text) return '';
        try {
            const rawHtml = marked.parse(text, { breaks: true });
            return DOMPurify.sanitize(rawHtml);
        } catch (e) {
            return escapeHtml(text);
        }
    }

    function enhanceSourceQuotes(bubbleEl) {
        bubbleEl.querySelectorAll('blockquote').forEach(bq => {
            const citRef = bq.querySelector('.citation-ref');
            if (citRef) {
                const label = document.createElement('span');
                label.className = 'source-quote-label';
                label.textContent = '\u21B3 ' + citRef.textContent.trim() + ' \u2014 verbatim';
                bq.insertBefore(label, bq.firstChild);
                citRef.style.display = 'none';
            }
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // -- Section 9: Confidence Badge Injection (D-02, UI-06) ----------

    function injectConfidenceBadges(html, sources) {
        return html;
    }

    // -- Section 10: Premise Warning Banner ---------------------------

    function createPremiseWarning(premiseData) {
        const div = document.createElement('div');
        div.className = 'premise-warning visible';
        div.innerHTML =
            '<div class="premise-warning-heading">PREMISE MAY BE INCORRECT</div>' +
            '<p>' + escapeHtml(premiseData.premise) + ' &mdash; ' + escapeHtml(premiseData.correction) + '</p>';
        return div;
    }

    // -- Section 11: Send Message Handler -----------------------------

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text || isStreaming) return;

        isStreaming = true;
        sendBtn.disabled = true;
        welcome.style.display = 'none';

        addUserMessage(text);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        const bubble = createAssistantBubble();

        try {
            await streamChat(text);
        } catch (err) {
            // Clear thinking timer on error
            const timerId = bubble.dataset.thinkingTimer;
            if (timerId) clearInterval(parseInt(timerId));
            bubble.innerHTML = '<div class="error-message">' + escapeHtml(err.message || 'Connection error. Check that the server is running and try again.') + '</div>';
            bubble.classList.add('reveal');
        } finally {
            isStreaming = false;
            sendBtn.disabled = false;
            chatInput.focus();
        }
    }

    // -- Section 12: Utility Functions --------------------------------

    // Input auto-resize
    function autoResize() {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 150) + 'px';
    }

    // Chat auto-scroll
    function scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    // Thinking indicator HTML
    function thinkingHTML() {
        return '<div class="thinking-wrapper">' +
            '<div class="thinking-status">' +
                '<div class="thinking-dots">' +
                    '<div class="typing-dot"></div>' +
                    '<div class="typing-dot"></div>' +
                    '<div class="typing-dot"></div>' +
                '</div>' +
                '<span class="thinking-label">Searching corpus</span>' +
                '<span class="thinking-elapsed">0s</span>' +
                '<button class="thinking-expand-btn" title="Preview response as it streams">' +
                    '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">' +
                        '<path d="M6 9l6 6 6-6"/>' +
                    '</svg>' +
                    ' Live' +
                '</button>' +
            '</div>' +
            '<div class="streaming-preview"></div>' +
        '</div>';
    }

    // Example queries
    function populateExamples() {
        const container = document.querySelector('.example-queries');
        if (!container) return;

        // Shuffle and pick 4
        const shuffled = QUESTION_POOL.slice().sort(function() { return 0.5 - Math.random(); });
        var selected = shuffled.slice(0, 4);

        container.innerHTML = '';
        selected.forEach(function(q) {
            var btn = document.createElement('button');
            btn.className = 'example-query';
            btn.textContent = q;
            btn.addEventListener('click', function() {
                chatInput.value = q;
                sendBtn.disabled = false;
                autoResize();
                sendMessage();
            });
            container.appendChild(btn);
        });
    }

    // Clear conversation
    function clearConversation() {
        chatArea.querySelectorAll('.message').forEach(function(msg) { msg.remove(); });
        welcome.style.display = 'flex';
        sessionId = null;
        currentConversationId = null;
        currentSources = [];
        premiseFlag = null;
        currentBubble = null;
        sourcesList.innerHTML = '<p class="sidebar-empty-state">No sources retrieved</p>';
        relationshipPanel.innerHTML = '<p class="sidebar-empty-state">No relationships found</p>';
        populateExamples();
    }

    // -- Section 12b: Utility Helpers ---------------------------------

    function relativeTime(iso) {
        var diff = Date.now() - new Date(iso).getTime();
        var m = Math.floor(diff / 60000);
        var h = Math.floor(diff / 3600000);
        var d = Math.floor(diff / 86400000);
        if (m < 1)  return 'just now';
        if (m < 60) return m + 'm ago';
        if (h < 24) return h + 'h ago';
        if (d < 7)  return d + 'd ago';
        return new Date(iso).toLocaleDateString();
    }

    // -- Document Viewer ----------------------------------------------

    function openDocumentViewer(library, filename, page) {
        var url = '/api/documents/' + encodeURIComponent(library) + '/' + encodeURIComponent(filename) + '#page=' + page + '&toolbar=0';
        docViewerFrame.src = 'about:blank';
        requestAnimationFrame(function() { docViewerFrame.src = url; });
        docViewerTitle.textContent = filename + ' \u2014 p.' + page;
        document.body.classList.add('doc-viewer-open');
    }

    function closeDocumentViewer() {
        document.body.classList.remove('doc-viewer-open');
        docViewerFrame.src = '';
    }

    // -- Section 13: Initialization -----------------------------------

    chatInput.focus();
    populateExamples();

    // Send button
    sendBtn.addEventListener('click', sendMessage);

    // Enter to send, Shift+Enter for newline
    chatInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // Enable/disable send button based on input
    chatInput.addEventListener('input', function() {
        sendBtn.disabled = !chatInput.value.trim() || isStreaming;
        autoResize();
    });

    // Clear conversation
    clearChat.addEventListener('click', clearConversation);

    // Document viewer close
    docViewerClose.addEventListener('click', closeDocumentViewer);
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && document.body.classList.contains('doc-viewer-open')) {
            closeDocumentViewer();
        }
    });

});
