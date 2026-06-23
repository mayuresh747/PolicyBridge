/* ================================================================
   Seattle Regulatory RAG -- Audit Panel (integrated into main page)
   ================================================================
   Renders pipeline trace cards in the audit panel sidebar.
   Called by app.js via window.AuditPanel.handleEvent().
   ================================================================ */

window.AuditPanel = (function() {
    'use strict';

    let totalElapsedMs = 0;
    let hasDecomposeCard = false;
    let stageCounter = 0;
    let usageData = null;

    function escapeHtml(str) {
        if (str == null) return '';
        var s = String(str);
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }

    function getWaterfall() {
        return document.getElementById('auditWaterfall');
    }

    function reset() {
        totalElapsedMs = 0;
        hasDecomposeCard = false;
        stageCounter = 0;
        usageData = null;
        var wf = getWaterfall();
        if (wf) wf.innerHTML = '';
        var tt = document.getElementById('auditTotalTime');
        if (tt) tt.textContent = '';
    }

    function handleEvent(eventType, rawData) {
        var data;
        try { data = typeof rawData === 'string' ? JSON.parse(rawData) : rawData; } catch(e) { data = rawData; }

        switch (eventType) {
            case 'audit_classify': addClassifyCard(data); break;
            case 'audit_premise': addPremiseCard(data); break;
            case 'audit_decompose': addDecomposeCard(data); break;
            case 'audit_retrieve': addRetrieveCard(data); break;
            case 'audit_rerank': addRerankCard(data); break;
            case 'audit_graph_expand': addGraphExpandCard(data); break;
            case 'audit_conflict_expand': addConflictExpandCard(data); break;
            case 'audit_budget': addBudgetCard(data); break;
            case 'audit_synthesis_context': addSynthesisContextCard(data); break;
            case 'audit_llm_io': addLlmIoCard(data); break;
            case 'audit_error': addErrorCard(data); break;
            case 'usage': usageData = data; updateLlmIoWithUsage(); break;
            case 'done': finalize(); break;
        }
    }

    function animateCard(card) {
        card.style.opacity = '0';
        card.style.transform = 'translateY(8px)';
        var wf = getWaterfall();
        if (wf) wf.appendChild(card);
        requestAnimationFrame(function() {
            card.style.transition = 'opacity 0.2s ease, transform 0.2s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        });
    }

    function createCard(stage, label, elapsedMs, summaryHtml, detailsHtml) {
        stageCounter++;
        totalElapsedMs += (elapsedMs || 0);
        var card = document.createElement('div');
        card.className = 'audit-card audit-card-' + stage;
        card.dataset.stage = stage;
        var elapsed = elapsedMs != null ? Math.round(elapsedMs) + 'ms' : '';
        card.innerHTML =
            '<div class="audit-card-header">' +
                '<span class="audit-card-num">' + stageCounter + '</span>' +
                '<span class="audit-card-label">' + escapeHtml(label) + '</span>' +
                '<span class="audit-card-summary">' + summaryHtml + '</span>' +
                '<span class="audit-card-elapsed">' + elapsed + '</span>' +
            '</div>' +
            (detailsHtml ? '<details class="audit-card-details"><summary>Details</summary><div class="audit-card-details-content">' + detailsHtml + '</div></details>' : '');
        animateCard(card);
        return card;
    }

    // -- Stage 1: Classification --
    function addClassifyCard(d) {
        var o = d.output || {};
        var summary = escapeHtml(o.level || '') + ' &mdash; ' + escapeHtml(o.reasoning || '');
        var details = '<div class="audit-detail-grid">' +
            '<div><strong>conflict_seeking:</strong> ' + (o.conflict_seeking ? 'true' : 'false') + '</div>' +
            '<div><strong>premise_scan_needed:</strong> ' + (o.premise_scan_needed ? 'true' : 'false') + '</div>' +
            '<div><strong>reasoning:</strong> ' + escapeHtml(o.reasoning || '') + '</div>' +
            '</div>';
        createCard('classify', 'Classification', d.elapsed_ms, summary, details);
    }

    // -- Stage 2: Premise Check --
    function addPremiseCard(d) {
        var o = d.output || {};
        var summary;
        if (o.verdict === 'false_premise') {
            summary = '&#9888; False premise: "' + escapeHtml(o.premise || '') + '"';
        } else if (o.verdict === 'skipped') {
            summary = '&#10003; Skipped';
        } else {
            summary = '&#10003; No false premise';
        }
        var details = '';
        if (o.verdict === 'false_premise') {
            details = '<div class="audit-detail-grid">' +
                '<div><strong>premise:</strong> ' + escapeHtml(o.premise || '') + '</div>' +
                '<div><strong>correction:</strong> ' + escapeHtml(o.correction || '') + '</div>' +
                '<div><strong>source:</strong> ' + escapeHtml(o.source_citation || '') + '</div>' +
                '</div>';
        }
        var card = createCard('premise', 'Premise Check', d.elapsed_ms, summary, details);
        if (o.verdict === 'false_premise') card.classList.add('premise-warning');
    }

    // -- Stage 3: Decomposition --
    function addDecomposeCard(d) {
        hasDecomposeCard = true;
        var o = d.output || {};
        var summary = (o.leaf_count || 0) + ' leaves &middot; depth ' + (o.depth || 0);

        // Structure analysis if available
        var structHtml = '';
        if (o.structure_analysis) {
            var sa = o.structure_analysis;
            structHtml = '<div class="audit-structure-analysis">' +
                '<strong>Structure Analysis:</strong>' +
                '<div>Core: ' + escapeHtml(sa.core_query || '') + '</div>' +
                '<div>Known: ' + escapeHtml((sa.known_entities || []).join(', ')) + '</div>' +
                '<div>Unknown: ' + escapeHtml((sa.unknown_entities || []).join(', ')) + '</div>' +
                '<div>Intent: ' + escapeHtml(sa.intent || '') + '</div>' +
                '</div>';
        }

        var treeHtml = '';
        if (o.tree) {
            treeHtml = '<div class="audit-tree-container">' + buildTreeNodeHtml(o.tree) + '</div>';
        }

        var card = createCard('decompose', 'Decomposition', d.elapsed_ms, summary, structHtml + treeHtml);

        // Fix tree connector positions when the details panel is opened
        // (tree has zero dimensions while <details> is closed)
        if (o.tree) {
            var details = card.querySelector('details.audit-card-details');
            if (details) {
                var connectorFixed = false;
                details.addEventListener('toggle', function() {
                    if (details.open && !connectorFixed) {
                        connectorFixed = true;
                        requestAnimationFrame(function() {
                            var treeContainer = card.querySelector('.audit-tree-container');
                            fixTreeConnectors(treeContainer);
                        });
                    }
                });
            }
        }
    }

    function buildTreeNodeHtml(node) {
        var isLeaf = (!node.left && !node.right);
        var typeBadge = isLeaf ? 'leaf' : (node.node_type || 'unknown');
        var html = '<div class="tree-node tree-node-' + typeBadge + '">' +
            '<div class="tree-node-badge">' + escapeHtml(typeBadge) + '</div>' +
            '<div class="tree-node-query">' + escapeHtml(node.query || '') + '</div>';
        if (node.left || node.right) {
            html += '<div class="tree-node-children">';
            if (node.left) html += buildTreeNodeHtml(node.left);
            if (node.right) html += buildTreeNodeHtml(node.right);
            html += '</div>';
        }
        html += '</div>';
        return html;
    }

    /**
     * After the tree DOM is rendered, fix horizontal connector bar positions.
     * Each .tree-node-children::before bar should span from the center of
     * the first child to the center of the last child. CSS can't calculate
     * this, so we use an inline element overlaid on each .tree-node-children.
     */
    function fixTreeConnectors(container) {
        if (!container) return;
        var childrenContainers = container.querySelectorAll('.tree-node-children');
        childrenContainers.forEach(function(childrenEl) {
            var children = childrenEl.querySelectorAll(':scope > .tree-node');
            if (children.length < 2) return;

            var first = children[0];
            var last = children[children.length - 1];
            var parentRect = childrenEl.getBoundingClientRect();

            // Calculate center X of first and last child relative to the children container
            var firstRect = first.getBoundingClientRect();
            var lastRect = last.getBoundingClientRect();
            var leftOffset = (firstRect.left + firstRect.width / 2) - parentRect.left;
            var rightOffset = parentRect.right - (lastRect.left + lastRect.width / 2);

            // Apply as CSS custom properties so ::before can use them,
            // or directly set left/right via an overlay div.
            // Since ::before can't read custom properties set on parent in
            // all browsers, create/update an inline connector element.
            var bar = childrenEl.querySelector('.tree-hbar');
            if (!bar) {
                bar = document.createElement('div');
                bar.className = 'tree-hbar';
                childrenEl.appendChild(bar);
            }
            bar.style.position = 'absolute';
            bar.style.top = '0';
            bar.style.left = leftOffset + 'px';
            bar.style.right = rightOffset + 'px';
            bar.style.height = '1px';
            bar.style.background = 'var(--border)';
        });
    }

    // -- Stage 4: Retrieval --
    function addRetrieveCard(d) {
        var o = d.output || {};
        var total = o.total_results || 0;
        var summaryParts = [total + ' results'];

        if (o.source_counts) {
            var sc = o.source_counts;
            summaryParts.push(
                '<span class="source-method-badge method-vector">V:' + (sc.vector || 0) + '</span>' +
                '<span class="source-method-badge method-bm25">B:' + (sc.bm25 || 0) + '</span>'
            );
        } else if (o.breakdown) {
            var bd = o.breakdown;
            summaryParts.push(
                '<span class="source-method-badge method-vector">V:' + ((bd.vector || []).length) + '</span>' +
                '<span class="source-method-badge method-bm25">B:' + ((bd.bm25 || []).length) + '</span>'
            );
        }
        if (o.per_leaf && o.per_leaf.length > 0) {
            summaryParts.push(o.per_leaf.length + ' leaves');
        }
        if (o.top_5 && o.top_5.length > 0) {
            summaryParts.push('top: ' + escapeHtml(o.top_5[0].citation || ''));
        }

        var detailsHtml = '';
        // Per-leaf breakdown with chunk tables
        if (o.per_leaf && o.per_leaf.length > 0) {
            detailsHtml += '<div class="audit-per-leaf-section">';
            detailsHtml += '<div class="audit-per-leaf-heading">Per-Leaf Breakdown</div>';
            o.per_leaf.forEach(function(leaf, idx) {
                var methods = leaf.methods || {};
                detailsHtml += '<details class="audit-per-leaf-item">' +
                    '<summary class="audit-per-leaf-query">' +
                        '<span class="audit-per-leaf-num">L' + (idx+1) + '</span> ' +
                        escapeHtml(leaf.leaf_query || '') +
                        ' <span style="color:var(--text-muted)">(' + (leaf.chunk_count || 0) + ' chunks)</span>' +
                        ' <span class="source-method-badge method-vector">V:' + (methods.vector || 0) + '</span>' +
                        '<span class="source-method-badge method-bm25">B:' + (methods.bm25 || 0) + '</span>' +
                    '</summary>';
                // Chunk table if available
                if (leaf.chunks && leaf.chunks.length > 0) {
                    detailsHtml += '<table class="audit-chunk-table"><thead><tr>' +
                        '<th>Citation</th><th>Score</th><th>Method</th></tr></thead><tbody>';
                    leaf.chunks.forEach(function(c) {
                        var badges = (c.retrieval_sources || []).map(function(m) {
                            return '<span class="source-method-badge method-' + m + '">' +
                                (m === 'vector' ? 'V' : m === 'bm25' ? 'B' : m) + '</span>';
                        }).join('');
                        detailsHtml += '<tr><td>' + escapeHtml(c.citation || '') +
                            '</td><td>' + (c.score || 0).toFixed(4) +
                            '</td><td>' + badges + '</td></tr>';
                    });
                    detailsHtml += '</tbody></table>';
                }
                detailsHtml += '</details>';
            });
            detailsHtml += '</div>';
        }

        // L1/L2 chunk details table (when chunks exist but no per_leaf)
        if (o.chunks && o.chunks.length > 0 && !(o.per_leaf && o.per_leaf.length > 0)) {
            detailsHtml += '<table class="audit-chunk-table"><thead><tr>' +
                '<th>#</th><th>Citation</th><th>Score</th><th>Source</th></tr></thead><tbody>';
            o.chunks.forEach(function(c, i) {
                var badges = (c.retrieval_sources || []).map(function(m) {
                    return '<span class="source-method-badge method-' + m + '">' +
                        (m === 'vector' ? 'V' : m === 'bm25' ? 'B' : m) + '</span>';
                }).join('');
                detailsHtml += '<tr><td>' + (i+1) + '</td><td>' + escapeHtml(c.citation || '') +
                    '</td><td>' + (c.score || 0).toFixed(4) +
                    '</td><td>' + badges + '</td></tr>';
            });
            detailsHtml += '</tbody></table>';
        }

        createCard('retrieve', 'Retrieval', d.elapsed_ms, summaryParts.join(' &middot; '), detailsHtml);
    }

    // -- Stage 5: Reranking (NEW) --
    function addRerankCard(d) {
        var summary = (d.before_count || 0) + ' &rarr; ' + (d.after_count || 0) + ' chunks &middot; method: ' + escapeHtml(d.method || '');
        if (d.fallback) summary += ' (fallback)';

        var detailsHtml = '';
        if (d.kept && d.kept.length > 0) {
            detailsHtml += '<table class="audit-chunk-table"><thead><tr>' +
                '<th>#</th><th>Citation</th><th>Before</th><th>After</th><th>&Delta;</th></tr></thead><tbody>';
            d.kept.forEach(function(r, i) {
                var delta = r.rank_change;
                var deltaStr = delta > 0 ? '+' + delta + '&uarr;' : delta < 0 ? delta + '&darr;' : '&mdash;';
                detailsHtml += '<tr><td>' + (i+1) + '</td><td>' + escapeHtml(r.citation || '') +
                    '</td><td>' + (r.before_score || 0).toFixed(4) +
                    '</td><td>' + (r.after_score || 0).toFixed(4) +
                    '</td><td>' + deltaStr + '</td></tr>';
            });
            detailsHtml += '</tbody></table>';
        }
        if (d.dropped && d.dropped.length > 0) {
            detailsHtml += '<div class="audit-dropped-heading">Dropped (' + (d.dropped_total || d.dropped.length) + ' total)</div>';
            detailsHtml += '<table class="audit-chunk-table audit-dropped-table"><thead><tr>' +
                '<th>Citation</th><th>Score</th></tr></thead><tbody>';
            d.dropped.forEach(function(r) {
                detailsHtml += '<tr><td>' + escapeHtml(r.citation || '') +
                    '</td><td>' + (r.before_score || 0).toFixed(4) + '</td></tr>';
            });
            detailsHtml += '</tbody></table>';
        }

        createCard('rerank', 'Reranking', d.elapsed_ms, summary, detailsHtml);
    }

    // -- Stage 6: Graph Expansion (NEW) --
    function addGraphExpandCard(d) {
        var added = d.added || [];
        var summary = added.length + ' chunks added from ' + (d.seeds_used || 0) + ' seeds';

        var detailsHtml = '';
        if (added.length > 0) {
            detailsHtml = '<div class="audit-graph-additions">';
            added.forEach(function(a) {
                detailsHtml += '<div class="audit-graph-addition">' +
                    '<span class="source-method-badge method-graph-expand">G+</span> ' +
                    escapeHtml(a.citation || a.chunk_id || '') +
                    ' <span style="color:var(--text-muted);font-size:0.85em">' + escapeHtml(a.edge_type || '') +
                    ' from ' + escapeHtml(a.seed_citation || '') +
                    ' (score: ' + (a.score || 0).toFixed(4) + ')</span></div>';
            });
            detailsHtml += '</div>';
        }

        createCard('graph_expand', 'Graph Expansion', d.elapsed_ms, summary, detailsHtml);
    }

    // -- Stage 7: Conflict Expansion (NEW) --
    function addConflictExpandCard(d) {
        var summary = (d.added_count || 0) + ' chunks added &middot; threshold: ' + (d.threshold || 0);

        var detailsHtml = '';
        var a1 = d.approach_1_hits || [];
        var a2 = d.approach_2_hits || [];

        if (a1.length > 0) {
            detailsHtml += '<div class="audit-conflict-heading">Approach 1 (Shared Authority): ' + a1.length + ' hits</div>';
            detailsHtml += '<table class="audit-chunk-table"><thead><tr><th>Citation</th><th>Agency</th><th>Shared Target</th></tr></thead><tbody>';
            a1.forEach(function(h) {
                detailsHtml += '<tr><td>' + escapeHtml(h.citation || '') + '</td><td>' + escapeHtml(h.agency || '') +
                    '</td><td>' + escapeHtml(h.shared_target || '') + '</td></tr>';
            });
            detailsHtml += '</tbody></table>';
        }
        if (a2.length > 0) {
            detailsHtml += '<div class="audit-conflict-heading">Approach 2 (Cross-Agency Vector): ' + a2.length + ' hits</div>';
            detailsHtml += '<table class="audit-chunk-table"><thead><tr><th>Citation</th><th>Agency</th><th>Cosine</th></tr></thead><tbody>';
            a2.forEach(function(h) {
                var cosineStr = (h.cosine || 0).toFixed(4);
                var passStr = (h.cosine || 0) >= (d.threshold || 0.55) ? ' &#10003;' : ' &#10007;';
                detailsHtml += '<tr><td>' + escapeHtml(h.citation || '') + '</td><td>' + escapeHtml(h.agency || '') +
                    '</td><td>' + cosineStr + passStr + '</td></tr>';
            });
            detailsHtml += '</tbody></table>';
        }

        createCard('conflict_expand', 'Conflict Expansion', d.elapsed_ms, summary, detailsHtml);
    }

    // -- Stage 8: Budget Gate --
    function addBudgetCard(d) {
        var trimmed = d.trimmed || 0;
        var summary = (d.total_before || 0) + ' &rarr; ' + (d.total_after || 0) + ' tokens';
        if (trimmed > 0) summary += ' (' + trimmed + ' chunks trimmed)';

        var detailsHtml = '';
        if (d.trimmed_chunks && d.trimmed_chunks.length > 0) {
            detailsHtml = '<table class="audit-chunk-table"><thead><tr>' +
                '<th>Citation</th><th>Priority</th><th>Tokens</th><th>Source</th></tr></thead><tbody>';
            d.trimmed_chunks.forEach(function(c) {
                var srcBadge = (c.retrieval_sources || []).map(function(s) {
                    return '<span class="source-method-badge method-' + s + '">' + s.charAt(0).toUpperCase() + '</span>';
                }).join('');
                detailsHtml += '<tr><td>' + escapeHtml(c.citation || '') +
                    '</td><td>' + (c.priority_tier || 0) +
                    '</td><td>' + (c.tokens || 0) +
                    '</td><td>' + srcBadge + '</td></tr>';
            });
            detailsHtml += '</tbody></table>';
        }

        createCard('budget', 'Budget Gate', d.elapsed_ms || 0, summary, detailsHtml);
    }

    // -- Stage 9: Synthesis Context --
    function addSynthesisContextCard(d) {
        var chunks = d.chunks || [];
        var graphCount = d.graph_expanded_count || 0;
        var conflictCount = d.conflict_expanded_count || 0;
        var summary = chunks.length + ' chunks';
        if (graphCount > 0) summary += ' &middot; ' + graphCount + ' graph-expanded';
        if (conflictCount > 0) summary += ' &middot; ' + conflictCount + ' conflict-expanded';
        if (d.total_tokens) summary += ' &middot; ' + d.total_tokens + ' tokens';

        var detailsHtml = '<div class="synthesis-ctx-list">';
        chunks.forEach(function(c, i) {
            var srcs = c.retrieval_sources || [];
            var isGraphExpand = srcs.indexOf('graph_expand') !== -1;
            var isConflictExpand = srcs.indexOf('conflict_expand') !== -1;
            var methodBadges = '';

            if (isConflictExpand) {
                methodBadges += '<span class="source-method-badge method-conflict">C</span>';
            }
            if (isGraphExpand) {
                methodBadges += '<span class="source-method-badge method-graph-expand">G+</span>';
            }
            ['vector','bm25','graph'].forEach(function(m) {
                if (srcs.indexOf(m) !== -1) {
                    methodBadges += '<span class="source-method-badge method-' + m + '">' +
                        (m === 'vector' ? 'V' : m === 'bm25' ? 'B' : 'G') + '</span>';
                }
            });

            var tokensLabel = c.tokens ? ' <span style="color:var(--text-muted);font-size:0.85em">' + c.tokens + 'tok</span>' : '';

            detailsHtml +=
                '<div class="synthesis-ctx-chunk' + (isGraphExpand ? ' synthesis-ctx-chunk-expanded' : '') + (isConflictExpand ? ' synthesis-ctx-chunk-conflict' : '') + '">' +
                    '<span class="synthesis-ctx-num">' + (i+1) + '</span>' +
                    '<span class="synthesis-ctx-citation">' + escapeHtml(c.citation || '') + '</span>' +
                    '<span class="sidebar-source-badge">' + escapeHtml(c.agency || '') + '</span>' +
                    methodBadges +
                    '<span class="synthesis-ctx-score">' + (c.score || 0).toFixed(3) + '</span>' +
                    tokensLabel +
                '</div>';
        });
        detailsHtml += '</div>';

        createCard('synthesis_context', 'Synthesis Context', null, summary, detailsHtml);
    }

    // -- Stage 10: LLM I/O --
    function addLlmIoCard(d) {
        var inp = d.input || {};
        var summary = (inp.num_sources || 0) + ' sources &middot; ' + (inp.context_length_chars || 0) + ' chars &middot; ' + escapeHtml(inp.model || '');
        createCard('llm_io', 'LLM I/O', null, summary,
            '<div class="audit-detail-grid">' +
            '<div><strong>Model:</strong> ' + escapeHtml(inp.model || '') + '</div>' +
            '<div><strong>Temperature:</strong> ' + (inp.temperature || 0) + '</div>' +
            '<div><strong>Max tokens:</strong> ' + (inp.max_tokens || 0) + '</div>' +
            '<div><strong>Sources:</strong> ' + (inp.num_sources || 0) + '</div>' +
            '<div><strong>Context:</strong> ' + (inp.context_length_chars || 0) + ' chars</div>' +
            '</div>'
        );
    }

    function updateLlmIoWithUsage() {
        if (!usageData) return;
        var data;
        try { data = typeof usageData === 'string' ? JSON.parse(usageData) : usageData; } catch(e) { return; }
        var card = document.querySelector('.audit-card-llm_io');
        if (!card) return;
        var details = card.querySelector('.audit-card-details .audit-detail-grid');
        if (details) {
            details.innerHTML += '<div><strong>Prompt tokens:</strong> ' + (data.prompt_tokens || 0) + '</div>' +
                '<div><strong>Completion tokens:</strong> ' + (data.completion_tokens || 0) + '</div>';
        }
    }

    // -- Error Card --
    function addErrorCard(d) {
        stageCounter++;
        var card = document.createElement('div');
        card.className = 'audit-card audit-card-error';
        card.innerHTML =
            '<div class="audit-card-header">' +
                '<span class="audit-card-num">' + stageCounter + '</span>' +
                '<span class="audit-card-label" style="color:var(--error)">' + escapeHtml(d.stage || 'unknown') + ' FAILED</span>' +
                '<span class="audit-card-summary">' + escapeHtml(d.error_type || '') + ': ' + escapeHtml(d.error || '') + '</span>' +
            '</div>' +
            '<details class="audit-card-details"><summary>View traceback</summary>' +
                '<pre class="audit-json" style="color:var(--error)">' + escapeHtml(d.traceback || '') + '</pre>' +
            '</details>';
        animateCard(card);
    }

    function finalize() {
        var tt = document.getElementById('auditTotalTime');
        if (tt) tt.textContent = 'Total: ' + Math.round(totalElapsedMs) + 'ms';
    }

    /**
     * Replay a historical trace instantly (D-24).
     * Shows "Historical -- {timestamp}" header and renders all stages
     * without staggered animation.
     *
     * @param {Object} traceData - { trace_id, stages: [...], total_ms, created_at }
     *   Each stage: { stage: "classify", data: {...}, elapsed_ms, timestamp }
     */
    function replayTrace(traceData) {
        reset();

        // Show historical header
        var header = document.createElement('div');
        header.className = 'audit-historical-header';
        var timestamp = 'Unknown';
        if (traceData.created_at) {
            timestamp = new Date(traceData.created_at).toLocaleString();
        } else if (traceData.stages && traceData.stages.length > 0 && traceData.stages[0].timestamp) {
            timestamp = new Date(traceData.stages[0].timestamp * 1000).toLocaleString();
        }
        header.textContent = 'Historical \u2014 ' + timestamp;
        var wf = getWaterfall();
        if (wf) wf.prepend(header);

        // Override animateCard temporarily to render instantly (no animation)
        var origAnimateCard = animateCard;
        animateCard = function(card) {
            card.style.opacity = '1';
            card.style.transform = 'none';
            if (wf) wf.appendChild(card);
        };

        // Replay all stages
        var stages = traceData.stages || [];
        for (var i = 0; i < stages.length; i++) {
            var stage = stages[i];
            var eventName = 'audit_' + stage.stage;
            // handleEvent takes (eventType, rawData) -- rawData can be object
            handleEvent(eventName, stage.data);
        }

        // Restore animateCard
        animateCard = origAnimateCard;

        // Set total time from stored value
        if (traceData.total_ms != null) {
            totalElapsedMs = traceData.total_ms;
        }
        finalize();
    }

    return { handleEvent: handleEvent, reset: reset, replayTrace: replayTrace, finalize: finalize };
})();
