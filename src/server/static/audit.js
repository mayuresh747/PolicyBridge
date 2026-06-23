/* ================================================================
   Seattle Regulatory RAG -- Pipeline Audit Panel
   ================================================================
   SSE consumer for /api/audit-chat with waterfall card renderer.
   Handles 5 audit event types + token streaming + decomposition tree.

   Event types consumed:
     audit_classify, audit_premise, audit_decompose,
     audit_retrieve, audit_llm_io,
     token, sources, status, usage, session_id, done
   ================================================================ */

// -- DOM References --------------------------------------------------
const auditInput          = document.getElementById('auditInput');
const auditSendBtn        = document.getElementById('auditSendBtn');
const auditWaterfall      = document.getElementById('auditWaterfall');
const auditAnswer         = document.getElementById('auditAnswer');
const auditAnswerContent  = document.getElementById('auditAnswerContent');
const auditPlaceholder    = document.getElementById('auditPlaceholder');
const auditTotalTime      = document.getElementById('auditTotalTime');
const auditSidebar        = document.getElementById('auditSidebar');
const auditSidebarToggle  = document.getElementById('auditSidebarToggle');
const auditSourcesList    = document.getElementById('auditSourcesList');
const auditRelPanel       = document.getElementById('auditRelationshipPanel');

// -- State -----------------------------------------------------------
let isRunning = false;
let totalElapsedMs = 0;
let answerBuffer = '';          // accumulates raw token text
let hasDecomposeCard = false;   // tracks whether a decompose card was emitted
let sidebarVisible = false;     // tracks sidebar open/close state

// -- Event Listeners -------------------------------------------------
auditSendBtn.addEventListener('click', function () { runAudit(); });

auditSidebarToggle.addEventListener('click', function () {
    sidebarVisible = !sidebarVisible;
    auditSidebar.style.display = sidebarVisible ? 'flex' : 'none';
    auditSidebarToggle.textContent = sidebarVisible ? 'Sources ✕' : 'Sources';
});

auditInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        runAudit();
    }
});

// -- Main Audit Runner -----------------------------------------------

async function runAudit() {
    const query = auditInput.value.trim();
    if (!query || isRunning) return;

    // Lock UI
    isRunning = true;
    auditSendBtn.disabled = true;
    auditSendBtn.textContent = 'Running...';

    // Reset state
    totalElapsedMs = 0;
    answerBuffer = '';
    hasDecomposeCard = false;
    sidebarVisible = false;

    // Clear previous results
    auditWaterfall.innerHTML = '';
    auditTotalTime.textContent = '';
    auditAnswer.innerHTML = '';
    auditAnswerContent.style.display = 'none';
    auditPlaceholder.style.display = 'block';
    auditSidebar.style.display = 'none';
    auditSidebarToggle.style.display = 'none';
    auditSidebarToggle.textContent = 'Sources';
    auditSourcesList.innerHTML = '';
    auditRelPanel.innerHTML = '<p class="sidebar-empty-state" style="padding:12px 16px;">Click a source to view relationships</p>';

    try {
        const response = await fetch('/api/audit-chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });

        if (!response.ok) {
            throw new Error('Server error: ' + response.status);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = 'message';

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
                    const data = line.slice(6);
                    handleAuditEvent(currentEvent, data);
                    currentEvent = 'message';
                }
            }
        }

        // Handle any remaining buffer
        if (buffer.trim()) {
            if (buffer.startsWith('event: ')) {
                currentEvent = buffer.slice(7).trim();
            } else if (buffer.startsWith('data: ')) {
                const data = buffer.slice(6);
                handleAuditEvent(currentEvent, data);
            }
        }
    } catch (err) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'audit-card';
        errorDiv.innerHTML = '<div class="audit-card-header">' +
            '<span class="audit-card-label" style="color:var(--error)">Error</span>' +
            '<span class="audit-card-summary">' + escapeHtml(err.message) + '</span>' +
            '</div>';
        auditWaterfall.appendChild(errorDiv);
    } finally {
        finalizeAudit();
    }
}

// -- SSE Event Handler -----------------------------------------------

function handleAuditEvent(eventType, data) {
    switch (eventType) {
        case 'audit_classify':
            addWaterfallCard('classify', JSON.parse(data));
            break;
        case 'audit_premise':
            addWaterfallCard('premise', JSON.parse(data));
            break;
        case 'audit_decompose':
            addWaterfallCard('decompose', JSON.parse(data));
            renderDecompositionTree(JSON.parse(data));
            break;
        case 'audit_retrieve':
            addWaterfallCard('retrieve', JSON.parse(data));
            break;
        case 'audit_llm_io':
            addWaterfallCard('llm_io', JSON.parse(data));
            break;
        case 'audit_synthesis_context':
            addSynthesisContextCard(JSON.parse(data));
            break;
        case 'token':
            appendToken(JSON.parse(data));
            break;
        case 'sources':
            renderAuditSources(JSON.parse(data));
            break;
        case 'status':
            // Could show a subtle status indicator; no-op for now
            break;
        case 'usage':
            // Usage data could augment llm_io card; no-op for now
            break;
        case 'done':
            // finalizeAudit() is called from the finally block
            break;
        default:
            // Ignore unknown events (session_id, etc.)
            break;
    }
}

// -- Waterfall Card Renderer -----------------------------------------

function getRetrieveNum() {
    return hasDecomposeCard ? 4 : 3;
}

function getLlmIoNum() {
    return getRetrieveNum() + 2; // +1 for synthesis context, +1 for LLM I/O
}

function addWaterfallCard(stage, payload) {
    const card = document.createElement('div');
    card.className = 'audit-card audit-card-' + stage;
    card.dataset.stage = stage;

    // Track decompose presence
    if (stage === 'decompose') {
        hasDecomposeCard = true;
    }

    var stageConfig = {
        classify:  { num: 1, label: 'Classification', icon: 'C' },
        premise:   { num: 2, label: 'Premise Check',  icon: 'P' },
        decompose: { num: 3, label: 'Decomposition',  icon: 'D' },
        retrieve:  { num: getRetrieveNum(), label: 'Retrieval', icon: 'R' },
        llm_io:    { num: getLlmIoNum(),    label: 'LLM I/O',   icon: 'L' }
    };
    var cfg = stageConfig[stage];
    var summary = buildSummaryLine(stage, payload);
    var elapsedMs = payload.elapsed_ms != null ? Math.round(payload.elapsed_ms) + 'ms' : '';

    totalElapsedMs += (payload.elapsed_ms || 0);

    // Add premise-warning class for false premise
    if (stage === 'premise' && payload.output && payload.output.verdict === 'false_premise') {
        card.classList.add('premise-warning');
    }

    card.innerHTML =
        '<div class="audit-card-header">' +
            '<span class="audit-card-num">' + cfg.num + '</span>' +
            '<span class="audit-card-label">' + cfg.label + '</span>' +
            '<span class="audit-card-summary">' + summary + '</span>' +
            '<span class="audit-card-elapsed">' + elapsedMs + '</span>' +
        '</div>' +
        '<details class="audit-card-details">' +
            '<summary>View payload</summary>' +
            '<pre class="audit-json">' + escapeHtml(JSON.stringify(payload, null, 2)) + '</pre>' +
        '</details>';

    // Animate in
    card.style.opacity = '0';
    card.style.transform = 'translateY(8px)';
    auditWaterfall.appendChild(card);
    requestAnimationFrame(function () {
        card.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
    });

    // Per-leaf breakdown for L3+ retrieve cards
    if (stage === 'retrieve' && payload.output && payload.output.per_leaf && payload.output.per_leaf.length > 0) {
        var details = card.querySelector('.audit-card-details');
        var leafSection = document.createElement('div');
        leafSection.className = 'audit-per-leaf-section';
        var leafHtml = '<div class="audit-per-leaf-heading">Per-Leaf Breakdown</div>';
        payload.output.per_leaf.forEach(function(leaf, idx) {
            var methods = leaf.methods || {};
            leafHtml +=
                '<div class="audit-per-leaf-item">' +
                    '<div class="audit-per-leaf-query">' +
                        '<span class="audit-per-leaf-num">L' + (idx+1) + '</span>' +
                        escapeHtml(leaf.leaf_query || '') +
                    '</div>' +
                    '<div class="audit-per-leaf-stats">' +
                        '<span>' + (leaf.chunk_count || 0) + ' chunks</span>' +
                        '<span class="source-method-badge method-vector">V:' + (methods.vector || 0) + '</span>' +
                        '<span class="source-method-badge method-bm25">B:' + (methods.bm25 || 0) + '</span>' +
                        '<span class="source-method-badge method-graph">G:' + (methods.graph || 0) + '</span>' +
                    '</div>' +
                '</div>';
        });
        leafSection.innerHTML = leafHtml;
        // Insert before the JSON pre block
        var preBlock = details.querySelector('.audit-json');
        if (preBlock) {
            details.insertBefore(leafSection, preBlock);
        } else {
            details.appendChild(leafSection);
        }
    }
}

// -- Summary Line Builder --------------------------------------------

function buildSummaryLine(stage, payload) {
    switch (stage) {
        case 'classify':
            return escapeHtml(payload.output.level) + ' — ' +
                   escapeHtml(payload.output.reasoning || '');

        case 'premise':
            if (payload.output.verdict === 'false_premise') {
                return '&#9888; False premise: "' +
                       escapeHtml(payload.output.premise || '') + '"';
            }
            if (payload.output.verdict === 'skipped') {
                return '&#10003; Skipped';
            }
            return '&#10003; No premise detected';

        case 'decompose':
            return (payload.output.leaf_count || 0) + ' nodes &middot; depth ' +
                   (payload.output.depth || 0);

        case 'retrieve': {
            var total = payload.output.total_results || 0;
            var parts = [total + ' results'];
            // Show per-method counts from breakdown (L1/L2 only)
            if (payload.output.breakdown) {
                var bd = payload.output.breakdown;
                var vCount = (bd.vector || []).length;
                var bCount = (bd.bm25   || []).length;
                var gCount = (bd.graph  || []).length;
                parts.push(
                    '<span class="source-method-badge method-vector">V:' + vCount + '</span>' +
                    '<span class="source-method-badge method-bm25">B:' + bCount + '</span>' +
                    '<span class="source-method-badge method-graph">G:' + gCount + '</span>'
                );
            }
            // Show per-leaf count for L3+ queries
            if (payload.output.per_leaf && payload.output.per_leaf.length > 0) {
                parts.push(payload.output.per_leaf.length + ' leaves');
            }
            // Show top citation
            if (payload.output.top_5 && payload.output.top_5.length > 0) {
                var topCit = payload.output.top_5[0].citation || 'N/A';
                parts.push('top: ' + escapeHtml(topCit));
            }
            return parts.join(' &middot; ');
        }

        case 'llm_io':
            return (payload.input.num_sources || 0) + ' sources &middot; ' +
                   (payload.input.context_length_chars || 0) + ' chars context';

        default:
            return '';
    }
}

// -- Decomposition Tree Renderer (CSS Flexbox) -----------------------

function renderDecompositionTree(payload) {
    // Find the decompose card (last card with data-stage="decompose")
    var cards = auditWaterfall.querySelectorAll('.audit-card-decompose');
    var decomposeCard = cards[cards.length - 1];
    if (!decomposeCard || !payload.output || !payload.output.tree) return;

    var details = decomposeCard.querySelector('.audit-card-details');
    if (!details) return;

    // Build the tree container
    var treeContainer = document.createElement('div');
    treeContainer.className = 'audit-tree-container';
    treeContainer.appendChild(buildTreeNode(payload.output.tree));

    // Insert before the <pre> JSON block
    var preBlock = details.querySelector('.audit-json');
    if (preBlock) {
        details.insertBefore(treeContainer, preBlock);
    } else {
        details.appendChild(treeContainer);
    }
}

function buildTreeNode(node) {
    var el = document.createElement('div');
    var isLeaf = (node.left == null && node.right == null);
    var typeBadge = isLeaf ? 'leaf' : (node.node_type || 'unknown');
    el.className = 'tree-node tree-node-' + typeBadge;

    el.innerHTML =
        '<div class="tree-node-badge">' + escapeHtml(typeBadge) + '</div>' +
        '<div class="tree-node-query">' + escapeHtml(node.query || '') + '</div>';

    if (node.left || node.right) {
        var children = document.createElement('div');
        children.className = 'tree-node-children';
        if (node.left) children.appendChild(buildTreeNode(node.left));
        if (node.right) children.appendChild(buildTreeNode(node.right));
        el.appendChild(children);
    }
    return el;
}

// -- Synthesis Context Card ------------------------------------------

function addSynthesisContextCard(payload) {
    var card = document.createElement('div');
    card.className = 'audit-card audit-card-synthesis-ctx';
    card.dataset.stage = 'synthesis_context';

    var synCtxNum = getRetrieveNum() + 1;

    var chunks = payload.chunks || [];
    var graphCount = payload.graph_expanded_count || 0;
    var summary = chunks.length + ' chunks sent to synthesis' +
        (graphCount > 0 ? ' (' + graphCount + ' graph-expanded)' : '');

    var chunkListHtml = '';
    chunks.forEach(function(c, i) {
        var methodBadges = '';
        var srcs = c.retrieval_sources || [];
        var isGraphExpand = srcs.indexOf('graph_expand') !== -1;

        if (isGraphExpand) {
            // Graph-expanded chunk: show G+ badge with provenance
            var gc = (c.graph_context || [])[0] || {};
            var relType = gc.rel_type || 'graph_expand';
            var seedId  = gc.seed_chunk_id || '';
            methodBadges =
                '<span class="source-method-badge method-graph-expand" ' +
                'title="via ' + escapeHtml(relType) + ' from ' + escapeHtml(seedId) + '">G+</span>';
        } else {
            ['vector','bm25','graph'].forEach(function(m) {
                if (srcs.indexOf(m) !== -1) {
                    methodBadges += '<span class="source-method-badge method-' + m + '">' +
                        (m === 'vector' ? 'V' : m === 'bm25' ? 'B' : 'G') + '</span>';
                }
            });
        }

        var provenance = '';
        if (isGraphExpand) {
            var gc2 = (c.graph_context || [])[0] || {};
            provenance = '<div class="synthesis-ctx-provenance">via ' +
                escapeHtml(gc2.rel_type || '') + ' from ' +
                escapeHtml(gc2.seed_chunk_id || '') +
                '</div>';
        }

        chunkListHtml +=
            '<div class="synthesis-ctx-chunk' + (isGraphExpand ? ' synthesis-ctx-chunk-expanded' : '') + '">' +
                '<span class="synthesis-ctx-num">' + (i+1) + '</span>' +
                '<span class="synthesis-ctx-citation">' + escapeHtml(c.citation || '') + '</span>' +
                '<span class="sidebar-source-badge">' + escapeHtml(c.agency || '') + '</span>' +
                methodBadges +
                '<span class="synthesis-ctx-score">' + (c.score || 0).toFixed(3) + '</span>' +
                provenance +
                '<div class="synthesis-ctx-excerpt">' + escapeHtml((c.text_excerpt || '').slice(0, 500)) + '</div>' +
            '</div>';
    });

    card.innerHTML =
        '<div class="audit-card-header">' +
            '<span class="audit-card-num">' + synCtxNum + '</span>' +
            '<span class="audit-card-label">Synthesis Context</span>' +
            '<span class="audit-card-summary">' + summary + '</span>' +
        '</div>' +
        '<details class="audit-card-details">' +
            '<summary>View chunks</summary>' +
            '<div class="synthesis-ctx-list">' + chunkListHtml + '</div>' +
        '</details>';

    card.style.opacity = '0';
    card.style.transform = 'translateY(8px)';
    auditWaterfall.appendChild(card);
    requestAnimationFrame(function() {
        card.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
    });
}

// -- Token Streaming -------------------------------------------------

function appendToken(text) {
    // Show answer area
    auditPlaceholder.style.display = 'none';
    auditAnswerContent.style.display = 'block';

    // Accumulate raw text
    answerBuffer += text;

    // Render markdown with sanitization
    try {
        auditAnswer.innerHTML = DOMPurify.sanitize(marked.parse(answerBuffer, { breaks: true }));
    } catch (e) {
        auditAnswer.textContent = answerBuffer;
    }

    // Auto-scroll answer area
    var answerArea = document.getElementById('auditAnswerArea');
    if (answerArea) {
        answerArea.scrollTop = answerArea.scrollHeight;
    }
}

// -- Audit Sources Sidebar -------------------------------------------

const METHOD_LABELS = { vector: 'V', bm25: 'B', graph: 'G' };

function renderAuditSources(sources) {
    if (!sources || sources.length === 0) return;

    auditSourcesList.innerHTML = '';

    var maxScore = sources[0].score || 1;

    sources.forEach(function (source, i) {
        var item = document.createElement('div');
        item.className = 'sidebar-source-item';
        item.dataset.chunkId = source.chunk_id || '';

        var ratio = maxScore > 0 ? (source.score || 0) / maxScore : 0;
        var confClass = ratio >= 0.7 ? 'confidence-high' : ratio >= 0.4 ? 'confidence-medium' : 'confidence-low';
        var confLabel = ratio >= 0.7 ? 'High' : ratio >= 0.4 ? 'Med' : 'Low';

        // Method badges from retrieval_sources
        var methodBadges = '';
        var srcs = source.retrieval_sources || [];
        var isGraphExpand = srcs.indexOf('graph_expand') !== -1;
        // graph_context is now included in the sources payload (pipeline.py _format_sources_event)
        var gc = (source.graph_context || [])[0] || {};
        if (isGraphExpand) {
            // Graph-expanded chunk: show G+ with specific edge type + seed (mirrors synthesis card)
            // All interpolated values passed through escapeHtml — no XSS risk
            var relType = gc.rel_type || 'graph_expand';
            methodBadges = '<span class="source-method-badge method-graph-expand" ' +
                'title="via ' + escapeHtml(relType) + ' from ' + escapeHtml(gc.seed_chunk_id || '') + '">G+</span>';
        } else {
            ['vector', 'bm25', 'graph'].forEach(function (m) {
                if (srcs.indexOf(m) !== -1) {
                    methodBadges += '<span class="source-method-badge method-' + m + '">' + METHOD_LABELS[m] + '</span>';
                }
            });
        }

        // Provenance block for G+ chunks — mirrors synthesis context card display
        // All values sanitized via escapeHtml before insertion
        var provenanceHtml = '';
        if (isGraphExpand && gc.rel_type) {
            provenanceHtml = '<div class="synthesis-ctx-provenance">via ' +
                escapeHtml(gc.rel_type) + ' from ' +
                escapeHtml(gc.seed_chunk_id || '') +
                '</div>';
        }

        var CHEVRON = '<svg class="sidebar-source-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>';

        var fullText = source.text_excerpt || '';
        var previewText = fullText.slice(0, 300);
        var hasMore = fullText.length > 300;

        // All user-derived values are passed through escapeHtml() before innerHTML insertion
        item.innerHTML =
            '<div class="sidebar-source-header">' +
                '<span class="sidebar-source-num">' + (i + 1) + '</span>' +
                '<span class="sidebar-source-citation" title="' + escapeHtml(source.section_title || '') + '">' +
                    escapeHtml(source.citation || '') +
                '</span>' +
                '<span class="sidebar-source-badge">' + escapeHtml(source.agency || '') + '</span>' +
                '<span class="confidence-pill ' + confClass + '">' + confLabel + '</span>' +
                CHEVRON +
            '</div>' +
            '<div class="sidebar-source-methods">' + methodBadges + '</div>' +
            provenanceHtml +
            '<div class="sidebar-source-excerpt" data-full-text="' + escapeHtml(fullText) + '">' +
                escapeHtml(previewText) + (hasMore ? '...' : '') +
            '</div>' +
            '<div class="sidebar-source-actions">' +
                '<button class="sidebar-source-view-btn" data-agency="' + escapeHtml(source.agency || '') + '" data-citation="' + escapeHtml(source.citation || '') + '">View chunk</button>' +
            '</div>';

        // Click header to expand/collapse + fetch relationships
        item.querySelector('.sidebar-source-header').addEventListener('click', function () {
            var expanded = item.classList.toggle('expanded');
            // Toggle between truncated preview and full text
            var excerptEl = item.querySelector('.sidebar-source-excerpt');
            if (excerptEl) {
                var full = excerptEl.getAttribute('data-full-text') || '';
                if (expanded) {
                    excerptEl.textContent = full;
                } else {
                    var preview = full.slice(0, 300);
                    excerptEl.textContent = full.length > 300 ? preview + '...' : preview;
                }
            }
            if (expanded && source.chunk_id) {
                fetchAuditRelationships(source.chunk_id);
            }
        });

        auditSourcesList.appendChild(item);

        // Auto-expand first item and show full text
        if (i === 0) {
            item.classList.add('expanded');
            var excerptEl = item.querySelector('.sidebar-source-excerpt');
            if (excerptEl) {
                excerptEl.textContent = excerptEl.getAttribute('data-full-text') || '';
            }
            if (source.chunk_id) fetchAuditRelationships(source.chunk_id);
        }
    });

    // Show toggle button and open sidebar automatically first time
    auditSidebarToggle.style.display = 'inline-block';
    if (!sidebarVisible) {
        sidebarVisible = true;
        auditSidebar.style.display = 'flex';
        auditSidebarToggle.textContent = 'Sources ✕';
    }

    // Add close button to sidebar heading
    var sourcesHeading = auditSidebar.querySelector('.audit-sidebar-heading');
    if (sourcesHeading && !sourcesHeading.querySelector('.audit-sidebar-close')) {
        var closeBtn = document.createElement('button');
        closeBtn.className = 'audit-sidebar-close';
        closeBtn.textContent = '\u00d7'; // multiplication sign as X
        closeBtn.title = 'Close sidebar';
        closeBtn.addEventListener('click', function() {
            sidebarVisible = false;
            auditSidebar.style.display = 'none';
            auditSidebarToggle.textContent = 'Sources';
        });
        sourcesHeading.appendChild(closeBtn);
    }
}

async function fetchAuditRelationships(chunkId) {
    auditRelPanel.innerHTML = '<p class="relationship-loading" style="padding:12px 16px;">Loading...</p>';
    try {
        var resp = await fetch('/api/relationships/' + encodeURIComponent(chunkId));
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        var data = await resp.json();

        var groups = [
            { key: 'cites',      label: 'Cites' },
            { key: 'cited_by',   label: 'Cited by' },
            { key: 'implements', label: 'Implements' },
            { key: 'subject_to', label: 'Subject to' },
        ];

        var hasAny = false;
        var html = '';
        groups.forEach(function (g) {
            var items = data[g.key] || [];
            if (items.length === 0) return;
            hasAny = true;
            html += '<div class="relationship-group">' +
                '<div class="relationship-group-title">' + g.label + '</div>';
            items.forEach(function (rel) {
                html += '<div class="relationship-item">' + escapeHtml(rel.citation || rel.chunk_id || '') + '</div>';
            });
            html += '</div>';
        });

        auditRelPanel.innerHTML = hasAny ? html : '<p class="sidebar-empty-state" style="padding:12px 16px;">No relationships found</p>';
    } catch (e) {
        auditRelPanel.innerHTML = '<p class="sidebar-empty-state" style="padding:12px 16px;">Could not load relationships</p>';
    }
}

// -- Finalize --------------------------------------------------------

function finalizeAudit() {
    // Update total time display
    auditTotalTime.textContent = 'Total: ' + Math.round(totalElapsedMs) + 'ms';

    // Re-enable button
    isRunning = false;
    auditSendBtn.disabled = false;
    auditSendBtn.textContent = 'Run Audit';
}

// -- Utility: HTML Escaping ------------------------------------------

function escapeHtml(str) {
    if (str == null) return '';
    var s = String(str);
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
