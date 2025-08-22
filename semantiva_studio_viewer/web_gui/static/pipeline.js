    const {useState, useEffect, useRef, useCallback} = React;

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
        }
      };

      return { ...baseStyle, ...typeStyles[type] };
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
    function PipelineNode({ node, pos, isSelected, onClick, registerAnchors, width, height }) {
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
                             ((node.data.defaultParams ? node.data.defaultParams.length : 0) || 0);
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

      return (
        <div
          ref={nodeRef}
          key={node.id}
          className={`custom-node ${pos.type} ${isSelected ? 'selected' : ''} ${hasErrors ? 'error' : ''}`}
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
              >
                {param}
              </div>
            ))}
            {(node.data.createdKeys || []).map((key, i) => (
              <div
                key={key}
                className="param-label created-key"
                style={createCalloutStyle('created', key)}
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
              >
                {param}
              </div>
            ))}
            {(node.data.defaultParams || []).map((param, i) => (
              <div
                key={param}
                className="param-label left-anchor-default"
                style={createCalloutStyle('default', param)}
              >
                {param}
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Custom Graph Component with dual-channel layout
    function CustomGraph({ nodes, edges, onNodeClick, selectedNodeId }) {
  const [zoomLevel, setZoomLevel] = useState(1);
  const [containerRef, setContainerRef] = useState(null);
  // CoordinateSystem helper instance
  const csRef = React.useRef(null);
      const [anchorMap, setAnchorMap] = useState({});
      const [colWidths, setColWidths] = useState({ data: 300, config: 80, context: 300 });

      // Calculate dynamic height for each node
      const calculateNodeHeight = (node) => {
        const leftParamCount = ((node.data.pipelineConfigParams ? node.data.pipelineConfigParams.length : 0) || 0) + 
                               ((node.data.defaultParams ? node.data.defaultParams.length : 0) || 0);
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
          .filter(n => n.data.label.match(/Context|Rename|Delete/))
          .map(n => anchorMap[n.id].node.width);
        const configWidths = nodes.map(n => {
          const configParams = n.data.pipelineConfigParams || [];
          const defaultParams = n.data.defaultParams || [];
          const allParams = [...configParams, ...defaultParams];
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
        const label = node.data.label || '';
        let nodeType, xPos;
        
        // Determine node category and horizontal position
        if (label.includes('Source') || label.includes('Sink') || label.includes('DataSource') || label.includes('DataSink')) {
          nodeType = 'source-sink';
          xPos = centerPosition;
        } else if (label.includes('Context') || label.includes('Rename') || label.includes('Delete')) {
          nodeType = 'context-processor';
          xPos = rightChannelCenter;
        } else {
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

          <div className="custom-graph-wrapper">
          <div
            ref={setContainerRef}
            className="custom-graph"
            style={{
              position: 'relative',
              width: totalWidth,
              height: '100%',
              minHeight: `${Math.max(totalHeight * zoomLevel, 500)}px`,
              transform: `scale(${zoomLevel})`,
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

      // Resizable panels
      const sidebar = useResizable(400, 200, 600);
      const details = useResizableRight(300, 200, 500);

      useEffect(() => {
        console.log('Loading pipeline data...');
        
        fetch('/api/pipeline')
          .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
          })
          .then(data => {
            console.log('Pipeline data loaded:', data);
            
            // Store pipeline-level information
            setPipelineInfo(data.pipeline || { has_errors: false, pipeline_errors: [], required_context_keys: [] });
            
            const map = {};
            const n = data.nodes.map((node, idx) => {
              map[node.id] = node;
              
              // Create parameter data with source information for visual display
              const configParams = [];
              const defaultParams = [];
              
              // Parameters from pipeline configuration
              if (node.parameter_resolution && node.parameter_resolution.from_pipeline_config) {
                configParams.push(...Object.keys(node.parameter_resolution.from_pipeline_config));
              }
              
              // Parameters from processor defaults
              if (node.parameter_resolution && node.parameter_resolution.from_processor_defaults) {
                defaultParams.push(...Object.keys(node.parameter_resolution.from_processor_defaults));
              }
              
              return {
                id: String(node.id),
                data: {
                  label: node.label,
                  inputType: node.input_type || '',
                  outputType: node.output_type || '',
                  pipelineConfigParams: configParams,
                  defaultParams: defaultParams,
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
          })
          .catch(err => {
            console.error('Error loading pipeline:', err);
            setError(err.message);
            setLoading(false);
          });
      }, []);

      const onNodeClick = (_, node) => {
        console.log('Node clicked:', node);
        const nodeData = nodeMap[parseInt(node.id)];
        setNodeInfo(nodeData);
        setSelectedNodeId(node.id);
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
        <div style={{display:'flex', height:'100%', width:'100%'}}>
          <div id="sidebar" style={{ 
            width: sidebarCollapsed ? '40px' : `${sidebar.width}px`, 
            overflow: 'hidden', 
            transition: sidebarCollapsed ? 'width 0.3s ease' : 'none',
            borderRight: '1px solid #ccc',
            padding: sidebarCollapsed ? '4px 0' : '4px',
            position: 'relative'
          }}>
            {!sidebarCollapsed && (
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
                writingMode: sidebarCollapsed ? 'vertical-rl' : 'horizontal-tb',
                textAlign: 'center',
                transform: sidebarCollapsed ? 'rotate(180deg)' : 'none',
                whiteSpace: 'nowrap',
                userSelect: 'none'
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
                .filter(n => 
                  !n.label.includes('Source') && 
                  !n.label.includes('Sink') && 
                  !n.label.includes('Context') && 
                  !n.label.includes('Rename') && 
                  !n.label.includes('Delete')
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
                  n.label.includes('Context') || 
                  n.label.includes('Rename') || 
                  n.label.includes('Delete')
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
                  n.label.includes('Source') || 
                  n.label.includes('Sink')
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
          <div id="graph">
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
              </div>
              <p style={{ margin: '5px 0 0 0', fontSize: '12px', color: '#666' }}>
                {rfNodes.length} nodes • {rfEdges.length} connections
              </p>
              {pipelineInfo && pipelineInfo.required_context_keys && pipelineInfo.required_context_keys.length > 0 && (
                <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#666' }}>
                  <span style={{ fontWeight: 'bold' }}>Required context keys:</span> {pipelineInfo.required_context_keys.join(', ')}
                </p>
              )}
            </div>
            <CustomGraph 
              nodes={rfNodes} 
              edges={rfEdges} 
              onNodeClick={onNodeClick}
              selectedNodeId={selectedNodeId}
            />
          </div>
          <div id="details" style={{ 
            width: `${details.width}px`,
            position: 'relative'
          }}>
            <div 
              className={`resize-handle resize-handle-left ${details.isResizing ? 'resizing' : ''}`}
              onMouseDown={details.handleMouseDown}
            />
            {nodeInfo ? (
              <div>
                <h3 style={{ color: '#48484a', borderBottom: '2px solid #5856d6', paddingBottom: '5px' }}>
                  {nodeInfo.label}
                </h3>
                
                {nodeInfo.docstring && (
                  <div style={{ 
                    marginBottom: '15px', 
                    padding: '12px', 
                    background: '#f8f9fa', 
                    borderLeft: '4px solid #48484a',
                    borderRadius: '6px',
                    fontStyle: 'italic',
                    fontSize: '14px',
                    color: '#48484a'
                  }}>
                    {nodeInfo.docstring}
                  </div>
                )}
                
                {nodeInfo.input_type && (
                  <div style={{ marginBottom: '10px', padding: '8px', background: '#e8f5ea', borderRadius: '6px', borderLeft: '3px solid #34c759' }}>
                    <strong style={{ color: '#34c759' }}>Input Type:</strong> {nodeInfo.input_type}
                  </div>
                )}
                
                {nodeInfo.output_type && (
                  <div style={{ marginBottom: '10px', padding: '8px', background: '#fff4e6', borderRadius: '6px', borderLeft: '3px solid #ff9500' }}>
                    <strong style={{ color: '#ff9500' }}>Output Type:</strong> {nodeInfo.output_type}
                  </div>
                )}
                
                <div style={{ marginBottom: '10px', padding: '8px', background: '#eeecff', borderRadius: '6px', borderLeft: '3px solid #5856d6' }}>
                  <strong style={{ color: '#5856d6' }}>Type:</strong> {nodeInfo.component_type}
                </div>
                
                <div>
                  <p><b>Parameters:</b></p>
                  
                  {nodeInfo.parameter_resolution && nodeInfo.parameter_resolution.required_params && 
                   nodeInfo.parameter_resolution.required_params.length > 0 ? (
                    <div>
                      {/* Parameters from pipeline configuration */}
                      <div style={{marginTop: '10px'}}>
                        <p style={{margin: '0 0 5px 0', fontWeight: 'bold', color: '#8e8e93'}}>From Pipeline Configuration:</p>
                        {Object.keys(nodeInfo.parameter_resolution.from_pipeline_config || {}).length > 0 ? (
                          <div style={{
                            background: '#f2f2f7', 
                            padding: '8px', 
                            borderRadius: '4px',
                            border: '1px solid #d1d1d6',
                            fontSize: '12px'
                          }}>
                            {Object.entries(nodeInfo.parameter_resolution.from_pipeline_config).map(([key, details]) => (
                              <div key={key} style={{marginBottom: '3px'}}>
                                <span style={{fontWeight: 'bold'}}>{key}:</span> {
                                  typeof details === 'object' && details.value !== undefined ? 
                                    details.value + (details.source === 'default' ? ' [default]' : '') :
                                    details
                                }
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{
                            background: '#f8f9fa',
                            padding: '8px',
                            borderRadius: '4px',
                            color: '#666',
                            fontSize: '12px'
                          }}>None</div>
                        )}
                      </div>
                      
                      {/* Parameters from processor defaults */}
                      <div style={{marginTop: '10px'}}>
                        <p style={{margin: '0 0 5px 0', fontWeight: 'bold', color: '#ff9f0a'}}>From Processor Defaults:</p>
                        {Object.keys(nodeInfo.parameter_resolution.from_processor_defaults || {}).length > 0 ? (
                          <div style={{
                            background: '#fff4e6', 
                            padding: '8px', 
                            borderRadius: '4px',
                            border: '1px solid #ffe0b3',
                            fontSize: '12px'
                          }}>
                            {Object.entries(nodeInfo.parameter_resolution.from_processor_defaults).map(([key, details]) => (
                              <div key={key} style={{marginBottom: '3px'}}>
                                <span style={{fontWeight: 'bold'}}>{key}:</span> {
                                  typeof details === 'object' && details.value !== undefined ? 
                                    details.value :
                                    details
                                }
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{
                            background: '#f8f9fa',
                            padding: '8px',
                            borderRadius: '4px',
                            color: '#666',
                            fontSize: '12px'
                          }}>None</div>
                        )}
                      </div>
                      
                      {/* Parameters from context */}
                      <div style={{marginTop: '10px'}}>
                        <p style={{margin: '0 0 5px 0', fontWeight: 'bold', color: '#af52de'}}>From Context:</p>
                        {Object.keys(nodeInfo.parameter_resolution.from_context || {}).length > 0 ? (
                          <div style={{
                            background: '#f5e6ff', 
                            padding: '8px', 
                            borderRadius: '4px',
                            border: '1px solid #e6ccff',
                            fontSize: '12px'
                          }}>
                            {Object.entries(nodeInfo.parameter_resolution.from_context).map(([key, details]) => (
                              <div key={key} style={{marginBottom: '3px'}}>
                                <span style={{fontWeight: 'bold'}}>{key}:</span> {
                                  typeof details === 'object' && details.source !== undefined ? (
                                    details.source !== "Initial Context" ? (
                                      <span>From <span style={{color: '#af52de', fontWeight: 'bold'}}>Node {details.source_idx}</span></span>
                                    ) : (
                                      <span>From <span style={{color: '#ff3b30', fontWeight: 'bold'}}>Initial Context</span></span>
                                    )
                                  ) : (
                                    details
                                  )
                                }
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{
                            background: '#f8f9fa',
                            padding: '8px',
                            borderRadius: '4px',
                            color: '#666',
                            fontSize: '12px'
                          }}>None</div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div style={{
                      background: '#f8f9fa', 
                      padding: '8px', 
                      borderRadius: '4px',
                      color: '#666',
                      fontSize: '12px'
                    }}>
                      This node does not require any parameters.
                    </div>
                  )}
                </div>
                
                <div style={{ marginBottom: '10px' }}>
                  <p><b>Created Keys:</b> {nodeInfo.created_keys && nodeInfo.created_keys.length > 0 ? nodeInfo.created_keys.join(', ') : 'None'}</p>
                  <p><b>Required Keys:</b> {nodeInfo.required_keys && nodeInfo.required_keys.length > 0 ? nodeInfo.required_keys.join(', ') : 'None'}</p>
                  <p><b>Suppressed Keys:</b> {nodeInfo.suppressed_keys && nodeInfo.suppressed_keys.length > 0 ? nodeInfo.suppressed_keys.join(', ') : 'None'}</p>
                </div>
                
                {/* Errors Section */}
                {nodeInfo.errors && nodeInfo.errors.length > 0 && (
                  <div>
                    <h4 style={{ color: '#dc3545', margin: '20px 0 10px 0', borderBottom: '1px solid #dc3545', paddingBottom: '5px' }}>
                      Errors
                    </h4>
                    <div style={{
                      background: '#f8d7da', 
                      border: '1px solid #dc3545',
                      borderRadius: '4px',
                      padding: '10px'
                    }}>
                      {nodeInfo.errors.map((error, index) => (
                        <div key={index} style={{
                          color: '#721c24',
                          fontSize: '13px',
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
