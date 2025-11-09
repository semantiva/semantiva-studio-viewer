    const {useState, useEffect, useRef, useCallback} = React;

    // Mobile detection utility
    const isMobile = () => window.innerWidth <= 768;

    // Constants and Configuration
    const LAYOUT_CONFIG = {
      channelGap: 10,
      nodeWidth: 300,
      verticalSpacing: 20,
      baseContentHeight: 80,
      calloutHeight: 24,
      calloutSpacing: 4,
      minCalloutWidth: 60,
      textWidthEstimate: 7, // pixels per character
      nameTextEstimate: 9, // pixels per character for node names
    };

    const COLORS = {
      configChannel: {
        background: 'linear-gradient(135deg, #f2f2f7 0%, #e5e5ea 100%)',
        border: '#8e8e93',
        text: '#48484a'
      },
      dataChannel: {
        background: 'linear-gradient(135deg, #e8f4fd 0%, #c7e0f4 100%)',
        border: '#007aff',
        text: '#007aff'
      },
      contextChannel: {
        background: 'linear-gradient(135deg, #f5e6ff 0%, #e6ccff 100%)',
        border: '#af52de',
        text: '#7b1fa2'
      },
      error: '#ff3b30',
      success: '#34c759',
      warning: '#ff9f0a'
    };

    // Utility Functions
    function calculateCalloutWidth(text) {
      const textWidth = text.length * LAYOUT_CONFIG.textWidthEstimate;
      return Math.max(LAYOUT_CONFIG.minCalloutWidth, textWidth + 16);
    }

    function truncateHash(hash, maxLength = 20) {
      if (!hash || hash.length <= maxLength) return hash;
      return hash.substring(0, maxLength) + '...';
    }

    // Format numeric values preserving float type (e.g., 10.0 stays "10.0", not "10")
    function formatNumber(value) {
      if (typeof value !== 'number') return String(value);
      // Always show at least one decimal place for whole numbers to preserve float type
      if (Number.isInteger(value)) {
        return value.toFixed(1);
      }
      return String(value);
    }

    function createCalloutStyle(type, text) {
      const width = calculateCalloutWidth(text);
      const baseStyle = {
        borderRadius: '4px',
        padding: '4px 8px',
        fontSize: '11px',
        whiteSpace: 'nowrap',
        height: `${LAYOUT_CONFIG.calloutHeight}px`,
        width: `${width}px`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxSizing: 'border-box',
        fontWeight: '500',
        textAlign: 'center'
      };

      const typeStyles = {
        config: {
          background: '#f2f2f7',
          border: '1px solid #8e8e93',
          color: '#48484a'
        },
        default: {
          background: '#fff4e6',
          border: '1px solid #ff9f0a',
          color: '#d68910'
        },
        context: {
          background: '#f5e6ff',
          border: '1px solid #af52de',
          color: '#7b1fa2'
        },
        created: {
          background: '#e8f5ea',
          border: '1px solid #34c759',
          color: '#1d8348'
        },
        sweep: {
          background: '#e6fbfb',
          border: '1px solid #00b3b3',
          color: '#007a7a'
        }
      };

      return { ...baseStyle, ...typeStyles[type] };
    }

    // Try to pretty-format string representations (JSON preferred, else a Python-ish dict/array heuristic)
    function formatRepr(raw) {
      if (!raw || typeof raw !== 'string') return String(raw || '');

      // Try JSON first (gives best structured output)
      try {
        const parsed = JSON.parse(raw);
        return JSON.stringify(parsed, null, 2);
      } catch (e) {
        // not JSON, continue
      }

      // Heuristic pretty-printer. Force expansion for dict-like braces ({}) so
      // keys appear one-per-line with indentation. Keep short arrays/tuples inline.
      const indentUnit = '  ';
      let out = '';
      let i = 0;
      const n = raw.length;

      function findMatching(startIdx, openChar) {
        const pairs = { '{': '}', '[': ']', '(': ')' };
        const closeChar = pairs[openChar];
        let depth = 0;
        let j = startIdx;
        let inString = false;
        let strChar = null;
        let esc = false;
        for (; j < n; j++) {
          const ch = raw[j];
          if (esc) { esc = false; continue; }
          if (ch === '\\') { esc = true; continue; }
          if (inString) {
            if (ch === strChar) { inString = false; strChar = null; }
            continue;
          }
          if (ch === '"' || ch === "'") { inString = true; strChar = ch; continue; }
          if (ch === openChar) depth += 1;
          else if (ch === closeChar) {
            depth -= 1;
            if (depth === 0) return j; // index of closing char
          }
        }
        return -1;
      }

      const indent = (d) => indentUnit.repeat(d);
      let depth = 0;
      const compactThreshold = 80;

      while (i < n) {
        const ch = raw[i];

        // Strings: copy verbatim until closing quote
        if (ch === '"' || ch === "'") {
          let j = i + 1;
          let esc = false;
          for (; j < n; j++) {
            if (esc) { esc = false; continue; }
            if (raw[j] === '\\') { esc = true; continue; }
            if (raw[j] === ch) { j++; break; }
          }
          out += raw.slice(i, j);
          i = j;
          continue;
        }

        if (ch === '{' || ch === '[' || ch === '(') {
          const matchIdx = findMatching(i, ch);
          if (matchIdx !== -1) {
            const content = raw.slice(i + 1, matchIdx);
            // For dictionaries ({}), always expand so keys are on separate lines.
            // For arrays/tuples keep inline when short and single-line.
            if (ch !== '{' && content.length <= compactThreshold && !content.includes('\n')) {
              out += ch + content + raw[matchIdx];
              i = matchIdx + 1;
              continue;
            }
          }

          // Expand (put contents on following indented lines)
          out += ch + '\n' + indent(depth + 1);
          depth += 1;
          i += 1;
          continue;
        }

        if (ch === '}' || ch === ']' || ch === ')') {
          depth = Math.max(0, depth - 1);
          out += '\n' + indent(depth) + ch;
          i += 1;
          // if next is comma, append it and then newline+indent for next key/elem
          if (i < n && raw[i] === ',') {
            out += ',';
            i += 1;
            out += '\n' + indent(depth);
          }
          continue;
        }

        if (ch === ',') {
          // put comma then space so key: value stays on same line but next key starts on new line
          out += ',';
          // if we're inside an expanded dict/array, newline + indent; otherwise keep space
          if (depth > 0) out += '\n' + indent(depth);
          else out += ' ';
          i += 1;
          continue;
        }

        // default: copy char
        out += ch;
        i += 1;
      }

      // Normalize trailing spaces and return
      return out.split('\n').map(line => line.replace(/\s+$/,'')).join('\n');
    }

    // Helper extractors for SER raw event data used by the Trace cards
    function extractInputSummaries(raw) {
      const s = (raw && raw.summaries) || {};
      const io = (raw && raw.context_delta) || {};
      const ioSum = io.key_summaries || {};
      const find = (k) => s[k] || ioSum[k] || null;
      const input = find('input_data');
      const preCtx = find('pre_context');
      return {
        dataType: (input && (input.dtype || input.type)) || undefined,
        dataRepr: (input && input.repr) || undefined,
        dataHash: input && input.sha256,
        ctxRepr: (preCtx && preCtx.repr) || undefined,
        ctxHash: preCtx && preCtx.sha256,
      };
    }

    function extractOutputSummaries(raw) {
      const s = (raw && raw.summaries) || {};
      const io = (raw && raw.context_delta) || {};
      const ioSum = io.key_summaries || {};
      const find = (k) => s[k] || ioSum[k] || null;
      const output = find('output_data');
      const postCtx = find('post_context');
      return {
        dataType: (output && (output.dtype || output.type)) || undefined,
        dataRepr: (output && output.repr) || undefined,
        dataHash: output && output.sha256,
        ctxRepr: (postCtx && postCtx.repr) || undefined,
        ctxHash: postCtx && postCtx.sha256,
      };
    }

    function extractContextDelta(raw) {
      const io = (raw && raw.context_delta) || {};
      const sums = io.key_summaries || {};
      const mk = (x) => Array.isArray(x) ? x : (x ? [x] : []);
      const created = mk(io.created_keys);
      const updated = mk(io.updated_keys);
      const read = mk(io.read_keys);
      return { created, updated, read, summariesByKey: sums };
    }

    function extractExecMeta(raw) {
      const ids = (raw && raw.identity) || {};
      const timing = (raw && raw.timing) || {};
      const assertions = (raw && raw.assertions) || {};
      return {
        node_uuid: ids.node_id || (raw && (raw.node_uuid || raw.node_id)) || '—',
  node_index: (raw && raw.node_index) != null ? raw.node_index : '—',
        started: timing.started_at || '—',
        ended: timing.finished_at || '—',
        status: (raw && raw.status) || '—',
  // Normalize timings: prefer wall_ms (schema v1), then legacy duration_ms, then seconds→ms
  wall: (timing.wall_ms != null) ? `${timing.wall_ms} ms` : (timing.duration_ms != null) ? `${timing.duration_ms} ms` : (timing.duration_s != null ? `${Math.round(Number(timing.duration_s) * 1000)} ms` : (timing.duration != null ? `${Math.round(Number(timing.duration) * 1000)} ms` : '—')),
  cpu: (timing.cpu_ms != null) ? `${timing.cpu_ms} ms` : (timing.cpu_s != null ? `${Math.round(Number(timing.cpu_s) * 1000)} ms` : (timing.cpu != null ? `${Math.round(Number(timing.cpu) * 1000)} ms` : '—')),
        env: assertions.environment || null,
        runArgs: assertions.args || null,
      };
    }

    // Trace panel card components
    function TraceExecutionCard({ raw, metaOverrides }) {
      const m0 = extractExecMeta(raw || {});
      const m = { ...m0, ...(metaOverrides || {}) };
      const statusClass = (m.status || '').toLowerCase() === 'completed' ? 'ok' : ((m.status || '').toLowerCase() === 'error' ? 'bad' : 'warn');
      return (
        <div className="sv-card">
          <div className="sv-card-title">Execution</div>
          <div className="sv-kv-grid">
            <div className="kv"><span className="k">node_uuid:</span> <span className="v mono" title={m.node_uuid}>{m.node_uuid}</span>{m.node_uuid && m.node_uuid !== '—' && (<button style={{marginLeft:'6px'}} onClick={() => navigator.clipboard && navigator.clipboard.writeText(m.node_uuid)}>Copy</button>)}</div>
            <div className="kv"><span className="k">node index:</span> <span className="v">{(m.node_index != null) ? m.node_index : '—'}</span></div>
            <div className="kv"><span className="k">started:</span> <span className="v">{m.started || '—'}</span></div>
            <div className="kv"><span className="k">ended:</span> <span className="v">{m.ended || '—'}</span></div>
            <div className="kv"><span className="k">status:</span> <span className={`v pill ${statusClass}`}>{m.status || '—'}</span></div>
            <div className="kv"><span className="k">wall:</span> <span className="v">{m.wall || '—'}</span></div>
            <div className="kv"><span className="k">cpu:</span> <span className="v">{m.cpu || '—'}</span></div>
          </div>
          {m.runArgs && Object.keys(m.runArgs).length > 0 && (
            <details className="sv-details">
              <summary>Run Args</summary>
              <pre className="sv-json">{JSON.stringify(m.runArgs, null, 2)}</pre>
            </details>
          )}
          {m.env && (
            <details className="sv-details">
              <summary>Environment</summary>
              <pre className="sv-json">{JSON.stringify(m.env, null, 2)}</pre>
            </details>
          )}
        </div>
      );
    }

    function TraceInputCard({ raw, paramProvenanceRenderer=null }) {
      const s = extractInputSummaries(raw);
      return (
        <div className="sv-card">
          <div className="sv-card-title">Input</div>
          <div className="sv-kv-grid">
            <div className="kv"><span className="k">data.type:</span> <span className="v">{s.dataType || 'n/a'}</span></div>
            <div className="kv"><span className="k">data.repr:</span> <span className="v mono" title={s.dataRepr || ''}>{s.dataRepr || '—'}</span></div>
            <div className="kv"><span className="k">data.hash:</span> <span className="v mono">{s.dataHash || '—'}</span>{s.dataHash && (<button style={{marginLeft:'6px'}} onClick={() => navigator.clipboard && navigator.clipboard.writeText(s.dataHash)}>Copy</button>)}</div>
            <div className="kv"><span className="k">context.repr:</span> <span className="v mono" title={s.ctxRepr || ''}>{s.ctxRepr || '—'}</span></div>
            <div className="kv"><span className="k">context.hash:</span> <span className="v mono">{s.ctxHash || '—'}</span>{s.ctxHash && (<button style={{marginLeft:'6px'}} onClick={() => navigator.clipboard && navigator.clipboard.writeText(s.ctxHash)}>Copy</button>)}</div>
          </div>
          {paramProvenanceRenderer && (
            <div style={{padding:'0 10px 10px 10px'}}>
              <div style={{marginTop:'8px', marginBottom:'6px', fontWeight:'600', fontSize:'12px', color:'#374151'}}>Parameter Provenance</div>
              {paramProvenanceRenderer()}
            </div>
          )}
        </div>
      );
    }

    function TraceOutputCard({ raw }) {
      const s = extractOutputSummaries(raw);
      const d = extractContextDelta(raw);
      const ChipList = ({ label, items }) => (
        <div className="kv">
          <span className="k">{label}:</span> 
          <span className="v">
            {(items && items.length) ? items.map(k => {
              const sum = d.summariesByKey && d.summariesByKey[k];
              const title = sum ? `${sum.repr || ''}${sum.sha256 ? `\n${sum.sha256}` : ''}` : '';
              return <span key={k} className="chip" title={title}>{k}</span>;
            }) : '—'}
          </span>
        </div>
      );
      return (
        <div className="sv-card">
          <div className="sv-card-title">Output</div>
          <div className="sv-kv-grid">
            <div className="kv"><span className="k">data.type:</span> <span className="v">{s.dataType || 'n/a'}</span></div>
            <div className="kv"><span className="k">data.repr:</span> <span className="v mono" title={s.dataRepr || ''}>{s.dataRepr || '—'}</span></div>
            <div className="kv"><span className="k">data.hash:</span> <span className="v mono">{s.dataHash || '—'}</span>{s.dataHash && (<button style={{marginLeft:'6px'}} onClick={() => navigator.clipboard && navigator.clipboard.writeText(s.dataHash)}>Copy</button>)}</div>
            <div className="kv"><span className="k">context.repr:</span> <span className="v mono" title={s.ctxRepr || ''}>{s.ctxRepr || '—'}</span></div>
            <div className="kv"><span className="k">context.hash:</span> <span className="v mono">{s.ctxHash || '—'}</span>{s.ctxHash && (<button style={{marginLeft:'6px'}} onClick={() => navigator.clipboard && navigator.clipboard.writeText(s.ctxHash)}>Copy</button>)}</div>
            {/* Render created/updated keys as `key: <repr>` lines; omit read keys (provenance covers reads) */}
            <div className="kv">
              <span className="k">created keys:</span>
              <span className="v">
                {(d.created && d.created.length) ? (
                  <div style={{display:'block'}}>
                    {d.created.map(k => {
                      const sum = d.summariesByKey && d.summariesByKey[k];
                      const repr = (sum && sum.repr) ? sum.repr : (s.summaries && s.summaries[k] && s.summaries[k].repr) || '—';
                      return <div key={`created-${k}`} className="kv"><span className="k">{k}:</span> <span className="v mono" title={repr}>{repr}</span></div>;
                    })}
                  </div>
                ) : '—'}
              </span>
            </div>
            <div className="kv">
              <span className="k">updated keys:</span>
              <span className="v">
                {(d.updated && d.updated.length) ? (
                  <div style={{display:'block'}}>
                    {d.updated.map(k => {
                      const sum = d.summariesByKey && d.summariesByKey[k];
                      const repr = (sum && sum.repr) ? sum.repr : (s.summaries && s.summaries[k] && s.summaries[k].repr) || '—';
                      return <div key={`updated-${k}`} className="kv"><span className="k">{k}:</span> <span className="v mono" title={repr}>{repr}</span></div>;
                    })}
                  </div>
                ) : '—'}
              </span>
            </div>
          </div>
        </div>
      );
    }

    function TraceChecksCard({ raw }) {
      const assertions = (raw && raw.assertions) || {};
      const preconditions = assertions.preconditions || [];
      const postconditions = assertions.postconditions || [];
      const Pills = ({ title, items }) => {
        if (!items || !items.length) return null;
        return (
          <div style={{marginTop:'6px'}}>
            <div className="sv-subtitle">{title}</div>
            <div className="pill-row">
              {items.map((x, i) => {
                const pass = (x.pass != null) ? x.pass : (String(x.result || '').toUpperCase() === 'PASS');
                const label = x.name || x.code || x.rule || (pass ? 'PASS' : 'FAIL');
                return <span key={i} className={`pill ${pass ? 'ok' : 'bad'}`}>{label}</span>;
              })}
            </div>
          </div>
        );
      };
      return (
        <div className="sv-card">
          <div className="sv-card-title">SER Checks</div>
          <Pills title="Pre-execution" items={preconditions} />
          <Pills title="Post-execution" items={postconditions} />
          <Pills title="Invariants" items={assertions.invariants} />
        </div>
      );
    }

    // Resizable panel hook
    function useResizable(initialWidth, minWidth = 200, maxWidth = 600) {
      const [width, setWidth] = useState(initialWidth);
      const [isResizing, setIsResizing] = useState(false);
      const startX = useRef(0);
      const startWidth = useRef(0);

      const handleMouseDown = useCallback((e) => {
        setIsResizing(true);
        startX.current = e.clientX;
        startWidth.current = width;
        e.preventDefault();
      }, [width]);

      const handleMouseMove = useCallback((e) => {
        if (!isResizing) return;
        
        const deltaX = e.clientX - startX.current;
        const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth.current + deltaX));
        setWidth(newWidth);
      }, [isResizing, minWidth, maxWidth]);

      const handleMouseUp = useCallback(() => {
        setIsResizing(false);
      }, []);

      useEffect(() => {
        if (isResizing) {
          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
          document.body.style.cursor = 'ew-resize';
          document.body.style.userSelect = 'none';
          
          return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
          };
        }
      }, [isResizing, handleMouseMove, handleMouseUp]);

      return { width, isResizing, handleMouseDown };
    }

    // Resizable panel hook for right panel (details)
    function useResizableRight(initialWidth, minWidth = 200, maxWidth = 500) {
      const [width, setWidth] = useState(initialWidth);
      const [isResizing, setIsResizing] = useState(false);
      const startX = useRef(0);
      const startWidth = useRef(0);

      const handleMouseDown = useCallback((e) => {
        setIsResizing(true);
        startX.current = e.clientX;
        startWidth.current = width;
        e.preventDefault();
      }, [width]);

      const handleMouseMove = useCallback((e) => {
        if (!isResizing) return;
        
        const deltaX = startX.current - e.clientX; // Reversed for right panel
        const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth.current + deltaX));
        setWidth(newWidth);
      }, [isResizing, minWidth, maxWidth]);

      const handleMouseUp = useCallback(() => {
        setIsResizing(false);
      }, []);

      useEffect(() => {
        if (isResizing) {
          document.addEventListener('mousemove', handleMouseMove);
          document.addEventListener('mouseup', handleMouseUp);
          document.body.style.cursor = 'ew-resize';
          document.body.style.userSelect = 'none';
          
          return () => {
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
          };
        }
      }, [isResizing, handleMouseMove, handleMouseUp]);

      return { width, isResizing, handleMouseDown };
    }

    // Individual node component with anchor placeholders
  function PipelineNode({ node, pos, isSelected, onClick, registerAnchors, width, height, traceAgg, traceOverlayVisible, getCalloutHoverText }) {
      const nodeRef = useRef(null);
      const topRefs = useRef([null]);
      const bottomRefs = useRef([null]);
      const leftParamRefs = useRef([]);
      const execRightRef = useRef(null);
      const paramRightRefs = useRef([]);

      useEffect(() => {
        if (!nodeRef.current) return;
        // Provide DOM elements to the registration function so the CoordinateSystem
        // helper can measure them consistently in container-local coordinates.
        const anchors = {
          top: topRefs.current.filter(Boolean),
          bottom: bottomRefs.current.filter(Boolean),
          left: leftParamRefs.current.filter(Boolean),
          right: [execRightRef.current, ...paramRightRefs.current.filter(Boolean)].filter(Boolean),
          node: nodeRef.current
        };
        registerAnchors(node.id, anchors);
      }, [node.id, node.data.contextParams.length, registerAnchors]);

      const leftParamCount = ((node.data.pipelineConfigParams ? node.data.pipelineConfigParams.length : 0) || 0) + 
                             ((node.data.defaultParams ? node.data.defaultParams.length : 0) || 0) +
                             ((node.data.sweepParams ? node.data.sweepParams.length : 0) || 0);
      const rightParamCount = (node.data.contextParams ? node.data.contextParams.length : 0) + 
                              (node.data.createdKeys ? node.data.createdKeys.length : 0);
      
      const nodeName = node.data.label;
      const inputType = node.data.inputType;
      const outputType = node.data.outputType;
      const hasErrors = node.data.hasErrors || false;
      
      // Calculate minimum width needed for the component name
      const nameLength = nodeName.length;
      const estimatedTextWidth = nameLength * LAYOUT_CONFIG.nameTextEstimate;
      const minWidthForText = Math.max(width, estimatedTextWidth + 40);
      const nodeWidthToUse = pos.type === 'source-sink' ? Math.max(450, minWidthForText) : minWidthForText;

      // Calculate dynamic height based on content and callouts
      const maxCallouts = Math.max(leftParamCount, rightParamCount);
      const calloutsHeight = maxCallouts > 0 ? 
        (maxCallouts * LAYOUT_CONFIG.calloutHeight) + ((maxCallouts - 1) * LAYOUT_CONFIG.calloutSpacing) : 0;
      const dynamicHeight = Math.max(LAYOUT_CONFIG.baseContentHeight, calloutsHeight + 30);

      // Determine trace status class (using SER v1 status field)
      let traceClass = '';
      if (traceOverlayVisible && traceAgg) {
        if (traceAgg.status === 'succeeded') {
          traceClass = 'trace-success';
        } else if (traceAgg.status === 'error') {
          traceClass = 'trace-error';
        } else if (traceAgg.status === 'skipped' || traceAgg.status === 'cancelled') {
          traceClass = 'trace-neutral';
        } else {
          traceClass = 'trace-neutral';
        }
      }

      return (
        <div
          ref={nodeRef}
          key={node.id}
          className={`custom-node ${pos.type} ${isSelected ? 'selected' : ''} ${hasErrors ? 'error' : ''} ${traceClass}`}
          style={{
            left: pos.x - nodeWidthToUse / 2,
            top: pos.y,
            width: nodeWidthToUse,
            height: dynamicHeight,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            padding: '8px',
            boxSizing: 'border-box'
          }}
          onClick={() => onClick(null, node)}
        >
          {/* Input data type at top */}
          <div
            style={{
              fontSize: '11px',
              color: '#666',
              textAlign: 'center',
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
              lineHeight: '1.2',
              minHeight: inputType ? 'auto' : '0px',
              padding: '0 4px'
            }}
          >
            {inputType ? `→ ${inputType}` : ''}
          </div>
          
          {/* Operation name in the center - will be automatically centered by flex */}
          <div
            style={{
              fontWeight: 'bold',
              fontSize: '14px',
              color: '#333',
              textAlign: 'center',
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
              hyphens: 'auto',
              lineHeight: '1.2',
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '0 4px' // Add some padding to prevent text from touching edges
            }}
          >
            {nodeName}
          </div>
          
          {/* Output data type at bottom */}
          <div
            style={{
              fontSize: '11px',
              color: '#666',
              textAlign: 'center',
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
              lineHeight: '1.2',
              minHeight: outputType ? 'auto' : '0px',
              padding: '0 4px'
            }}
          >
            {outputType ? `${outputType} →` : ''}
          </div>

          {/* Node ID - positioned absolutely */}
          <div
            style={{
              position: 'absolute',
              top: '2px',
              right: '8px',
              fontSize: '10px',
              color: '#999',
              fontWeight: 'bold'
            }}
          >
            #{node.id}
          </div>

          {/* Anchor elements - positioned at edge centers */}
          <div 
            ref={el => (topRefs.current[0] = el)} 
            className="anchor top"
            style={{
              position: 'absolute',
              top: '0px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: '1px',
              height: '1px'
            }}
          />
          <div 
            ref={el => (bottomRefs.current[0] = el)} 
            className="anchor bottom"
            style={{
              position: 'absolute',
              bottom: '0px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: '1px',
              height: '1px'
            }}
          />
          {[...Array(leftParamCount)].map((_, i) => (
            <div
              key={`l-${i}`}
              ref={el => (leftParamRefs.current[i] = el)}
              className="anchor left"
            />
          ))}
          <div ref={execRightRef} className="anchor right" />
          
          {/* Context params and created keys - positioned on the right */}
          <div 
            className="context-params"
            style={{
              position: 'absolute',
              left: '100%',
              top: '50%',
              transform: 'translateY(-50%)',
              marginLeft: '8px',
              display: 'flex',
              flexDirection: 'column',
              gap: `${LAYOUT_CONFIG.calloutSpacing}px`
            }}
          >
            {node.data.contextParams.map((param, i) => (
              <div
                key={param}
                ref={el => (paramRightRefs.current[i] = el)}
                className="param-label right-anchor"
                style={createCalloutStyle('context', param)}
                title={getCalloutHoverText ? getCalloutHoverText(node.id, 'param', param) : undefined}
              >
                {param}
              </div>
            ))}
            {(node.data.createdKeys || []).map((key, i) => (
              <div
                key={key}
                className="param-label created-key"
                style={createCalloutStyle('created', key)}
                title={getCalloutHoverText ? getCalloutHoverText(node.id, 'created', key) : undefined}
              >
                {key}
              </div>
            ))}
          </div>
          
          {/* Config params - positioned on the left */}
          <div 
            className="config-params"
            style={{
              position: 'absolute',
              right: '100%',
              top: '50%',
              transform: 'translateY(-50%)',
              marginRight: '8px',
              display: 'flex',
              flexDirection: 'column',
              gap: `${LAYOUT_CONFIG.calloutSpacing}px`,
              alignItems: 'flex-end'
            }}
          >
            {(node.data.pipelineConfigParams || []).map((param, i) => (
              <div
                key={param}
                className="param-label left-anchor"
                style={createCalloutStyle('config', param)}
                title={getCalloutHoverText ? getCalloutHoverText(node.id, 'param', param) : undefined}
              >
                {param}
              </div>
            ))}
            {(node.data.defaultParams || []).map((param, i) => (
              <div
                key={param}
                className="param-label left-anchor-default"
                style={createCalloutStyle('default', param)}
                title={getCalloutHoverText ? getCalloutHoverText(node.id, 'default', param) : undefined}
              >
                {param}
              </div>
            ))}
            {(node.data.sweepParams || []).map((param, i) => (
              <div
                key={param}
                className="param-label left-anchor-default"
                style={createCalloutStyle('sweep', param)}
                title={getCalloutHoverText ? getCalloutHoverText(node.id, 'sweep', param) : undefined}
              >
                {param}
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Custom Graph Component with dual-channel layout
  function CustomGraph({ nodes, edges, onNodeClick, selectedNodeId, traceAvailable, traceOverlayVisible, getTraceAggForNode, getCalloutHoverText }) {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [containerRef, setContainerRef] = useState(null);
  const wrapperRef = React.useRef(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const draggingRef = React.useRef(false);
  const lastPointer = React.useRef({ x: 0, y: 0 });
  // CoordinateSystem helper instance
  const csRef = React.useRef(null);
      const [anchorMap, setAnchorMap] = useState({});
      const [colWidths, setColWidths] = useState({ data: 300, config: 80, context: 300 });

      // Calculate dynamic height for each node
      const calculateNodeHeight = (node) => {
        const leftParamCount = ((node.data.pipelineConfigParams ? node.data.pipelineConfigParams.length : 0) || 0) + 
                               ((node.data.defaultParams ? node.data.defaultParams.length : 0) || 0) +
                               ((node.data.sweepParams ? node.data.sweepParams.length : 0) || 0);
        const rightParamCount = (node.data.contextParams ? node.data.contextParams.length : 0) + 
                                (node.data.createdKeys ? node.data.createdKeys.length : 0);
        const maxCallouts = Math.max(leftParamCount, rightParamCount);
        const calloutsHeight = maxCallouts > 0 ? 
          (maxCallouts * LAYOUT_CONFIG.calloutHeight) + ((maxCallouts - 1) * LAYOUT_CONFIG.calloutSpacing) : 0;
        return Math.max(LAYOUT_CONFIG.baseContentHeight, calloutsHeight + 30);
      };

      const registerAnchors = useCallback((id, rects) => {
        if (!containerRef) {
          // Retry after a short delay if container ref is not ready
          setTimeout(() => registerAnchors(id, rects), 10);
          return;
        }

        // If CoordinateSystem is available, use it to compute container-local coords
        const cs = csRef.current;

        const makeAnchorFromElement = (el) => {
          if (!el) return null;
          if (cs && cs.elementToContainer) {
            const r = cs.elementToContainer(el);
            return { x: r.x + r.width / 2, y: r.y + r.height / 2, width: r.width, height: r.height };
          }
          // Fallback: measure via getBoundingClientRect
          const crect = containerRef.getBoundingClientRect();
          const rect = el.getBoundingClientRect();
          return { x: rect.left + rect.width / 2 - crect.left, y: rect.top + rect.height / 2 - crect.top, width: rect.width, height: rect.height };
        };

        const makeNodeFromElement = (el) => {
          if (!el) return null;
          if (cs && cs.elementToContainer) {
            const r = cs.elementToContainer(el);
            return { x: r.x, y: r.y, width: r.width, height: r.height };
          }
          const crect = containerRef.getBoundingClientRect();
          const rect = el.getBoundingClientRect();
          return { x: rect.left - crect.left, y: rect.top - crect.top, width: rect.width, height: rect.height };
        };

        const convArrFromEls = arr => (arr || []).map(makeAnchorFromElement).filter(Boolean);
        const convTopBottomArrFromEls = arr => (arr || []).map(makeAnchorFromElement).filter(Boolean);

        setAnchorMap(prev => ({
          ...prev,
          [id]: {
            top: convTopBottomArrFromEls(rects.top),
            bottom: convTopBottomArrFromEls(rects.bottom),
            left: convArrFromEls(rects.left),
            right: convArrFromEls(rects.right),
            node: makeNodeFromElement(rects.node)
          }
        }));
      }, [containerRef]);
      
      const handleZoomIn = () => {
        setZoomLevel(prev => Math.min(prev + 0.2, 2.0));
      };
      
      const handleZoomOut = () => {
        setZoomLevel(prev => Math.max(prev - 0.2, 0.4));
      };
      
      const handleResetZoom = () => {
        setZoomLevel(1);
        // also reset pan to origin
        setPan({ x: 0, y: 0 });
      };

      // Pointer-based panning (unconstrained)
      const handlePointerDown = (e) => {
        // Only left button
        if (e.button !== undefined && e.button !== 0) return;
        // Don't start panning when clicking interactive controls or nodes
        const tgt = e.target;
        if (tgt.closest && (tgt.closest('.custom-node') || tgt.closest('.zoom-controls') || tgt.closest('.pipeline-metadata'))) {
          return;
        }
        draggingRef.current = true;
        lastPointer.current = { x: e.clientX, y: e.clientY };
        // capture pointer for consistent move events
        try { e.target.setPointerCapture && e.target.setPointerCapture(e.pointerId); } catch (ex) {}
        if (wrapperRef.current) wrapperRef.current.style.cursor = 'grabbing';
        e.preventDefault();
      };

      const handlePointerMove = (e) => {
        if (!draggingRef.current) return;
        const dx = e.clientX - lastPointer.current.x;
        const dy = e.clientY - lastPointer.current.y;
        // Adjust pan inversely by zoom so movement feels natural
        setPan(prev => ({ x: prev.x + dx / zoomLevel, y: prev.y + dy / zoomLevel }));
        lastPointer.current = { x: e.clientX, y: e.clientY };
      };

      const stopDragging = (e) => {
        if (!draggingRef.current) return;
        draggingRef.current = false;
        try { e.target.releasePointerCapture && e.target.releasePointerCapture(e.pointerId); } catch (ex) {}
        if (wrapperRef.current) wrapperRef.current.style.cursor = 'grab';
      };

      // When containerRef becomes available, initialize or set the container on csRef
      React.useEffect(() => {
        if (!containerRef) return;
        if (!csRef.current && typeof window !== 'undefined' && window.CoordinateSystem) {
          csRef.current = new window.CoordinateSystem();
        }
        if (csRef.current) csRef.current.setContainer(containerRef);
      }, [containerRef]);

      // When zoom changes, let CoordinateSystem know (so logical<->container conversions work)
      React.useEffect(() => {
        if (csRef.current && csRef.current.setScale) csRef.current.setScale(zoomLevel);
      }, [zoomLevel]);



      useEffect(() => {
        // Only calculate after anchorMap has entries for nodes
        const ids = nodes.map(n => n.id);
        if (!ids.every(id => anchorMap[id] && anchorMap[id].node)) return;
        // Determine max widths by channel
        const dataWidths = nodes
          .filter(n => !(n.data.label.match(/Source|Sink/)))
          .map(n => anchorMap[n.id].node.width);
        const ctxWidths = nodes
          .filter(n => n.data.componentType === 'ContextProcessor')
          .map(n => anchorMap[n.id].node.width);
        const configWidths = nodes.map(n => {
          const configParams = n.data.pipelineConfigParams || [];
          const defaultParams = n.data.defaultParams || [];
          const sweepParams = n.data.sweepParams || [];
          const allParams = [...configParams, ...defaultParams, ...sweepParams];
          return allParams.length ? Math.max(...allParams.map(p => p.length)) : 80;
        });
        const maxData = Math.max(LAYOUT_CONFIG.nodeWidth, ...dataWidths);
        const maxCtx = Math.max(LAYOUT_CONFIG.nodeWidth, ...ctxWidths, 0);
        const configMax = Math.max(...configWidths, 80);
        setColWidths({
          data: maxData + 2 * LAYOUT_CONFIG.channelGap,
          config: configMax + LAYOUT_CONFIG.channelGap,
          context: maxCtx + 2 * LAYOUT_CONFIG.channelGap
        });
      }, [nodes, anchorMap]);

      // Compute channel centers based on measured column widths
      const totalWidth =
        colWidths.config + colWidths.data + colWidths.context + LAYOUT_CONFIG.channelGap * 4;
      const leftChannelCenter =
        LAYOUT_CONFIG.channelGap + colWidths.config + LAYOUT_CONFIG.channelGap + colWidths.data / 2;
      const rightChannelCenter =
        LAYOUT_CONFIG.channelGap +
        colWidths.config +
        LAYOUT_CONFIG.channelGap +
        colWidths.data +
        LAYOUT_CONFIG.channelGap +
        colWidths.context / 2;
      const centerPosition = (leftChannelCenter + rightChannelCenter) / 2;
      
      // Calculate positions maintaining original vertical order
      const nodePositions = {};
      let currentY = 60; // Start lower to reveal channel titles
      
      // Process all nodes in their original order, just split horizontally by type
      nodes.forEach((node, originalIndex) => {
        const componentType = node.data.componentType || '';
        let nodeType, xPos;
        
        // Determine node category and horizontal position using component_type (semantic metadata only)
        if (componentType === 'DataSource' || componentType === 'DataSink') {
          nodeType = 'source-sink';
          xPos = centerPosition;
        } else if (componentType === 'ContextProcessor') {
          nodeType = 'context-processor';
          xPos = rightChannelCenter;
        } else {
          // DataOperation and other data processing nodes
          nodeType = 'data-processor';
          xPos = leftChannelCenter;
        }
        
        const nodeHeight = calculateNodeHeight(node);
        
        nodePositions[node.id] = {
          x: xPos,
          y: currentY,
          type: nodeType,
          height: nodeHeight
        };
        
        currentY += nodeHeight + LAYOUT_CONFIG.verticalSpacing;
      });
      
      const totalHeight = currentY + 80;

      return (
        <div style={{ position: 'relative', width: '100%', height: '100%' }}>
          {/* Zoom controls */}
          <div className="zoom-controls">
            <button className="zoom-btn" onClick={handleZoomIn} title="Zoom In">+</button>
            <button className="zoom-btn" onClick={handleResetZoom} title="Reset Zoom">⌂</button>
            <button className="zoom-btn" onClick={handleZoomOut} title="Zoom Out">−</button>
          </div>

          <div className="custom-graph-wrapper" ref={wrapperRef}
            onPointerDown={handlePointerDown}
            onPointerMove={handlePointerMove}
            onPointerUp={stopDragging}
            onPointerLeave={stopDragging}
            style={{ cursor: 'grab' }}>
          <div
            ref={setContainerRef}
            className="custom-graph"
            style={{
              position: 'relative',
              width: totalWidth,
              height: '100%',
              minHeight: `${Math.max(totalHeight * zoomLevel, 500)}px`,
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoomLevel})`,
              transformOrigin: '0 0',
              gridTemplateColumns: `${colWidths.config}px ${colWidths.data}px ${colWidths.context}px`,
              columnGap: `${LAYOUT_CONFIG.channelGap}px`,
              paddingLeft: LAYOUT_CONFIG.channelGap,
              paddingRight: LAYOUT_CONFIG.channelGap
            }}>
          {/* Channel backgrounds - rendered within transform scope */}
          <div 
            className="channel-background config-channel" 
            style={{ 
              position: 'absolute',
              top: 10,
              left: LAYOUT_CONFIG.channelGap,
              width: colWidths.config, 
              height: totalHeight - 100,
              background: COLORS.configChannel.background,
              border: `2px dashed ${COLORS.configChannel.border}`,
              borderRadius: '12px',
              opacity: 0.6,
              zIndex: 0
            }}
          >
            <div className="channel-label">Config</div>
          </div>
          <div 
            className="channel-background data-channel" 
            style={{ 
              position: 'absolute',
              top: 10,
              left: colWidths.config + 2 * LAYOUT_CONFIG.channelGap, 
              width: colWidths.data,
              height: totalHeight - 100,
              background: COLORS.dataChannel.background,
              border: `2px dashed ${COLORS.dataChannel.border}`,
              borderRadius: '12px',
              opacity: 0.6,
              zIndex: 0
            }}
          >
            <div className="channel-label">Data Channel</div>
          </div>
          <div 
            className="channel-background context-channel" 
            style={{ 
              position: 'absolute',
              top: 10,
              left: colWidths.config + colWidths.data + 3 * LAYOUT_CONFIG.channelGap, 
              width: colWidths.context,
              height: totalHeight - 100,
              background: COLORS.contextChannel.background,
              border: `2px dashed ${COLORS.contextChannel.border}`,
              borderRadius: '12px',
              opacity: 0.6,
              zIndex: 0
            }}
          >
            <div className="channel-label">Context Channel</div>
          </div>
          
          {/* Render edges (arrows) - SVG with complete isolation */}
          <svg 
            style={{ 
              position: 'absolute', 
              top: 0, 
              left: 0, 
              width: `${totalWidth}px`, 
              height: `${totalHeight}px`, 
              zIndex: 10,
              pointerEvents: 'none',
              background: 'none',
              backgroundColor: 'transparent',
              border: 'none',
              margin: 0,
              padding: 0,
              overflow: 'visible'
            }}
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <marker id="arrow-black" markerWidth="6" markerHeight="5" refX="5" refY="2.5" orient="auto">
                <polygon points="0 0, 6 2.5, 0 5" fill="#000000" />
              </marker>
              <marker id="arrow-red" markerWidth="6" markerHeight="5" refX="5" refY="2.5" orient="auto">
                <polygon points="0 0, 6 2.5, 0 5" fill="#dc3545" />
              </marker>
            </defs>
            
            {edges.map(edge => {
              const sourcePos = nodePositions[edge.source];
              const targetPos = nodePositions[edge.target];
              
              if (!sourcePos || !targetPos) return null;

              // Calculate connection points directly from node positions
              const sourceNodeWidth = sourcePos.type === 'source-sink' ? 450 : LAYOUT_CONFIG.nodeWidth;
              const targetNodeWidth = targetPos.type === 'source-sink' ? 450 : LAYOUT_CONFIG.nodeWidth;
              
              // Start from bottom center of source node
              const startX = sourcePos.x;
              const startY = sourcePos.y + sourcePos.height;
              
              // End at top center of target node  
              const endX = targetPos.x;
              const endY = targetPos.y;

              // Use red styling for edges with data type incompatibility errors
              const hasError = edge.hasError || false;
              const strokeColor = hasError ? COLORS.error : "#48484a";
              const markerUrl = hasError ? "url(#arrow-red)" : "url(#arrow-black)";

              return (
                <line
                  key={edge.id}
                  x1={startX}
                  y1={startY}
                  x2={endX}
                  y2={endY}
                  stroke={strokeColor}
                  strokeWidth="1.5"
                  strokeDasharray="5,3"
                  markerEnd={markerUrl}
                />
              );
            })}
          </svg>
          
          {/* Render nodes */}
          {nodes.map(node => {
            const pos = nodePositions[node.id];
            if (!pos) return null;
            const isSelected = selectedNodeId === node.id;
            const traceAgg = traceAvailable && traceOverlayVisible && getTraceAggForNode ? getTraceAggForNode(node.id) : null;
            return (
              <PipelineNode
                key={node.id}
                node={node}
                pos={pos}
                isSelected={isSelected}
                onClick={onNodeClick}
                registerAnchors={registerAnchors}
                width={LAYOUT_CONFIG.nodeWidth}
                height={pos.height}
                traceAgg={traceAgg}
                traceOverlayVisible={traceOverlayVisible}
                getCalloutHoverText={getCalloutHoverText}
              />
            );
          })}
        </div>
      </div>
      </div>
      );
    }

    function App() {
      const [rfNodes, setRfNodes] = useState([]);
      const [rfEdges, setRfEdges] = useState([]);
      const [nodeInfo, setNodeInfo] = useState(null);
      const [nodeMap, setNodeMap] = useState({});
      const [pipelineInfo, setPipelineInfo] = useState(null); // Add pipeline info state
      const [error, setError] = useState(null);
      const [loading, setLoading] = useState(true);
      const [selectedNodeId, setSelectedNodeId] = useState(null);
      const [sidebarCollapsed, setSidebarCollapsed] = useState(true);

      // Mobile detection state
      const [isMobileView, setIsMobileView] = useState(isMobile());

      // Multi-run state
      const [runs, setRuns] = useState([]);
      const [currentRun, setCurrentRun] = useState(null);

      // Run-space state
      const [runSpaces, setRunSpaces] = useState([]);
      const [hasRunsWithoutRunSpace, setHasRunsWithoutRunSpace] = useState(false);
      const [selectedRunSpace, setSelectedRunSpace] = useState('__all__');
      const [runSpaceDetails, setRunSpaceDetails] = useState(null);
      
  // Scroll preservation: detail panel or window
  const detailPanelRef = useRef(null);
  const traceSectionRef = useRef(null);
  const scrollRestoreRef = useRef({ mode: null, detailTop: 0, windowTop: 0, traceLocked: false, _raf1: null, _raf2: null });

      // Trace overlay state
      const [traceAvailable, setTraceAvailable] = useState(false);
      const [traceMeta, setTraceMeta] = useState(null);
      const [traceSummary, setTraceSummary] = useState(new Map());
      const [traceOverlayVisible, setTraceOverlayVisible] = useState(true);
      const [traceFqnToUuid, setTraceFqnToUuid] = useState(new Map());
      const [traceLabelToUuid, setTraceLabelToUuid] = useState(new Map());
      const [nodeTraceEvents, setNodeTraceEvents] = useState(new Map());
      const [metadataPanelOpen, setMetadataPanelOpen] = useState(false);
      
      // Pipeline configuration data state (for metadata display)
      const [pipelineData, setPipelineData] = useState(null);
      
      // Identity states (SPLIT: inspection vs trace)
      const [inspectionIdentity, setInspectionIdentity] = useState(null);
      const [traceIdentity, setTraceIdentity] = useState(null);

      // Resizable panels
      const sidebar = useResizable(400, 200, 600);
  const details = useResizableRight(700, 200, 10000);

      // Wrap fetch helper for trace endpoints
      const traceFetch = (path) => {
        // In export mode (file:// or mocked fetch), just use the path directly
        if (window.location.protocol === 'file:' || window.TRACE_DATA) {
          const url = path + (currentRun ? `?run=${encodeURIComponent(currentRun)}` : '');
          return fetch(url);
        }
        // In server mode, construct proper URL
        const u = new URL(path, window.location.origin);
        if (currentRun) u.searchParams.set('run', currentRun);
        return fetch(u.toString());
      };

      useEffect(() => {
        // Load run-space launches if endpoint exists
        fetch('/api/runspace/launches')
          .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
          .then(data => {
            setRunSpaces(data.launches || []);
            setHasRunsWithoutRunSpace(data.has_runs_without_runspace || false);
            
            // Check URL for run-space deep-link
            const urlParams = new URLSearchParams(window.location.search);
            const launchParam = urlParams.get('launch');
            const attemptParam = urlParams.get('attempt');
            const noneParam = urlParams.get('none');

            if (noneParam === 'true') {
              setSelectedRunSpace('__none__');
            } else if (launchParam && attemptParam) {
              const matchingLaunch = (data.launches || []).find(
                l => l.launch_id === launchParam && l.attempt === parseInt(attemptParam)
              );
              if (matchingLaunch) {
                setSelectedRunSpace(JSON.stringify({
                  launch: matchingLaunch.launch_id,
                  attempt: matchingLaunch.attempt
                }));
              }
            }
          })
          .catch(err => {
            console.log('Run-space endpoint unavailable:', err.message);
            setRunSpaces([]);
            setHasRunsWithoutRunSpace(false);
          });
      }, []);

      // Load runs based on run-space selection
      const loadRunsForRunSpace = useCallback((runSpaceValue) => {
        let url = '/api/runspace/runs';
        
        if (runSpaceValue === '__none__') {
          url += '?none=true';
        } else if (runSpaceValue !== '__all__') {
          try {
            const { launch, attempt } = JSON.parse(runSpaceValue);
            url += `?launch_id=${encodeURIComponent(launch)}&attempt=${attempt}`;
          } catch (e) {
            console.error('Failed to parse run-space value:', e);
            url = '/api/runspace/runs';
          }
        }

        fetch(url)
          .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
          .then(data => {
            const runsList = data.runs || [];
            setRuns(runsList);
            
            // Preserve current run if it's still in the list, otherwise select first
            const urlParams = new URLSearchParams(window.location.search);
            const preRun = urlParams.get('run');
            const chosen = (preRun && runsList.find(x => x.run_id === preRun)) ? preRun
                          : (runsList.length ? runsList[0].run_id : null);
            setCurrentRun(chosen);
          })
          .catch(err => {
            console.error('Failed to load runs for run-space:', err.message);
            setRuns([]);
            setCurrentRun(null);
          });
      }, []);

      // Update runs when run-space selection changes
      useEffect(() => {
        if (runSpaces.length > 0 || hasRunsWithoutRunSpace) {
          loadRunsForRunSpace(selectedRunSpace);
        }
      }, [selectedRunSpace, runSpaces, hasRunsWithoutRunSpace, loadRunsForRunSpace]);

      // Load run-space details when selection changes
      useEffect(() => {
        if (selectedRunSpace === '__all__' || selectedRunSpace === '__none__') {
          setRunSpaceDetails(null);
          return;
        }

        try {
          const { launch, attempt } = JSON.parse(selectedRunSpace);
          fetch(`/api/runspace/launch_details?launch_id=${encodeURIComponent(launch)}&attempt=${attempt}`)
            .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
            .then(details => {
              setRunSpaceDetails(details);
            })
            .catch(err => {
              console.error('Failed to load run-space details:', err);
              setRunSpaceDetails(null);
            });
        } catch (e) {
          console.error('Failed to parse run-space value:', e);
          setRunSpaceDetails(null);
        }
      }, [selectedRunSpace]);

      useEffect(() => {
        // Load runs if endpoint exists; in export mode this may throw and we simply proceed without runs.
        // Only load directly if run-space endpoint is not available (backward compatibility)
        if (runSpaces.length === 0 && !hasRunsWithoutRunSpace) {
          fetch('/api/runs')
            .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
            .then(list => {
              setRuns(list || []);
              // select from URL ?run=..., else first item
              const urlParams = new URLSearchParams(window.location.search);
              const pre = urlParams.get('run');
              const preNode = urlParams.get('node');
              const chosen = (pre && (list || []).find(x => x.run_id === pre)) ? pre
                            : ((list && list.length) ? list[0].run_id : null);
              setCurrentRun(chosen);
              if (chosen && pre !== chosen) {
                const u = new URL(window.location.href);
                u.searchParams.set('run', chosen);
                if (preNode) u.searchParams.set('node', preNode);
                window.history.replaceState({}, '', u.toString());
              }
              if (preNode) setSelectedNodeId(preNode);
            })
            .catch(err => {
              // No runs endpoint (export) or server without runs; continue without runs
              console.log('Runs endpoint unavailable or empty:', err.message);
              setRuns([]);
              setCurrentRun(null);
            });
        }
      }, [runSpaces, hasRunsWithoutRunSpace]);

      useEffect(() => {
        console.log('Loading pipeline data...');
        
        fetch('/api/pipeline')
          .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
          })
          .then(data => {
            console.log('Pipeline data loaded:', data);
            
            // Store complete pipeline data for metadata display
            setPipelineData(data);
            
            // Extract inspection identity (YAML SSOT only)
            if (data && data.identity) {
              setInspectionIdentity(data.identity);
            }
            
            // Store pipeline-level information
            setPipelineInfo(data.pipeline || { has_errors: false, pipeline_errors: [], required_context_keys: [] });
            
            const map = {};
            const n = data.nodes.map((node, idx) => {
              map[node.id] = node;
              
              // Create parameter data with source information for visual display
              const configParams = [];
              let configParamValues = {};
              const defaultParams = [];
              let defaultParamValues = {};
              
              // Parameters from pipeline configuration
              if (node.parameter_resolution && node.parameter_resolution.from_pipeline_config) {
                configParams.push(...Object.keys(node.parameter_resolution.from_pipeline_config));
                configParamValues = node.parameter_resolution.from_pipeline_config;
              }
              
              // Parameters from processor defaults
              if (node.parameter_resolution && node.parameter_resolution.from_processor_defaults) {
                defaultParams.push(...Object.keys(node.parameter_resolution.from_processor_defaults));
                defaultParamValues = node.parameter_resolution.from_processor_defaults;
              }
              
              // Extract sweep parameters from preprocessor_metadata
              const sweepParams = [];
              let sweepParamExpressions = {};
              let preprocessorView = null;
              if (node.preprocessor_metadata && 
                  node.preprocessor_metadata.type === 'derive.parameter_sweep' &&
                  node.preprocessor_metadata.param_expressions) {
                sweepParams.push(...Object.keys(node.preprocessor_metadata.param_expressions));
                sweepParamExpressions = node.preprocessor_metadata.param_expressions;
                preprocessorView = node.preprocessor_view || null;
              }
              
              return {
                id: String(node.id),
                data: {
                  label: node.label,
                  componentType: node.component_type || '',
                  inputType: node.input_type || '',
                  outputType: node.output_type || '',
                  pipelineConfigParams: configParams,
                  configParamValues: configParamValues,
                  defaultParams: defaultParams,
                  defaultParamValues: defaultParamValues,
                  sweepParams: sweepParams,
                  sweepParamExpressions: sweepParamExpressions,
                  preprocessorView: preprocessorView,
                  contextParams: node.contextParams || [],
                  createdKeys: node.created_keys || [],
                  errors: node.errors || [], // Include error information
                  hasErrors: (node.errors && node.errors.length > 0), // Add convenient flag
                },
                position: { x: idx * 200, y: 100 },
                type: 'default'
              };
            });
            
            // Check for data type incompatibility errors between consecutive nodes
            const e = data.edges.map(edge => {
              const sourceNode = data.nodes.find(n => n.id === edge.source);
              const targetNode = data.nodes.find(n => n.id === edge.target);
              const hasDataTypeError = targetNode && targetNode.errors && 
                targetNode.errors.some(err => err.includes('Data type incompatibility'));
              
              return { 
                id: edge.source + '-' + edge.target, 
                source: String(edge.source), 
                target: String(edge.target),
                type: 'default',
                hasError: hasDataTypeError // Mark edges with data type incompatibility
              };
            });
            
            setRfNodes(n); 
            setRfEdges(e); 
            setNodeMap(map);
            setLoading(false);
            
            // Load trace data. If currentRun is set we'll scope by run; otherwise
            // try once (exported HTML has inline TRACE_DATA mocks without runs).
            loadTraceData();
          })
          .catch(err => {
            console.error('Error loading pipeline:', err);
            setError(err.message);
            setLoading(false);
          });
      }, []); // Load pipeline only once on mount

      // Separate effect to reload trace data when currentRun changes
      useEffect(() => {
        // Only reload trace if we already have pipeline data
        if (rfNodes.length > 0) {
          loadTraceData();
        }
      }, [currentRun]);

      const loadTraceData = () => {
        // Try to load trace data if available
        traceFetch('/api/trace/meta')
          .then(r => {
            if (r.ok) return r.json();
            throw new Error('No trace data');
          })
          .then(meta => {
            console.log('Trace metadata loaded:', meta);
            setTraceMeta(meta);
            setTraceAvailable(true);
            
            // Extract trace identity (Runtime SSOT only)
            if (meta) {
              setTraceIdentity({
                identity: {
                  run_id: meta.run_id,
                  pipeline_id: meta.pipeline_id,
                  semantic_id: meta.semantic_id,
                  config_id: meta.config_id
                },
                run_space: {
                  launch_id: meta.run_space_launch_id,
                  attempt: meta.run_space_attempt,
                  index: meta.run_space_index,
                  context: meta.run_space_context,
                  spec_id: meta.run_space_spec_id,
                  inputs_id: meta.run_space_inputs_id
                },
                timing: {
                  started_at: meta.started_at,
                  ended_at: meta.ended_at
                }
              });
            }
            
            // Store FQN to UUID mappings
            if (meta.node_mappings && meta.node_mappings.fqn_to_uuid) {
              const mappings = new Map();
              Object.entries(meta.node_mappings.fqn_to_uuid).forEach(([fqn, uuid]) => {
                mappings.set(fqn, uuid);
              });
              setTraceFqnToUuid(mappings);
            }
            
            // Load trace summary
            return traceFetch('/api/trace/summary');
          })
          .then(r => {
            if (r.ok) return r.json();
            throw new Error('Failed to load trace summary');
          })
          .then(summary => {
            console.log('Trace summary loaded:', summary);
            const summaryMap = new Map();
            if (summary.nodes) {
              Object.entries(summary.nodes).forEach(([nodeUuid, agg]) => {
                summaryMap.set(nodeUuid, agg);
              });
            }
            setTraceSummary(summaryMap);
            
            // Load label to UUID mapping
            return traceFetch('/api/trace/mapping');
          })
          .then(r => {
            if (r.ok) return r.json();
            throw new Error('Failed to load trace mapping');
          })
          .then(mapping => {
            console.log('Trace label mapping loaded:', mapping);
            const labelMap = new Map();
            Object.entries(mapping.label_to_uuid || {}).forEach(([label, uuid]) => {
              labelMap.set(label, uuid);
            });
            setTraceLabelToUuid(labelMap);
          })
          .catch(err => {
            console.log('No trace data available:', err.message);
            setTraceAvailable(false);
          });
      };

      // Mobile detection resize listener
      useEffect(() => {
        const handleResize = () => setIsMobileView(isMobile());
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
      }, []);

      // Validate and sync ?node= from URL against nodeMap once available
      useEffect(() => {
        if (!nodeMap || Object.keys(nodeMap).length === 0) return;
        const urlParams = new URLSearchParams(window.location.search);
        const urlNode = urlParams.get('node');
        if (urlNode && nodeMap[parseInt(urlNode)]) {
          // ensure state reflects URL
          if (selectedNodeId !== urlNode) setSelectedNodeId(urlNode);
          setNodeInfo(nodeMap[parseInt(urlNode)]);
        } else if (urlNode && !nodeMap[parseInt(urlNode)]) {
          // remove invalid node from URL
          const u = new URL(window.location.href);
          u.searchParams.delete('node');
          window.history.replaceState({}, '', u.toString());
        }
      }, [nodeMap]);

      // Restore scroll position after trace data loads/layout settles
      useEffect(() => {
        if (traceLabelToUuid.size === 0) return;
        const restore = () => {
          const { mode, detailTop, windowTop } = scrollRestoreRef.current || {};
          if (!mode) return;
          if (mode === 'detail' && detailPanelRef.current) {
            detailPanelRef.current.scrollTop = detailTop;
          } else if (mode === 'window') {
            window.scrollTo({ top: windowTop });
          }
          // Do not unlock height here; a dedicated effect will animate height to the new content when ready
          // Keep traceLocked until animation completes
        };
        const raf1 = requestAnimationFrame(() => {
          const raf2 = requestAnimationFrame(restore);
          scrollRestoreRef.current._raf2 = raf2;
        });
        scrollRestoreRef.current._raf1 = raf1;
        return () => {
          if (scrollRestoreRef.current._raf1) cancelAnimationFrame(scrollRestoreRef.current._raf1);
          if (scrollRestoreRef.current._raf2) cancelAnimationFrame(scrollRestoreRef.current._raf2);
        };
      }, [traceLabelToUuid, currentRun]);

      // Animate the trace section height to match new content once ready (or after a short delay)
      useEffect(() => {
        if (!scrollRestoreRef.current.traceLocked) return;
        const traceEl = traceSectionRef.current;
        if (!traceEl) return;

        // consider content ready when we have events for the selected node in the new run
        let ready = false;
        const now = Date.now();
        const deadline = scrollRestoreRef.current.unlockDeadline || 0;
        try {
          const currentNode = nodeMap && selectedNodeId ? nodeMap[parseInt(selectedNodeId)] : null;
          if (currentNode && traceLabelToUuid && traceLabelToUuid.size) {
            const nodeUuid = currentNode.node_uuid || traceLabelToUuid.get(currentNode.label);
            const runMap = nodeTraceEvents.get(currentRun) || new Map();
            if (nodeUuid && runMap.has(nodeUuid)) {
              const evs = runMap.get(nodeUuid) || [];
              ready = evs.length > 0;
            }
          }
        } catch (_) {}

        if (!ready && now < deadline) {
          const t = setTimeout(() => {
            // retrigger effect by a layout read
            if (traceSectionRef.current) void traceSectionRef.current.offsetHeight;
          }, 80);
          return () => clearTimeout(t);
        }

        // Animate to the new scrollHeight (or current content height after deadline)
        const newH = traceEl.scrollHeight;
        requestAnimationFrame(() => {
          traceEl.style.height = `${Math.max(0, Math.floor(newH))}px`;
        });

        const cleanup = () => {
          traceEl.style.height = '';
          traceEl.style.overflow = '';
          traceEl.style.transition = '';
          scrollRestoreRef.current.traceLocked = false;
          scrollRestoreRef.current.unlockDeadline = 0;
          // clear scroll restoration state now that animation is done
          scrollRestoreRef.current.mode = null;
          scrollRestoreRef.current.detailTop = 0;
          scrollRestoreRef.current.windowTop = 0;
        };

        // Fallback timeout in case transitionend doesn't fire
        const endTimer = setTimeout(() => {
          if (scrollRestoreRef.current.traceLocked) cleanup();
        }, 700);
        traceEl.addEventListener('transitionend', cleanup, { once: true });
        return () => clearTimeout(endTimer);
  }, [nodeTraceEvents, traceLabelToUuid, selectedNodeId, currentRun]);

      // Function to load trace events for a specific node
    const loadNodeTraceEvents = useCallback((nodeId) => {
  if (!traceAvailable || !nodeMap) return;
        
        // Find the UUID for this node using label mapping
        const nodeInfo = nodeMap[parseInt(nodeId)];
        if (!nodeInfo) return;
        
  // Prefer node_uuid directly if present
  const directUuid = nodeInfo.node_uuid;
  const label = nodeInfo.label;
  const nodeUuid = directUuid || (traceLabelToUuid.size ? traceLabelToUuid.get(label) : null);
        
        if (!nodeUuid) {
          console.log(`No UUID mapping found for node label: ${label}`);
          return;
        }
        
  // Check if we already have events for this node in the current run
  const existingRunMap = nodeTraceEvents.get(currentRun) || new Map();
  if (existingRunMap.has(nodeUuid)) return;
        
        console.log(`Loading trace events for node ${nodeId} (label: ${label}, UUID: ${nodeUuid})`);
        
        traceFetch(`/api/trace/node/${nodeUuid}`)
          .then(r => {
            if (r.ok) return r.json();
            throw new Error(`Failed to load events for node ${nodeUuid}`);
          })
          .then(response => {
            const rawEvents = response.events || [];
            // Wrap raw SER dicts for frontend compatibility: {status, _raw: ser_dict}
            const events = rawEvents.map(ser => ({
              status: ser.status || 'unknown',
              _raw: ser
            }));
            console.log(`Loaded ${events.length} trace events for node ${nodeId}`);
            setNodeTraceEvents(prev => {
              const outer = new Map(prev);
              const runMap = new Map(outer.get(currentRun) || []);
              runMap.set(nodeUuid, events);
              outer.set(currentRun, runMap);
              return outer;
            });
          })
          .catch(err => {
            console.log(`Failed to load trace events for node ${nodeId}:`, err.message);
          });
      }, [traceAvailable, traceLabelToUuid, nodeMap, nodeTraceEvents, traceFetch, currentRun]);

      // Load trace events when a node is selected
      useEffect(() => {
        if (selectedNodeId && traceAvailable) {
          loadNodeTraceEvents(selectedNodeId);
        }
      }, [selectedNodeId, traceAvailable, loadNodeTraceEvents]);

      // Helper function to get trace aggregation for a node
      const getTraceAggForNode = (nodeId) => {
        if (!traceAvailable || !nodeMap[parseInt(nodeId)]) return null;
        
        const node = nodeMap[parseInt(nodeId)];
        
        // Try to find trace data by node_uuid if available
        if (node.node_uuid) {
          return traceSummary.get(node.node_uuid);
        }
        
        // Fallback: try to find by label matching with FQN patterns
        const label = node.label;
        if (label && traceFqnToUuid.size > 0) {
          // Try exact matches first
          for (const [fqn, nodeUuid] of traceFqnToUuid.entries()) {
            // Extract component name from FQN
            const parts = fqn.split(":");
            let componentName;
            if (parts.length >= 2) {
              // For sweep/slicer style FQNs, take the middle part
              componentName = parts[1];
            } else {
              // For direct FQNs, take the whole thing
              componentName = fqn;
            }
            
            if (componentName === label) {
              return traceSummary.get(nodeUuid);
            }
          }
          
          // Try partial matches
          for (const [fqn, nodeUuid] of traceFqnToUuid.entries()) {
            if (fqn.includes(label)) {
              return traceSummary.get(nodeUuid);
            }
          }
        }
        
        return null;
      };

      // Compute a user-friendly value for a callout hover from SER trace.
      // type: 'param' for any parameter callout (config/default/context), 'sweep' for sweep parameters, 'created' for produced keys.
      const getCalloutHoverText = useCallback((nodeId, type, name) => {
        try {
          if (!name) return undefined;
          
          // Handle sweep parameters: show the expression defined at configuration
          if (type === 'sweep') {
            const rfNode = rfNodes.find(n => n.id === nodeId);
            if (!rfNode || !rfNode.data || !rfNode.data.sweepParamExpressions) return undefined;
            
            // Just return the expression string directly—no parsing, no conversion
            if (rfNode.data.preprocessorView && 
                rfNode.data.preprocessorView.param_expressions && 
                rfNode.data.preprocessorView.param_expressions[name] &&
                rfNode.data.preprocessorView.param_expressions[name].expr) {
              return rfNode.data.preprocessorView.param_expressions[name].expr;
            }
            
            return '<expression (source not available)>';
          }
          
          // Handle default parameters: show the default value from configuration
          if (type === 'default') {
            const rfNode = rfNodes.find(n => n.id === nodeId);
            if (!rfNode || !rfNode.data || !rfNode.data.defaultParamValues) return undefined;
            const defVal = rfNode.data.defaultParamValues[name];
            if (defVal === undefined) return undefined;
            
            // Format the default value nicely
            if (defVal && typeof defVal === 'object') {
              if (defVal.repr) return String(defVal.repr);
              try { return JSON.stringify(defVal); } catch (e) { return String(defVal); }
            }
            // Preserve float representation for numbers
            if (typeof defVal === 'number') {
              const repr = formatNumber(defVal);
              return repr.length > 40 ? repr.substring(0, 40) + '...' : repr;
            }
            try { 
              const repr = String(defVal);
              return repr.length > 40 ? repr.substring(0, 40) + '...' : repr;
            } catch (e) { 
              return ''; 
            }
          }
          
          // For other types, use trace data
          if (!traceAvailable) return undefined;
          const currentNode = nodeMap[parseInt(nodeId)];
          if (!currentNode) return undefined;

          // Resolve nodeUuid similarly to details section
          let nodeUuid = null;
          if (currentNode.node_uuid) nodeUuid = currentNode.node_uuid;
          if (!nodeUuid && traceLabelToUuid && currentNode.label) {
            nodeUuid = traceLabelToUuid.get(currentNode.label);
          }
          if (!nodeUuid && traceMeta && traceMeta.node_mappings && traceMeta.node_mappings.fqn_to_uuid) {
            for (const [fqn, uuid] of Object.entries(traceMeta.node_mappings.fqn_to_uuid)) {
              if (currentNode.label && fqn.includes(currentNode.label)) { nodeUuid = uuid; break; }
            }
          }
          if (!nodeUuid) return undefined;

          const runMap = nodeTraceEvents.get(currentRun) || new Map();
          const nodeEvents = runMap.get(nodeUuid) || [];
          if (!nodeEvents.length) return undefined;

          // Prefer 'succeeded', else 'error', else first
          let chosen = null;
          for (const ev of nodeEvents) { if (ev.status === 'succeeded') chosen = ev; }
          if (!chosen) { for (const ev of nodeEvents) { if (ev.status === 'error') { chosen = ev; break; } } }
          if (!chosen) chosen = nodeEvents[0];
          const rawData = chosen && chosen._raw;
          if (!rawData || rawData.record_type !== 'ser') return undefined;

          if (type === 'param') {
            // First try to get from node data (config parameters)
            const rfNode = rfNodes.find(n => n.id === nodeId);
            if (rfNode && rfNode.data && rfNode.data.configParamValues) {
              const configVal = rfNode.data.configParamValues[name];
              if (configVal !== undefined) {
                if (configVal && typeof configVal === 'object') {
                  if (configVal.repr) return String(configVal.repr);
                  try { return JSON.stringify(configVal); } catch (e) { return String(configVal); }
                }
                if (typeof configVal === 'number') {
                  const repr = formatNumber(configVal);
                  return repr.length > 40 ? repr.substring(0, 40) + '...' : repr;
                }
                try {
                  const repr = String(configVal);
                  return repr.length > 40 ? repr.substring(0, 40) + '...' : repr;
                } catch (e) {
                  return '';
                }
              }
            }
            
            // Fallback to trace data
            if (!rawData.processor || !rawData.processor.parameters) return undefined;
            let pval = rawData.processor.parameters[name];
            if (pval === undefined) pval = rawData.processor.parameters[name && name.toString ? name.toString() : name];
            if (pval === undefined) return undefined;
            if (pval && typeof pval === 'object') {
              if (pval.repr) return String(pval.repr);
              try { return JSON.stringify(pval); } catch (e) { return String(pval); }
            }
            // Preserve float representation for numbers
            if (typeof pval === 'number') {
              const repr = formatNumber(pval);
              return repr.length > 40 ? repr.substring(0, 40) + '...' : repr;
            }
            try { 
              const repr = String(pval);
              return repr.length > 40 ? repr.substring(0, 40) + '...' : repr;
            } catch (e) { 
              return ''; 
            }
          }

          if (type === 'created') {
            // Look for created keys in context_delta.key_summaries
            const keySummaries = (rawData.context_delta && rawData.context_delta.key_summaries) || {};
            const s = keySummaries[name] || keySummaries[name && name.toString ? name.toString() : name];
            if (s && (s.repr || s.sample || s.preview)) return String(s.repr || s.sample || s.preview);
            return undefined;
          }

          return undefined;
        } catch (err) {
          return undefined;
        }
      }, [traceAvailable, nodeMap, traceMeta, traceLabelToUuid, nodeTraceEvents, currentRun, rfNodes]);

      const onNodeClick = (_, node) => {
        console.log('Node clicked:', node);
        const nodeData = nodeMap[parseInt(node.id)];
        setNodeInfo(nodeData);
        setSelectedNodeId(node.id);
        // Update URL with node selection
        const u = new URL(window.location.href);
        u.searchParams.set('node', node.id);
        window.history.replaceState({}, '', u.toString());
      };

      if (error) {
        return (
          <div className="error">
            <h2>Error loading pipeline</h2>
            <p>{error}</p>
            <p>Check the browser console for more details.</p>
          </div>
        );
      }

      if (loading) {
        return <div className="loading">Loading pipeline...</div>;
      }

      return (
        <div style={{
          display: 'flex', 
          flexDirection: isMobileView ? 'column' : 'row',
          height: isMobileView ? 'auto' : '100%', 
          width: '100%',
          minHeight: isMobileView ? '100vh' : 'auto'
        }}>
          <div id="sidebar" style={{ 
            width: isMobileView ? '100%' : (sidebarCollapsed ? '40px' : `${sidebar.width}px`), 
            overflow: 'hidden', 
            transition: sidebarCollapsed ? 'width 0.3s ease' : 'none',
            borderRight: isMobileView ? 'none' : '1px solid #ccc',
            borderBottom: isMobileView ? '1px solid #ccc' : 'none',
            padding: sidebarCollapsed ? '4px 0' : '4px',
            position: 'relative',
            maxHeight: isMobileView ? '200px' : 'auto',
            order: isMobileView ? 1 : 'unset'
          }} className={sidebarCollapsed ? 'collapsed' : ''}>
            {!sidebarCollapsed && !isMobileView && (
              <div 
                className={`resize-handle resize-handle-right ${sidebar.isResizing ? 'resizing' : ''}`}
                onMouseDown={sidebar.handleMouseDown}
              />
            )}
            <h3 
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              style={{
                margin: '10px 5px', 
                color: '#5856d6',
                cursor: 'pointer',
                writingMode: (sidebarCollapsed && !isMobileView) ? 'vertical-rl' : 'horizontal-tb',
                textAlign: 'center',
                transform: (sidebarCollapsed && !isMobileView) ? 'rotate(180deg)' : 'none',
                whiteSpace: 'nowrap',
                userSelect: 'none',
                fontSize: isMobileView ? '16px' : 'inherit',
                padding: isMobileView ? '10px' : '0'
              }}
            >
              Pipeline Node List
            </h3>
            
            {!sidebarCollapsed && (
              <div>
                {/* Data Processing Channel */}
                <div style={{ marginBottom: '15px' }}>
              <h4 style={{ 
                margin: '5px', 
                padding: '5px 8px', 
                background: '#e8f4fd', 
                borderLeft: '4px solid #007aff',
                fontSize: '12px',
                color: '#007aff',
                fontWeight: 'bold'
              }}>
                DATA PROCESSING
              </h4>
              {Object.values(nodeMap)
                .filter(n => {
                  // Use component_type semantic metadata only (no name-based fallbacks)
                  const isSourceSink = n.component_type === 'DataSource' || n.component_type === 'DataSink';
                  const isContextProcessor = n.component_type === 'ContextProcessor';
                  return !isSourceSink && !isContextProcessor;
                })
                .map(n => (
                <div 
                  key={n.id} 
                  onClick={() => {
                    setNodeInfo(n);
                    setSelectedNodeId(String(n.id));
                  }} 
                  className={`node-item ${selectedNodeId === String(n.id) ? 'selected' : ''}`}
                  style={{
                    backgroundColor: selectedNodeId === String(n.id) ? '#c7e0f4' : '#f8fbff',
                    borderLeftColor: '#007aff'
                  }}
                >
                  <div style={{ fontWeight: 'bold' }}>{n.label}</div>
                  <div style={{ fontSize: '11px', color: '#007aff' }}>{n.component_type}</div>
                </div>
              ))}
            </div>
            
            {/* Context Processing Channel */}
            <div style={{ marginBottom: '15px' }}>
              <h4 style={{ 
                margin: '5px', 
                padding: '5px 8px', 
                background: '#f5e6ff', 
                borderLeft: '4px solid #af52de',
                fontSize: '12px',
                color: '#af52de',
                fontWeight: 'bold'
              }}>
                CONTEXT PROCESSING
              </h4>
              {Object.values(nodeMap)
                .filter(n => 
                  n.component_type === 'ContextProcessor'
                )
                .map(n => (
                <div 
                  key={n.id} 
                  onClick={() => {
                    setNodeInfo(n);
                    setSelectedNodeId(String(n.id));
                  }} 
                  className={`node-item ${selectedNodeId === String(n.id) ? 'selected' : ''}`}
                  style={{
                    backgroundColor: selectedNodeId === String(n.id) ? '#e1bee7' : '#faf8ff',
                    borderLeftColor: '#7b1fa2'
                  }}
                >
                  <div style={{ fontWeight: 'bold' }}>{n.label}</div>
                  <div style={{ fontSize: '11px', color: '#7b1fa2' }}>{n.component_type}</div>
                </div>
              ))}
            </div>
            
            {/* I/O Nodes */}
            <div style={{ marginBottom: '15px' }}>
              <h4 style={{ 
                margin: '5px', 
                padding: '5px 8px', 
                background: '#ffebee', 
                borderLeft: '4px solid #d32f2f',
                fontSize: '12px',
                color: '#d32f2f',
                fontWeight: 'bold'
              }}>
                INPUT/OUTPUT
              </h4>
              {Object.values(nodeMap)
                .filter(n => 
                  n.component_type === 'DataSource' || n.component_type === 'DataSink'
                )
                .map(n => (
                <div 
                  key={n.id} 
                  onClick={() => {
                    setNodeInfo(n);
                    setSelectedNodeId(String(n.id));
                  }} 
                  className={`node-item ${selectedNodeId === String(n.id) ? 'selected' : ''}`}
                  style={{
                    backgroundColor: selectedNodeId === String(n.id) ? '#ffcdd2' : '#fff8f8',
                    borderLeftColor: '#ff3b30'
                  }}
                >
                  <div style={{ fontWeight: 'bold' }}>{n.label}</div>
                  <div style={{ fontSize: '11px', color: '#ff3b30' }}>{n.component_type}</div>
                </div>
              ))}
            </div>
              </div>
            )}
          </div>
          <div id="graph" style={{
            flex: isMobileView ? 'none' : '1',
            order: isMobileView ? 2 : 'unset',
            minHeight: isMobileView ? '400px' : 'auto',
            overflowX: isMobileView ? 'auto' : 'visible'
          }}>
            <div style={{ padding: '10px', borderBottom: '1px solid #ddd', background: '#f8f9fa' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <h3 style={{ margin: '0', color: '#5856d6' }}>Semantiva Studio Lite - Dual-Channel Pipeline Inspection</h3>
                {pipelineInfo && pipelineInfo.has_errors && (
                  <span style={{ 
                    color: '#dc3545', 
                    fontWeight: 'bold', 
                    fontSize: '16px',
                    background: '#f8d7da',
                    padding: '4px 8px',
                    borderRadius: '4px',
                    border: '1px solid #dc3545'
                  }}>
                    Invalid Pipeline
                  </span>
                )}
                {/* Run-Space selector and Run selector - stacked vertically on the right */}
                {traceAvailable && (runSpaces.length > 0 || hasRunsWithoutRunSpace || (traceMeta && runs && runs.length > 1)) && (
                  <div style={{ marginLeft: 'auto', display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'flex-end' }}>
                    {/* Run-Space selector */}
                    {(runSpaces.length > 0 || hasRunsWithoutRunSpace) && (
                      <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
                        <label style={{fontSize:'12px', opacity:0.7, fontWeight:'500'}}>Run-Space:</label>
                        <select
                          value={selectedRunSpace}
                          onChange={(e) => {
                            const value = e.target.value;
                            setSelectedRunSpace(value);
                            
                            // Update URL params
                            const u = new URL(window.location.href);
                            if (value === '__all__') {
                              u.searchParams.delete('launch');
                              u.searchParams.delete('attempt');
                              u.searchParams.delete('none');
                            } else if (value === '__none__') {
                              u.searchParams.delete('launch');
                              u.searchParams.delete('attempt');
                              u.searchParams.set('none', 'true');
                            } else {
                              try {
                                const { launch, attempt } = JSON.parse(value);
                                u.searchParams.set('launch', launch);
                                u.searchParams.set('attempt', String(attempt));
                                u.searchParams.delete('none');
                              } catch (e) {
                                console.error('Failed to parse run-space value:', e);
                              }
                            }
                            u.searchParams.delete('run'); // Clear run selection when changing run-space
                            window.history.replaceState({}, '', u.toString());
                          }}
                          style={{fontSize:'13px', padding:'4px 8px', fontWeight:'500', maxWidth: '300px'}}
                        >
                          <option value="__all__">All</option>
                          {hasRunsWithoutRunSpace && <option value="__none__">None</option>}
                          {runSpaces.map(rs => (
                            <option 
                              key={`${rs.launch_id}-${rs.attempt}`} 
                              value={JSON.stringify({ launch: rs.launch_id, attempt: rs.attempt })}
                            >
                              {rs.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                    {/* Run selector */}
                    {traceMeta && runs && runs.length > 1 && (
                      <div style={{display:'flex', gap:'8px', alignItems:'center'}}>
                        <label style={{fontSize:'12px', opacity:0.7, fontWeight:'500'}}>Run:</label>
                      <select
                        value={currentRun || ''}
                        onChange={(e) => {
                          // Save current scroll position (detail panel if scrollable, else window)
                          const el = detailPanelRef.current;
                          const isDetailScrollable = !!(el && (el.scrollHeight - el.clientHeight > 4));
                          if (isDetailScrollable && el) {
                            scrollRestoreRef.current = { mode: 'detail', detailTop: el.scrollTop, windowTop: window.scrollY };
                          } else {
                            scrollRestoreRef.current = { mode: 'window', detailTop: 0, windowTop: window.scrollY };
                          }

                          // Lock the current height of the Trace section with a smooth height transition
                          const traceEl = traceSectionRef.current;
                          if (traceEl) {
                            const h = traceEl.getBoundingClientRect().height;
                            traceEl.style.height = `${Math.max(0, Math.floor(h))}px`;
                            traceEl.style.overflow = 'hidden';
                            traceEl.style.transition = 'height 280ms ease';
                            scrollRestoreRef.current.traceLocked = true;
                            scrollRestoreRef.current.unlockDeadline = Date.now() + 1000; // give content up to 1s to arrive
                          }

                          const id = e.target.value || null;
                          setCurrentRun(id);
                          const u = new URL(window.location.href);
                          if (id) u.searchParams.set('run', id); else u.searchParams.delete('run');
                          window.history.replaceState({}, '', u.toString());
                          // Keep stale node events visible; they'll be replaced as new run data arrives
                        }}
                        style={{fontSize:'13px', padding:'4px 8px', fontWeight:'500'}}
                      >
                        {runs.map(r => (
                          <option key={r.run_id} value={r.run_id}>
                            {(r.run_id || '').slice(0,8)} • {r.started_at || 'n/a'}
                          </option>
                        ))}
                      </select>
                    </div>
                    )}
                  </div>
                )}
              </div>
              <p style={{ margin: '5px 0 0 0', fontSize: '12px', color: '#666' }}>
                {rfNodes.length} nodes • {rfEdges.length} connections
              </p>
              {/* Pipeline input snapshot chips (if available in trace meta) */}
              {traceMeta && (traceMeta.pipeline_input_repr || traceMeta.pipeline_input_context_repr) && (
                <div style={{ marginTop: '6px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                  {traceMeta.pipeline_input_repr && (
                    <div style={{ fontFamily: 'monospace', maxWidth: '40%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={traceMeta.pipeline_input_repr}>
                      Input Data: {traceMeta.pipeline_input_repr}
                      <button onClick={() => navigator.clipboard && navigator.clipboard.writeText(traceMeta.pipeline_input_repr)} style={{ marginLeft: '8px' }}>Copy</button>
                    </div>
                  )}
                  {traceMeta.pipeline_input_context_repr && (
                    <div style={{ fontFamily: 'monospace', maxWidth: '40%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={traceMeta.pipeline_input_context_repr}>
                      Input Context: {traceMeta.pipeline_input_context_repr}
                      <button onClick={() => navigator.clipboard && navigator.clipboard.writeText(traceMeta.pipeline_input_context_repr)} style={{ marginLeft: '8px' }}>Copy</button>
                    </div>
                  )}
                </div>
              )}
              {pipelineInfo && pipelineInfo.required_context_keys && pipelineInfo.required_context_keys.length > 0 && (
                <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#666' }}>
                  <span style={{ fontWeight: 'bold' }}>Required context keys:</span> {pipelineInfo.required_context_keys.join(', ')}
                </p>
              )}
            </div>
            {/* Pipeline Metadata Panel - Collapsible */}
            {(
              <div style={{
                borderBottom: '1px solid #ddd',
                background: '#fafbfc'
              }}>
                <button
                  onClick={() => setMetadataPanelOpen(!metadataPanelOpen)}
                  style={{
                    width: '100%',
                    padding: '12px 10px',
                    background: 'transparent',
                    border: 'none',
                    borderBottom: metadataPanelOpen ? '2px solid #5856d6' : '1px solid #e0e0e0',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    fontSize: '13px',
                    fontWeight: '600',
                    color: '#5856d6',
                    textAlign: 'left'
                  }}
                >
                  <span style={{
                    display: 'inline-block',
                    width: '16px',
                    height: '16px',
                    lineHeight: '16px',
                    textAlign: 'center',
                    transition: 'transform 200ms ease',
                    transform: metadataPanelOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                    fontSize: '12px'
                  }}>▶</span>
                  Pipeline Metadata
                </button>
                {metadataPanelOpen && (
                  <div style={{
                    padding: '12px 15px',
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                    gap: '12px'
                  }}>
                    {/* 1. Configuration Identity (YAML) - DEFAULT EXPANDED */}
                    <details open style={{
                      background: '#f8f9fa',
                      border: '2px solid #d0d0d0',
                      borderRadius: '6px',
                      padding: '12px',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      gridColumn: '1 / -1'
                    }}>
                      <summary style={{
                        cursor: 'pointer',
                        fontWeight: '700',
                        fontSize: '12px',
                        color: '#555',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        userSelect: 'none',
                        listStyle: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '10px'
                      }}>
                        <span style={{ fontSize: '10px', display: 'inline-block', transition: 'transform 200ms ease' }}>▶</span>
                        Configuration Identity (YAML)
                      </summary>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '8px', fontSize: '12px' }}>
                        {/* Configuration File */}
                        {pipelineData && pipelineData.config_file && (
                          <div>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Configuration File</div>
                            <div style={{ 
                              color: '#333', 
                              padding: '4px 8px',
                              background: '#ffffff',
                              borderRadius: '4px',
                              marginTop: '2px',
                              fontFamily: 'monospace',
                              border: '1px solid #ddd',
                              fontWeight: '600'
                            }}>
                              {pipelineData.config_file}
                            </div>
                          </div>
                        )}
                        
                        {/* Semantic ID */}
                        {inspectionIdentity && inspectionIdentity.semantic_id && (
                          <div>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Semantic ID (Structure)</div>
                            <div style={{ 
                              fontFamily: 'monospace', 
                              color: '#333', 
                              wordBreak: 'break-all',
                              padding: '4px 8px',
                              background: '#ffffff',
                              borderRadius: '4px',
                              marginTop: '2px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              border: '1px solid #ddd'
                            }}>
                              <span>{truncateHash(inspectionIdentity.semantic_id)}</span>
                              <button 
                                onClick={() => navigator.clipboard && navigator.clipboard.writeText(inspectionIdentity.semantic_id)} 
                                style={{ 
                                  padding: '2px 6px', 
                                  fontSize: '10px',
                                  background: '#e0e0e0',
                                  border: 'none',
                                  borderRadius: '3px',
                                  cursor: 'pointer',
                                  marginLeft: '6px'
                                }}
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                        
                        {/* Config ID */}
                        {inspectionIdentity && inspectionIdentity.config_id && (
                          <div>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Config ID (Parameters)</div>
                            <div style={{ 
                              fontFamily: 'monospace', 
                              color: '#333', 
                              wordBreak: 'break-all',
                              padding: '4px 8px',
                              background: '#ffffff',
                              borderRadius: '4px',
                              marginTop: '2px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              border: '1px solid #ddd'
                            }}>
                              <span>{truncateHash(inspectionIdentity.config_id)}</span>
                              <button 
                                onClick={() => navigator.clipboard && navigator.clipboard.writeText(inspectionIdentity.config_id)} 
                                style={{ 
                                  padding: '2px 6px', 
                                  fontSize: '10px',
                                  background: '#e0e0e0',
                                  border: 'none',
                                  borderRadius: '3px',
                                  cursor: 'pointer',
                                  marginLeft: '6px'
                                }}
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                        
                        {/* Run-Space Config ID */}
                        {inspectionIdentity && inspectionIdentity.run_space && inspectionIdentity.run_space.spec_id && (
                          <div>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Run-Space Config ID</div>
                            <div style={{ 
                              fontFamily: 'monospace', 
                              color: '#333', 
                              wordBreak: 'break-all',
                              padding: '4px 8px',
                              background: '#ffffff',
                              borderRadius: '4px',
                              marginTop: '2px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              border: '1px solid #ddd'
                            }}>
                              <span>{truncateHash(inspectionIdentity.run_space.spec_id)}</span>
                              <button 
                                onClick={() => navigator.clipboard && navigator.clipboard.writeText(inspectionIdentity.run_space.spec_id)} 
                                style={{ 
                                  padding: '2px 6px', 
                                  fontSize: '10px',
                                  background: '#e0e0e0',
                                  border: 'none',
                                  borderRadius: '3px',
                                  cursor: 'pointer',
                                  marginLeft: '6px'
                                }}
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                        
                        {/* Required Context Keys */}
                        {pipelineData && pipelineData.required_context_keys && pipelineData.required_context_keys.length > 0 && (
                          <div style={{ gridColumn: '1 / -1' }}>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Required Context Keys</div>
                            <div style={{ 
                              color: '#333', 
                              padding: '4px 8px',
                              background: '#ffffff',
                              borderRadius: '4px',
                              marginTop: '2px',
                              border: '1px solid #ddd',
                              fontFamily: 'monospace',
                              fontSize: '11px'
                            }}>
                              {pipelineData.required_context_keys.join(', ')}
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                    
                    {/* 2. Runtime Execution - DEFAULT COLLAPSED */}
                    {traceIdentity && (
                    <details style={{
                      background: 'white',
                      border: '1px solid #e0e0e0',
                      borderRadius: '6px',
                      padding: '12px',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      gridColumn: '1 / -1'
                    }}>
                      <summary style={{
                        cursor: 'pointer',
                        fontWeight: '700',
                        fontSize: '12px',
                        color: '#333',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        userSelect: 'none',
                        listStyle: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '10px'
                      }}>
                        <span style={{ fontSize: '10px', display: 'inline-block', transition: 'transform 200ms ease' }}>▶</span>
                        Runtime Execution
                      </summary>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                        <div>
                          <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Run ID</div>
                          <div style={{ 
                            fontFamily: 'monospace', 
                            color: '#333', 
                            wordBreak: 'break-all',
                            padding: '4px 8px',
                            background: '#f5f5f5',
                            borderRadius: '4px',
                            marginTop: '2px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between'
                          }}>
                            <span>{truncateHash(traceIdentity.identity.run_id)}</span>
                            <button 
                              onClick={() => navigator.clipboard && navigator.clipboard.writeText(traceIdentity.identity.run_id)} 
                              style={{ 
                                padding: '2px 6px', 
                                fontSize: '10px',
                                background: '#e0e0e0',
                                border: 'none',
                                borderRadius: '3px',
                                cursor: 'pointer',
                                marginLeft: '6px'
                              }}
                            >
                              Copy
                            </button>
                          </div>
                        </div>
                        
                        {/* Pipeline ID (runtime) */}
                        {traceIdentity.identity.pipeline_id && (
                          <div>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Pipeline ID</div>
                            <div style={{ 
                              fontFamily: 'monospace', 
                              color: '#333', 
                              wordBreak: 'break-all',
                              padding: '4px 8px',
                              background: '#f5f5f5',
                              borderRadius: '4px',
                              marginTop: '2px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between'
                            }}>
                              <span>{truncateHash(traceIdentity.identity.pipeline_id)}</span>
                              <button 
                                onClick={() => navigator.clipboard && navigator.clipboard.writeText(traceIdentity.identity.pipeline_id)} 
                                style={{ 
                                  padding: '2px 6px', 
                                  fontSize: '10px',
                                  background: '#e0e0e0',
                                  border: 'none',
                                  borderRadius: '3px',
                                  cursor: 'pointer',
                                  marginLeft: '6px'
                                }}
                              >
                                Copy
                              </button>
                            </div>
                          </div>
                        )}
                        
                        {/* Timestamps */}
                        {traceIdentity.timing && traceIdentity.timing.started_at && (
                          <div>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Started</div>
                            <div style={{ 
                              color: '#333', 
                              padding: '4px 8px',
                              background: '#f5f5f5',
                              borderRadius: '4px',
                              marginTop: '2px',
                              fontFamily: 'monospace',
                              fontSize: '11px'
                            }}>
                              {traceIdentity.timing.started_at}
                            </div>
                          </div>
                        )}
                        
                        {traceIdentity.timing && traceIdentity.timing.ended_at && (
                          <div>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Ended</div>
                            <div style={{ 
                              color: '#333', 
                              padding: '4px 8px',
                              background: '#f5f5f5',
                              borderRadius: '4px',
                              marginTop: '2px',
                              fontFamily: 'monospace',
                              fontSize: '11px'
                            }}>
                              {traceIdentity.timing.ended_at}
                            </div>
                          </div>
                        )}
                        
                        {/* Status - if available */}
                        <div>
                          <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Status</div>
                          <div style={{ 
                            color: '#333', 
                            padding: '4px 8px',
                            background: '#f5f5f5',
                            borderRadius: '4px',
                            marginTop: '2px',
                            fontSize: '11px',
                            fontWeight: '600'
                          }}>
                            {traceIdentity.timing && traceIdentity.timing.ended_at ? 'Completed' : 'Running'}
                          </div>
                        </div>
                        
                        {/* Context Values - Always show if trace available */}
                        {traceIdentity.run_space && traceIdentity.run_space.context && (
                          <div style={{ gridColumn: '1 / -1' }}>
                            <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Context Values</div>
                            <div style={{ 
                              fontFamily: 'monospace', 
                              color: '#333', 
                              padding: '4px 8px',
                              background: '#f5f5f5',
                              borderRadius: '4px',
                              marginTop: '2px',
                              fontSize: '11px',
                              maxWidth: '100%',
                              overflow: 'auto'
                            }}>
                              {Object.entries(traceIdentity.run_space.context)
                                .map(([k, v]) => {
                                  // Handle objects by stringifying them
                                  const valueStr = typeof v === 'object' && v !== null 
                                    ? JSON.stringify(v) 
                                    : String(v);
                                  return `${k}: ${valueStr}`;
                                })
                                .join(', ')}
                            </div>
                          </div>
                        )}
                      </div>
                    </details>
                    )}
                    
                    {/* 3. Identity Health (YAML ↔ Trace) - DEFAULT COLLAPSED */}
                    {inspectionIdentity && traceIdentity && (
                      <details style={{
                        background: 'white',
                        border: '2px solid #5856d6',
                        borderRadius: '6px',
                        padding: '12px',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                        gridColumn: '1 / -1'
                      }}>
                        <summary style={{
                          cursor: 'pointer',
                          fontWeight: '700',
                          fontSize: '12px',
                          color: '#5856d6',
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px',
                          userSelect: 'none',
                          listStyle: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          marginBottom: '10px'
                        }}>
                          <span style={{ fontSize: '10px', display: 'inline-block', transition: 'transform 200ms ease' }}>▶</span>
                          Identity Health (YAML ↔ Trace)
                        </summary>
                        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '12px' }}>
                          {inspectionIdentity.semantic_id && traceIdentity.identity && traceIdentity.identity.semantic_id && (
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '6px 12px',
                              borderRadius: '4px',
                              background: inspectionIdentity.semantic_id === traceIdentity.identity.semantic_id ? '#d4edda' : '#f8d7da',
                              border: `1px solid ${inspectionIdentity.semantic_id === traceIdentity.identity.semantic_id ? '#28a745' : '#dc3545'}`
                            }}>
                              <span style={{ fontSize: '14px' }}>{inspectionIdentity.semantic_id === traceIdentity.identity.semantic_id ? '✓' : '✗'}</span>
                              <span style={{ fontWeight: '600' }}>Semantic ID</span>
                              <span style={{ opacity: 0.7 }}>{inspectionIdentity.semantic_id === traceIdentity.identity.semantic_id ? 'Match' : 'Differs'}</span>
                            </div>
                          )}
                          {inspectionIdentity.config_id && traceIdentity.identity && traceIdentity.identity.config_id && (
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '6px 12px',
                              borderRadius: '4px',
                              background: inspectionIdentity.config_id === traceIdentity.identity.config_id ? '#fff3cd' : '#f8d7da',
                              border: `1px solid ${inspectionIdentity.config_id === traceIdentity.identity.config_id ? '#ffc107' : '#dc3545'}`
                            }}>
                              <span style={{ fontSize: '14px' }}>{inspectionIdentity.config_id === traceIdentity.identity.config_id ? '⚠' : '✗'}</span>
                              <span style={{ fontWeight: '600' }}>Config ID</span>
                              <span style={{ opacity: 0.7 }}>{inspectionIdentity.config_id === traceIdentity.identity.config_id ? 'Match (expected variation)' : 'Differs'}</span>
                            </div>
                          )}
                          {inspectionIdentity.run_space && inspectionIdentity.run_space.spec_id && traceIdentity.run_space && traceIdentity.run_space.spec_id && (
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '6px 12px',
                              borderRadius: '4px',
                              background: inspectionIdentity.run_space.spec_id === traceIdentity.run_space.spec_id ? '#d4edda' : '#f8d7da',
                              border: `1px solid ${inspectionIdentity.run_space.spec_id === traceIdentity.run_space.spec_id ? '#28a745' : '#dc3545'}`
                            }}>
                              <span style={{ fontSize: '14px' }}>{inspectionIdentity.run_space.spec_id === traceIdentity.run_space.spec_id ? '✓' : '✗'}</span>
                              <span style={{ fontWeight: '600' }}>Run-Space Plan</span>
                              <span style={{ opacity: 0.7 }}>{inspectionIdentity.run_space.spec_id === traceIdentity.run_space.spec_id ? 'Match' : 'Differs'}</span>
                            </div>
                          )}
                        </div>
                      </details>
                    )}

                    {/* 4. Run-Space Configuration - DEFAULT COLLAPSED (already using details) */}
                    {((runSpaces.length > 0 || hasRunsWithoutRunSpace) || (pipelineData && pipelineData.run_space_config)) && (
                      <details style={{
                        background: 'white',
                        border: '1px solid #e0e0e0',
                        borderRadius: '6px',
                        padding: '12px',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                        gridColumn: '1 / -1'  // Full width
                      }}>
                        <summary style={{
                          cursor: 'pointer',
                          fontWeight: '700',
                          fontSize: '12px',
                          color: '#333',
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px',
                          userSelect: 'none',
                          listStyle: 'none',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          marginBottom: '10px'
                        }}>
                          <span style={{ fontSize: '10px', display: 'inline-block', transition: 'transform 200ms ease' }}>▶</span>
                          Run-Space Configuration
                        </summary>
                        
                        <div style={{ marginTop: '12px' }}>
                        
                        {/* Show configuration from YAML if no trace-based run-space */}
                        {!runSpaceDetails && pipelineData && pipelineData.run_space_config && (
                          <div>
                            {/* Parse and display expansions from run_space_config */}
                            {(() => {
                              const config = pipelineData.run_space_config;
                              const blocks = config.blocks || [];
                              const allExpansions = [];
                              
                              // Parse blocks and generate expansions
                              blocks.forEach(block => {
                                if (block.mode === 'by_position' && block.context) {
                                  const keys = Object.keys(block.context);
                                  const values = keys.map(k => block.context[k] || []);
                                  const length = Math.max(...values.map(v => v.length));
                                  
                                  for (let i = 0; i < length; i++) {
                                    const expansion = {};
                                    keys.forEach(k => {
                                      expansion[k] = block.context[k][i];
                                    });
                                    allExpansions.push(expansion);
                                  }
                                } else if (block.mode === 'combinatorial' && block.context) {
                                  // Combinatorial expansion
                                  const keys = Object.keys(block.context);
                                  const values = keys.map(k => block.context[k] || []);
                                  
                                  const generateCombinations = (arrays) => {
                                    if (arrays.length === 0) return [[]];
                                    const first = arrays[0];
                                    const rest = generateCombinations(arrays.slice(1));
                                    const result = [];
                                    first.forEach(item => {
                                      rest.forEach(combo => {
                                        result.push([item, ...combo]);
                                      });
                                    });
                                    return result;
                                  };
                                  
                                  const combinations = generateCombinations(values);
                                  combinations.forEach(combo => {
                                    const expansion = {};
                                    keys.forEach((k, idx) => {
                                      expansion[k] = combo[idx];
                                    });
                                    allExpansions.push(expansion);
                                  });
                                }
                              });
                              
                              return (
                                <div>
                                  {/* Expansions Preview */}
                                  {allExpansions.length > 0 && (
                                    <details style={{ marginBottom: '12px' }}>
                                      <summary style={{ 
                                        cursor: 'pointer', 
                                        color: '#666', 
                                        fontSize: '11px', 
                                        fontWeight: '600',
                                        userSelect: 'none',
                                        listStyle: 'none',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px',
                                        marginBottom: '6px'
                                      }}>
                                        <span style={{ fontSize: '10px' }}>▶</span>
                                        Expansions Preview (Showing {Math.min(30, allExpansions.length)} of {allExpansions.length})
                                      </summary>
                                      <div style={{ 
                                        padding: '8px',
                                        background: '#f5f5f5',
                                        borderRadius: '4px',
                                        maxHeight: '300px',
                                        overflowY: 'auto',
                                        fontSize: '11px',
                                        fontFamily: 'monospace'
                                      }}>
                                        {allExpansions.slice(0, 30).map((exp, idx) => {
                                          const line = Object.entries(exp)
                                            .map(([k, v]) => `${k}=${v}`)
                                            .join(', ');
                                          return (
                                            <div 
                                              key={idx}
                                              style={{
                                                padding: '4px 0',
                                                borderBottom: idx < Math.min(29, allExpansions.length - 1) ? '1px solid #e0e0e0' : 'none',
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                whiteSpace: 'nowrap'
                                              }}
                                              title={line}
                                            >
                                              {line}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </details>
                                  )}
                                  
                                  {/* Full configuration (collapsed) */}
                                  <details>
                                    <summary style={{ 
                                      cursor: 'pointer', 
                                      color: '#666', 
                                      fontSize: '11px', 
                                      fontWeight: '600',
                                      userSelect: 'none',
                                      listStyle: 'none',
                                      display: 'flex',
                                      alignItems: 'center',
                                      gap: '4px'
                                    }}>
                                      <span style={{ fontSize: '10px' }}>▶</span>
                                      Full Configuration
                                    </summary>
                                    <div style={{ 
                                      padding: '8px',
                                      background: '#f5f5f5',
                                      borderRadius: '4px',
                                      maxHeight: '300px',
                                      overflowY: 'auto',
                                      marginTop: '6px'
                                    }}>
                                      <pre style={{ 
                                        margin: 0, 
                                        fontSize: '11px', 
                                        fontFamily: 'monospace',
                                        whiteSpace: 'pre-wrap',
                                        wordBreak: 'break-word'
                                      }}>
                                        {JSON.stringify(config, null, 2)}
                                      </pre>
                                    </div>
                                  </details>
                                </div>
                              );
                            })()}
                          </div>
                        )}
                        
                        {selectedRunSpace === '__all__' && runSpaceDetails && (
                          <div style={{ color: '#666', fontSize: '12px', fontStyle: 'italic' }}>
                            Select a specific run-space above to view its configuration.
                          </div>
                        )}
                        
                        {selectedRunSpace === '__none__' && (
                          <div style={{ color: '#666', fontSize: '12px', fontStyle: 'italic' }}>
                            This run has no run-space configuration.
                          </div>
                        )}
                        
                        {runSpaceDetails && (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {/* Basic Information - Always Expanded */}
                            <div>
                              <div style={{ color: '#888', fontSize: '10px', fontWeight: '600', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                Basic Information
                              </div>
                              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '8px', fontSize: '12px' }}>
                              {runSpaceDetails.spec_id && (
                                <div>
                                  <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Spec ID</div>
                                  <div style={{ 
                                    fontFamily: 'monospace', 
                                    color: '#333', 
                                    wordBreak: 'break-all',
                                    padding: '4px 8px',
                                    background: '#f5f5f5',
                                    borderRadius: '4px',
                                    marginTop: '2px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between'
                                  }}>
                                    <span title={runSpaceDetails.spec_id}>{truncateHash(runSpaceDetails.spec_id)}</span>
                                    <button 
                                      onClick={() => navigator.clipboard && navigator.clipboard.writeText(runSpaceDetails.spec_id)} 
                                      style={{ 
                                        padding: '2px 6px', 
                                        fontSize: '10px',
                                        background: '#e0e0e0',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer',
                                        marginLeft: '6px'
                                      }}
                                    >
                                      Copy
                                    </button>
                                  </div>
                                </div>
                              )}
                              
                              {runSpaceDetails.launch_id && (
                                <div>
                                  <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Launch ID</div>
                                  <div style={{ 
                                    fontFamily: 'monospace', 
                                    color: '#333', 
                                    wordBreak: 'break-all',
                                    padding: '4px 8px',
                                    background: '#f5f5f5',
                                    borderRadius: '4px',
                                    marginTop: '2px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between'
                                  }}>
                                    <span title={runSpaceDetails.launch_id}>{truncateHash(runSpaceDetails.launch_id)}</span>
                                    <button 
                                      onClick={() => navigator.clipboard && navigator.clipboard.writeText(runSpaceDetails.launch_id)} 
                                      style={{ 
                                        padding: '2px 6px', 
                                        fontSize: '10px',
                                        background: '#e0e0e0',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer',
                                        marginLeft: '6px'
                                      }}
                                    >
                                      Copy
                                    </button>
                                  </div>
                                </div>
                              )}
                              
                              {runSpaceDetails.inputs_id && (
                                <div>
                                  <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Inputs ID</div>
                                  <div style={{ 
                                    fontFamily: 'monospace', 
                                    color: '#333', 
                                    wordBreak: 'break-all',
                                    padding: '4px 8px',
                                    background: '#f5f5f5',
                                    borderRadius: '4px',
                                    marginTop: '2px',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between'
                                  }}>
                                    <span title={runSpaceDetails.inputs_id}>{truncateHash(runSpaceDetails.inputs_id)}</span>
                                    <button 
                                      onClick={() => navigator.clipboard && navigator.clipboard.writeText(runSpaceDetails.inputs_id)} 
                                      style={{ 
                                        padding: '2px 6px', 
                                        fontSize: '10px',
                                        background: '#e0e0e0',
                                        border: 'none',
                                        borderRadius: '3px',
                                        cursor: 'pointer',
                                        marginLeft: '6px'
                                      }}
                                    >
                                      Copy
                                    </button>
                                  </div>
                                </div>
                              )}
                              
                              <div>
                                <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Attempt</div>
                                <div style={{ 
                                  color: '#333', 
                                  padding: '4px 8px',
                                  background: '#f5f5f5',
                                  borderRadius: '4px',
                                  marginTop: '2px'
                                }}>
                                  {runSpaceDetails.attempt}
                                </div>
                              </div>
                              
                              {runSpaceDetails.combine_mode && (
                                <div>
                                  <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Combine Mode</div>
                                  <div style={{ 
                                    color: '#333', 
                                    padding: '4px 8px',
                                    background: '#f5f5f5',
                                    borderRadius: '4px',
                                    marginTop: '2px',
                                    fontFamily: 'monospace'
                                  }}>
                                    {runSpaceDetails.combine_mode}
                                  </div>
                                </div>
                              )}
                              
                              <div>
                                <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Planned / Total Runs</div>
                                <div style={{ 
                                  color: '#333', 
                                  padding: '4px 8px',
                                  background: '#f5f5f5',
                                  borderRadius: '4px',
                                  marginTop: '2px'
                                }}>
                                  {runSpaceDetails.planned_run_count != null ? runSpaceDetails.planned_run_count : '?'} / {runSpaceDetails.total_runs != null ? runSpaceDetails.total_runs : '?'}
                                </div>
                              </div>
                              
                              {runSpaceDetails.max_runs_limit && (
                                <div>
                                  <div style={{ color: '#666', fontSize: '11px', fontWeight: '600' }}>Max Runs Limit</div>
                                  <div style={{ 
                                    color: '#333', 
                                    padding: '4px 8px',
                                    background: '#f5f5f5',
                                    borderRadius: '4px',
                                    marginTop: '2px'
                                  }}>
                                    {runSpaceDetails.max_runs_limit}
                                  </div>
                                </div>
                              )}
                            </div>
                            </div>
                            
                            {/* Input Fingerprints - Collapsible */}
                            {runSpaceDetails.fingerprints && runSpaceDetails.fingerprints.length > 0 && (
                              <details style={{ marginTop: '8px' }}>
                                <summary style={{ 
                                  cursor: 'pointer', 
                                  color: '#666', 
                                  fontSize: '11px', 
                                  fontWeight: '600',
                                  userSelect: 'none',
                                  listStyle: 'none',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px'
                                }}>
                                  <span style={{ fontSize: '10px' }}>▶</span>
                                  Input Fingerprints ({runSpaceDetails.fingerprints.length})
                                </summary>
                                <div style={{ 
                                  marginTop: '6px',
                                  maxHeight: '200px', 
                                  overflowY: 'auto', 
                                  border: '1px solid #e0e0e0', 
                                  borderRadius: '4px',
                                  background: '#fafafa'
                                }}>
                                  <table style={{ 
                                    width: '100%', 
                                    fontSize: '11px', 
                                    borderCollapse: 'collapse'
                                  }}>
                                    <thead style={{ position: 'sticky', top: 0, background: '#f0f0f0', borderBottom: '2px solid #ddd' }}>
                                      <tr>
                                        <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: '600' }}>URI</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: '600' }}>Digest</th>
                                        <th style={{ padding: '6px 8px', textAlign: 'right', fontWeight: '600' }}>Size</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {runSpaceDetails.fingerprints.map((fp, idx) => (
                                        <tr key={idx} style={{ borderBottom: '1px solid #e8e8e8' }}>
                                          <td style={{ 
                                            padding: '6px 8px', 
                                            fontFamily: 'monospace', 
                                            fontSize: '10px',
                                            maxWidth: '250px',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap'
                                          }} title={fp.uri}>
                                            {fp.uri}
                                          </td>
                                          <td style={{ 
                                            padding: '6px 8px', 
                                            fontFamily: 'monospace', 
                                            fontSize: '10px',
                                            maxWidth: '150px',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis'
                                          }}>
                                            <span title={fp.digest}>{fp.digest ? fp.digest.slice(0, 16) + '...' : ''}</span>
                                            {fp.digest && (
                                              <button 
                                                onClick={() => navigator.clipboard && navigator.clipboard.writeText(fp.digest)} 
                                                style={{ 
                                                  padding: '1px 4px', 
                                                  fontSize: '9px',
                                                  background: '#e0e0e0',
                                                  border: 'none',
                                                  borderRadius: '2px',
                                                  cursor: 'pointer',
                                                  marginLeft: '4px'
                                                }}
                                              >
                                                Copy
                                              </button>
                                            )}
                                          </td>
                                          <td style={{ padding: '6px 8px', textAlign: 'right' }}>
                                            {fp.size ? fp.size.toLocaleString() : ''}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </details>
                            )}
                            
                            {/* Planner Metadata - Collapsible */}
                            {runSpaceDetails.planner_meta && (
                              <details style={{ marginTop: '8px' }}>
                                <summary style={{ 
                                  cursor: 'pointer', 
                                  color: '#666', 
                                  fontSize: '11px', 
                                  fontWeight: '600',
                                  userSelect: 'none',
                                  listStyle: 'none',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '4px'
                                }}>
                                  <span style={{ fontSize: '10px' }}>▶</span>
                                  Planner Metadata
                                </summary>
                                <div style={{ 
                                  marginTop: '6px',
                                  padding: '8px',
                                  background: '#f5f5f5',
                                  borderRadius: '4px',
                                  maxHeight: '200px',
                                  overflowY: 'auto'
                                }}>
                                  <pre style={{ 
                                    margin: 0, 
                                    fontSize: '10px', 
                                    fontFamily: 'monospace',
                                    whiteSpace: 'pre-wrap',
                                    wordBreak: 'break-word'
                                  }}>
                                    {JSON.stringify(runSpaceDetails.planner_meta, null, 2)}
                                  </pre>
                                  <button 
                                    onClick={() => navigator.clipboard && navigator.clipboard.writeText(JSON.stringify(runSpaceDetails.planner_meta, null, 2))} 
                                    style={{ 
                                      marginTop: '6px',
                                      padding: '4px 8px', 
                                      fontSize: '10px',
                                      background: '#e0e0e0',
                                      border: 'none',
                                      borderRadius: '3px',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    Copy JSON
                                  </button>
                                </div>
                              </details>
                            )}
                          </div>
                        )}
                        </div>
                      </details>
                    )}

                    {/* 5. Options (renamed from Visualization) - DEFAULT COLLAPSED */}
                    <details style={{
                      background: 'white',
                      border: '1px solid #e0e0e0',
                      borderRadius: '6px',
                      padding: '12px',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      gridColumn: '1 / -1'
                    }}>
                      <summary style={{
                        cursor: 'pointer',
                        fontWeight: '700',
                        fontSize: '12px',
                        color: '#333',
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        userSelect: 'none',
                        listStyle: 'none',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '10px'
                      }}>
                        <span style={{ fontSize: '10px', display: 'inline-block', transition: 'transform 200ms ease' }}>▶</span>
                        Options
                      </summary>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <button
                          onClick={() => setTraceOverlayVisible(!traceOverlayVisible)}
                          style={{
                            background: traceOverlayVisible ? '#28a745' : '#6c757d',
                            color: 'white',
                            border: 'none',
                            padding: '8px 12px',
                            borderRadius: '4px',
                            fontSize: '12px',
                            cursor: 'pointer',
                            fontWeight: '600',
                            transition: 'background 200ms ease'
                          }}
                        >
                          {traceOverlayVisible ? '✓ Overlay Visible' : '✗ Overlay Hidden'}
                        </button>
                      </div>
                    </details>
                  </div>
                )}
              </div>
            )}
            <CustomGraph 
              nodes={rfNodes} 
              edges={rfEdges} 
              onNodeClick={onNodeClick}
              selectedNodeId={selectedNodeId}
              traceAvailable={traceAvailable}
              traceOverlayVisible={traceOverlayVisible}
              getTraceAggForNode={getTraceAggForNode}
              getCalloutHoverText={getCalloutHoverText}
            />
          </div>
          <div id="details" ref={detailPanelRef} style={{ 
            width: isMobileView ? '100%' : `${details.width}px`,
            position: 'relative',
            borderLeft: isMobileView ? 'none' : '1px solid #ccc',
            borderTop: isMobileView ? '2px solid #007aff' : 'none',
            order: isMobileView ? 3 : 'unset',
            minHeight: isMobileView ? '200px' : 'auto',
            maxHeight: isMobileView ? '400px' : 'auto',
            overflowY: isMobileView ? 'auto' : 'visible',
            background: isMobileView ? 'white' : 'transparent',
            padding: isMobileView ? '15px' : '0'
          }}>
            {!isMobileView && (
              <div 
                className={`resize-handle resize-handle-left ${details.isResizing ? 'resizing' : ''}`}
                onMouseDown={details.handleMouseDown}
              />
            )}
            {nodeInfo ? (
              <div>
                <div style={{ 
                  marginBottom: '16px',
                  padding: '16px',
                  background: 'white',
                  border: '1px solid #e8e9ea',
                  borderRadius: '8px',
                  boxShadow: '0 2px 4px rgba(0, 0, 0, 0.06)'
                }}>
                  <h3 style={{ color: '#48484a', borderBottom: '2px solid #5856d6', paddingBottom: '8px', margin: '0 0 12px 0' }}>
                    {nodeInfo.label}
                  </h3>
                  
                  {nodeInfo.docstring && (
                    <div style={{ 
                      padding: '12px', 
                      background: '#f8f9fa', 
                      borderLeft: '4px solid #48484a',
                      borderRadius: '6px',
                      fontStyle: 'italic',
                      fontSize: '14px',
                      color: '#48484a',
                      marginTop: '12px'
                    }}>
                      {nodeInfo.docstring}
                    </div>
                  )}
                  
                  {/* Contract information in the same card */}
                  <div style={{ marginTop: '16px' }}>
                    {nodeInfo.input_type && (
                      <div className="contract-item">
                        <strong>Input Type:</strong> {nodeInfo.input_type}
                      </div>
                    )}
                    
                    {nodeInfo.output_type && (
                      <div className="contract-item">
                        <strong>Output Type:</strong> {nodeInfo.output_type}
                      </div>
                    )}
                    
                    <div className="contract-item">
                      <strong>Role:</strong> {nodeInfo.component_type}
                    </div>
                  </div>
                </div>
                
                {/* Parameter provenance section is now shown inside the Input card when trace is available. 
                    Keep it here only when trace overlay is not available to avoid duplication. */}
                {!traceAvailable && (
                  <div className="details-section">
                    <h4 className="details-subheader">Parameter provenance:</h4>
                    {nodeInfo.parameter_resolution && nodeInfo.parameter_resolution.required_params && 
                      nodeInfo.parameter_resolution.required_params.length > 0 ? (
                      <div>
                        {(() => {
                          // Build a set of invalid parameter names for quick lookup
                          const invalidParams = new Set((nodeInfo.invalid_parameters || []).map(p => p.name));
                          
                          return (
                            <React.Fragment>
                              {Object.keys(nodeInfo.parameter_resolution.from_pipeline_config || {}).length > 0 && (
                                <div className="prov-box prov-box-config">
                                  <div className="prov-header">From Pipeline Configuration:</div>
                                  {Object.entries(nodeInfo.parameter_resolution.from_pipeline_config).map(([key, details]) => {
                                    const isInvalid = invalidParams.has(key);
                                    return (
                                      <div key={key} className={`trace-item ${isInvalid ? 'trace-item-invalid' : ''}`}>
                                        <strong>{key}:</strong> {typeof details === 'object' && details.value !== undefined ? details.value + (details.source === 'default' ? ' [default]' : '') : details}
                                        {isInvalid && <span className="invalid-param-badge">⚠ Invalid parameter</span>}
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                              {Object.keys(nodeInfo.parameter_resolution.from_processor_defaults || {}).length > 0 && (
                                <div className="prov-box prov-box-default">
                                  <div className="prov-header">From Processor Defaults:</div>
                                  {Object.entries(nodeInfo.parameter_resolution.from_processor_defaults).map(([key, details]) => (
                                    <div key={key} className="trace-item">
                                      <strong>{key}:</strong> {typeof details === 'object' && details.value !== undefined ? details.value : details}
                                    </div>
                                  ))}
                                </div>
                              )}
                              {Object.keys(nodeInfo.parameter_resolution.from_context || {}).length > 0 && (
                                <div className="prov-box prov-box-context">
                                  <div className="prov-header">From Context:</div>
                                  {Object.entries(nodeInfo.parameter_resolution.from_context).map(([key, details]) => (
                                    <div key={key} className="trace-item">
                                      <strong>{key}:</strong> {
                                        typeof details === 'object' && details.source !== undefined ? (
                                          details.source !== "Initial Context" ? (
                                            <span>(From <span style={{color: '#af52de', fontWeight: 'bold'}}>Node {details.source_idx}</span>)</span>
                                          ) : (
                                            <span>(From <span style={{color: '#ff3b30', fontWeight: 'bold'}}>Initial Context</span>)</span>
                                          )
                                        ) : (
                                          <span>({details})</span>
                                        )
                                      }
                                    </div>
                                  ))}
                                </div>
                              )}
                            </React.Fragment>
                          );
                        })()}
                      </div>
                    ) : (
                      <div className="prov-box" style={{ background: '#f8f9fa', borderLeft: '3px solid #666', color: '#666', fontStyle: 'italic' }}>
                        This node does not require any parameters.
                      </div>
                    )}
                  </div>
                )}
                
                {/* Derived Preprocessor Metadata Section */}
                {nodeInfo.preprocessor_metadata && nodeInfo.preprocessor_metadata.type === 'derive.parameter_sweep' && (
                  <div className="details-section">
                    <h4 className="details-subheader">Derived Preprocessor: Parameter Sweep</h4>
                    
                    <div className="sv-card">
                      <div className="sv-card-title">Sweep Configuration</div>
                      <div className="sv-kv-grid">
                        <div className="kv">
                          <span className="k">Mode: </span>
                          <span className="v">{nodeInfo.preprocessor_metadata.mode || 'combinatorial'}</span>
                        </div>
                        <div className="kv">
                          <span className="k">Broadcast: </span>
                          <span className="v">{nodeInfo.preprocessor_metadata.broadcast ? 'Yes' : 'No'}</span>
                        </div>
                        {nodeInfo.preprocessor_metadata.collection && (
                          <div className="kv">
                            <span className="k">Collection: </span>
                            <span className="v mono">{nodeInfo.preprocessor_metadata.collection}</span>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {nodeInfo.preprocessor_metadata.variables && Object.keys(nodeInfo.preprocessor_metadata.variables).length > 0 && (
                      <div className="sv-card">
                        <div className="sv-card-title">Variables</div>
                        <div className="sv-kv-grid">
                          {Object.entries(nodeInfo.preprocessor_metadata.variables).map(([varName, varDef]) => (
                            <div key={varName} className="kv">
                              <span className="k">{varName}: </span>
                              <span className="v">
                                {varDef.kind === 'range' ? (
                                  `range(${formatNumber(varDef.lo)} → ${formatNumber(varDef.hi)}, ${varDef.steps} steps)`
                                ) : varDef.kind === 'list' ? (
                                  `list[${varDef.values ? varDef.values.length : 0} items]`
                                ) : (
                                  JSON.stringify(varDef)
                                )}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {nodeInfo.preprocessor_metadata.param_expressions && Object.keys(nodeInfo.preprocessor_metadata.param_expressions).length > 0 && (
                      <div className="sv-card">
                        <div className="sv-card-title">Parameter Expressions</div>
                        <div className="sv-kv-grid">
                          {Object.entries(nodeInfo.preprocessor_metadata.param_expressions).map(([paramName, exprData]) => (
                            <div key={paramName} className="kv">
                              <span className="k">{paramName}: </span>
                              <span className="v mono">
                                {(nodeInfo.preprocessor_view && 
                                  nodeInfo.preprocessor_view.param_expressions && 
                                  nodeInfo.preprocessor_view.param_expressions[paramName] &&
                                  nodeInfo.preprocessor_view.param_expressions[paramName].expr) || 
                                 '<expression (source not available)>'}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                <div className="details-section">
                  <h4 className="details-subheader">Context contracts:</h4>
                  
                  {(() => {
                    const hasCreatedKeys = nodeInfo.created_keys && nodeInfo.created_keys.length > 0;
                    const hasRequiredKeys = nodeInfo.required_keys && nodeInfo.required_keys.length > 0;
                    const hasSuppressedKeys = nodeInfo.suppressed_keys && nodeInfo.suppressed_keys.length > 0;
                    
                    if (!hasCreatedKeys && !hasRequiredKeys && !hasSuppressedKeys) {
                      return (
                        <div className="prov-box" style={{
                          background: '#f8f9fa', 
                          borderLeft: '3px solid #666',
                          color: '#666',
                          fontStyle: 'italic'
                        }}>
                          This node does not use the context.
                        </div>
                      );
                    }
                    
                    return (
                      <div>
                        {hasRequiredKeys && (
                          <div className="trace-item">
                            <strong>Requires:</strong> {nodeInfo.required_keys.join(', ')}
                          </div>
                        )}
                        {hasCreatedKeys && (
                          <div className="trace-item">
                            <strong>Produces:</strong> {nodeInfo.created_keys.join(', ')}
                          </div>
                        )}
                        {hasSuppressedKeys && (
                          <div className="trace-item">
                            <strong>Removes:</strong> {nodeInfo.suppressed_keys.join(', ')}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
                
                {/* Trace Information Section */}
                {(traceOverlayVisible && traceAvailable) && (
                  <div className="details-section" ref={traceSectionRef}>
                    <h4 className="details-subheader">Trace records:</h4>
                    {traceMeta ? (function() {
                  // Bind by node_uuid when possible. Prefer canonical_nodes or mappings from trace meta.
                  const currentNode = nodeMap[parseInt(selectedNodeId)];
                  let nodeUuid = null;

                  // If the pipeline emitted node_uuid (nodeMap may include it)
                  if (currentNode && currentNode.node_uuid) nodeUuid = currentNode.node_uuid;

                  // Otherwise, try mapping via label -> uuid
                  if (!nodeUuid && traceLabelToUuid && currentNode) {
                    nodeUuid = traceLabelToUuid.get(currentNode.label);
                  }

                  // Also try matching via canonical_nodes data in traceMeta
                  let canonicalInfo = null;
                  if (!nodeUuid && traceMeta && traceMeta.node_mappings && traceMeta.node_mappings.fqn_to_uuid) {
                    // try to find by fqn that contains the label
                    for (const [fqn, uuid] of Object.entries(traceMeta.node_mappings.fqn_to_uuid)) {
                      if (currentNode && currentNode.label && fqn.includes(currentNode.label)) {
                        nodeUuid = uuid; break;
                      }
                    }
                  }

                  // If traceIndex exposed canonical_nodes list, find declaration_index/subindex
                  if (traceMeta && traceMeta.canonical_nodes && nodeUuid) {
                    canonicalInfo = traceMeta.canonical_nodes.find(n => n.node_uuid === nodeUuid) || null;
                  }

                  const nodeEvents = (() => {
                    if (!nodeUuid) return [];
                    const runMap = nodeTraceEvents.get(currentRun) || new Map();
                    return runMap.get(nodeUuid) || [];
                  })();

                  // SER v1: Single event per execution (not before/after bucketing)
                  // Get the most recent event (should be only one per execution)
                  const latestEvent = nodeEvents.length > 0 ? nodeEvents[nodeEvents.length - 1] : null;
                  
                  // Extract data from the event
                  const rawData = latestEvent && latestEvent._raw;
                  const timing = (rawData && rawData.timing) || {};
                  const status_from_raw = (rawData && rawData.status) || 'unknown';
                  
                  // Determine display status
                  let status = 'Unknown';
                  if (latestEvent) {
                    if (latestEvent.status === 'error') {
                      status = 'Error';
                    } else if (latestEvent.status === 'succeeded' || status_from_raw === 'succeeded') {
                      status = 'Completed';
                    }
                  }

                  const metaOverrides = {
                    node_uuid: nodeUuid || '—',
                    node_index: canonicalInfo ? (canonicalInfo.declaration_index + 1) : '—',
                    started: timing.started_at || '—',
                    ended: timing.finished_at || '—',
                    status: status,
                  };
                  // Don't override wall/cpu - let extractExecMeta get them from _raw

                  // Renderer for parameter provenance (moved into Input card)
                  const renderParamProvenance = () => {
                    if (!nodeInfo || !nodeInfo.parameter_resolution) return null;
                    const pr = nodeInfo.parameter_resolution;
                    if (!pr.required_params || pr.required_params.length === 0) {
                      return (
                        <div className="prov-box" style={{ background: '#f8f9fa', borderLeft: '3px solid #666', color: '#666', fontStyle: 'italic' }}>
                          This node does not require any parameters.
                        </div>
                      );
                    }
                    
                    // Build a set of invalid parameter names for quick lookup
                    const invalidParams = new Set((nodeInfo.invalid_parameters || []).map(p => p.name));
                    
                    return (
                      <div>
                        {Object.keys(pr.from_pipeline_config || {}).length > 0 && (
                          <div className="prov-box prov-box-config">
                            <div className="prov-header">From Pipeline Configuration:</div>
                            {Object.entries(pr.from_pipeline_config).map(([key, details]) => {
                              const isInvalid = invalidParams.has(key);
                              return (
                                <div key={key} className={`trace-item ${isInvalid ? 'trace-item-invalid' : ''}`}>
                                  <strong>{key}:</strong> {typeof details === 'object' && details.value !== undefined ? details.value + (details.source === 'default' ? ' [default]' : '') : details}
                                  {isInvalid && <span className="invalid-param-badge">⚠ Invalid parameter</span>}
                                </div>
                              );
                            })}
                          </div>
                        )}
                        {Object.keys(pr.from_processor_defaults || {}).length > 0 && (
                          <div className="prov-box prov-box-default">
                            <div className="prov-header">From Processor Defaults:</div>
                            {Object.entries(pr.from_processor_defaults).map(([key, details]) => (
                              <div key={key} className="trace-item">
                                <strong>{key}:</strong> {typeof details === 'object' && details.value !== undefined ? details.value : details}
                              </div>
                            ))}
                          </div>
                        )}
                        {Object.keys(pr.from_context || {}).length > 0 && (
                          <div className="prov-box prov-box-context">
                            <div className="prov-header">From Context:</div>
                            {Object.entries(pr.from_context).map(([key, details]) => {
                              // Try to get parameter value from SER raw data if available
                              let valueRepr = '';
                              try {
                                if (rawData && rawData.processor && rawData.processor.parameters) {
                                  const paramValue = rawData.processor.parameters[key];
                                  if (paramValue !== undefined) {
                                    if (typeof paramValue === 'object' && paramValue.repr) {
                                      valueRepr = paramValue.repr;
                                    } else if (typeof paramValue === 'number') {
                                      // Preserve float representation
                                      valueRepr = formatNumber(paramValue);
                                    } else {
                                      valueRepr = String(paramValue);
                                    }
                                    // Cap at 40 characters
                                    if (valueRepr.length > 40) {
                                      valueRepr = valueRepr.substring(0, 40) + '...';
                                    }
                                  }
                                }
                              } catch (e) {
                                // ignore errors, fall back to no repr
                              }
                              
                              return (
                                <div key={key} className="trace-item">
                                  <strong>{key}:</strong>{' '}
                                  {valueRepr && <span style={{fontFamily: 'monospace', color: '#333'}}>{valueRepr}</span>}
                                  {valueRepr && ' '}
                                  {typeof details === 'object' && details.source !== undefined ? (
                                    details.source !== 'Initial Context' ? (
                                      <span>(From <span style={{color: '#af52de', fontWeight: 'bold'}}>Node {details.source_idx}</span>)</span>
                                    ) : (
                                      <span>(From <span style={{color: '#ff3b30', fontWeight: 'bold'}}>Initial Context</span>)</span>
                                    )
                                  ) : (
                                    <span>({details})</span>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  };

                  return (
                    <div>
                      {rawData && rawData.record_type === 'ser' ? (
                        <React.Fragment>
                          <TraceExecutionCard raw={rawData} metaOverrides={metaOverrides} />
                          <TraceInputCard raw={rawData} paramProvenanceRenderer={renderParamProvenance} />
                          <TraceOutputCard raw={rawData} />
                          <TraceChecksCard raw={rawData} />
                        </React.Fragment>
                      ) : (
                        // Fallback minimal cards when no SER raw present
                        <React.Fragment>
                          <TraceExecutionCard raw={{}} metaOverrides={metaOverrides} />
                        </React.Fragment>
                      )}

                      {/* Error summary if event is error */}
                      {latestEvent && latestEvent.status === 'error' && (
                        <div style={{ marginTop: '8px', padding: '10px', border: '1px solid #f8d7da', background: '#fff5f6', borderRadius: '6px' }}>
                          <div className="trace-item"><strong>Error Type:</strong> {latestEvent.error_type}</div>
                          {latestEvent.error_msg && (
                            <div className="trace-item" title={latestEvent.error_msg}>
                              <strong>Message:</strong> {String(latestEvent.error_msg).split('\n')[0]} 
                              <button onClick={() => navigator.clipboard && navigator.clipboard.writeText(latestEvent.error_msg)} style={{ marginLeft: '6px' }}>Copy</button>
                            </div>
                          )}
                          {rawData && rawData.traceback && (
                            <div style={{ marginTop: '6px' }}>
                              <div className="trace-item"><strong>Traceback:</strong></div>
                              <pre style={{ maxHeight: '8em', overflow: 'auto', fontFamily: 'monospace', background: '#fff', padding: '8px', borderRadius: '4px', marginTop: '4px' }}>{rawData.traceback}</pre>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                    })() : (
                      // Placeholder while traceMeta is refreshing; keep space to prevent jump
                      <div style={{ padding: '8px', color: '#666', fontStyle: 'italic' }}>Refreshing trace…</div>
                    )}
                  </div>
                )}
                
                {/* Errors Section */}
                {nodeInfo.errors && nodeInfo.errors.length > 0 && (
                  <div className="details-section">
                    <div className="details-subheader" style={{ color: '#dc3545', borderBottomColor: '#dc3545' }}>
                      Errors
                    </div>
                    <div style={{
                      background: '#f8d7da', 
                      border: '1px solid #dc3545',
                      borderRadius: '6px',
                      padding: '12px'
                    }}>
                      {nodeInfo.errors.map((error, index) => (
                        <div key={index} style={{
                          color: '#721c24',
                          fontSize: '14px',
                          marginBottom: index < nodeInfo.errors.length - 1 ? '8px' : '0',
                          lineHeight: '1.4'
                        }}>
                          • {error}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ padding: '20px', textAlign: 'center', color: '#666' }}>
                <h4>Select a node to see details</h4>
                <p>Click on any node in the graph or sidebar to view its properties, parameters, and relationships.</p>
              </div>
            )}
          </div>
        </div>
      );
    }

    ReactDOM.render(React.createElement(App), document.getElementById('root'));
