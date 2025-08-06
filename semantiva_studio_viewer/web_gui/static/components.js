    const { useState, useEffect } = React;

    // Resizable panel hook
    function useResizable(initialWidth, minWidth = 200, maxWidth = 600) {
      const [width, setWidth] = useState(initialWidth);
      const [isResizing, setIsResizing] = useState(false);
      const startX = React.useRef(0);
      const startWidth = React.useRef(0);

      const handleMouseDown = React.useCallback((e) => {
        setIsResizing(true);
        startX.current = e.clientX;
        startWidth.current = width;
        e.preventDefault();
      }, [width]);

      const handleMouseMove = React.useCallback((e) => {
        if (!isResizing) return;
        
        const deltaX = e.clientX - startX.current;
        const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth.current + deltaX));
        setWidth(newWidth);
      }, [isResizing, minWidth, maxWidth]);

      const handleMouseUp = React.useCallback(() => {
        setIsResizing(false);
      }, []);

      React.useEffect(() => {
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
      const startX = React.useRef(0);
      const startWidth = React.useRef(0);

      const handleMouseDown = React.useCallback((e) => {
        setIsResizing(true);
        startX.current = e.clientX;
        startWidth.current = width;
        e.preventDefault();
      }, [width]);

      const handleMouseMove = React.useCallback((e) => {
        if (!isResizing) return;
        
        const deltaX = startX.current - e.clientX; // Reversed for right panel
        const newWidth = Math.max(minWidth, Math.min(maxWidth, startWidth.current + deltaX));
        setWidth(newWidth);
      }, [isResizing, minWidth, maxWidth]);

      const handleMouseUp = React.useCallback(() => {
        setIsResizing(false);
      }, []);

      React.useEffect(() => {
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

    function TreeNode({ node, depth, onSelect, selectedId }) {
      const isSelected = selectedId === node.id;
      const componentTypeClass = getComponentTypeClass(node.component_type);
      
      return (
        <div className="tree-node" style={{ marginLeft: depth * 40 }}>
          <div 
            className={`tree-node-item ${componentTypeClass} ${isSelected ? 'selected' : ''}`} 
            onClick={() => onSelect(node)}
          >
            <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
              {node.label}
            </div>
            <div style={{ fontSize: '11px', color: '#666' }}>
              {node.component_type}
            </div>
            <div className="component-type-badge">
              {getComponentTypeBadge(node.component_type)}
            </div>
          </div>
          {node.children && node.children.length > 0 && (
            <div className="tree-connector">
              {node.children.map(child => (
                <TreeNode key={child.id} node={child} depth={depth + 1} onSelect={onSelect} selectedId={selectedId} />
              ))}
            </div>
          )}
        </div>
      );
    }

    function buildTree(nodes, edges) {
      const map = {};
      nodes.forEach(n => { map[n.id] = { ...n, children: [] }; });
      edges.forEach(e => { if(map[e.source] && map[e.target]) map[e.source].children.push(map[e.target]); });
      const childIds = new Set(edges.map(e => e.target));
      return Object.values(map).filter(n => !childIds.has(n.id));
    }

    function groupByType(nodes) {
      const groups = {};
      nodes.forEach(n => {
        const type = n.component_type || 'Unknown';
        if(!groups[type]) groups[type] = [];
        groups[type].push(n);
      });
      return groups;
    }

    function isPrivateComponent(node) {
      return node.label && node.label.startsWith('_');
    }

    function filterPrivateComponents(nodes, showPrivate) {
      if (showPrivate) return nodes;
      return nodes.filter(node => !isPrivateComponent(node));
    }

    function filterPrivateGroups(groups, showPrivate) {
      if (showPrivate) return groups;
      const filteredGroups = {};
      Object.entries(groups).forEach(([type, list]) => {
        const filteredList = list.filter(node => !isPrivateComponent(node));
        if (filteredList.length > 0) {
          filteredGroups[type] = filteredList;
        }
      });
      return filteredGroups;
    }

    function getComponentTypeClass(componentType) {
      const type = (componentType || '').toLowerCase();
      if (type.includes('data') && (type.includes('processor') || type.includes('source') || type.includes('sink'))) {
        return 'data-processor';
      } else if (type.includes('context') || type.includes('rename') || type.includes('delete')) {
        return 'context-processor';
      } else if (type.includes('source') || type.includes('sink') || type.includes('io')) {
        return 'io-component';
      } else if (type.includes('workflow') || type.includes('pipeline')) {
        return 'workflow';
      }
      return 'default';
    }

    function getComponentTypeBadge(componentType) {
      const type = (componentType || '').toLowerCase();
      if (type.includes('data')) return 'DATA';
      if (type.includes('context')) return 'CTX';
      if (type.includes('source') || type.includes('sink')) return 'I/O';
      if (type.includes('workflow')) return 'WF';
      return 'COMP';
    }

    function getGroupClass(componentType) {
      return `group-${getComponentTypeClass(componentType)}`;
    }

    function filterTreeByGroups(nodes, edges, enabledGroups) {
      // Filter nodes to only include those from enabled groups
      const filteredNodes = nodes.filter(node => {
        const groupType = node.component_type || 'Unknown';
        return enabledGroups.has(groupType);
      });
      
      // Filter edges to only include connections between visible nodes
      const visibleNodeIds = new Set(filteredNodes.map(n => n.id));
      const filteredEdges = edges.filter(edge => 
        visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)
      );
      
      return { nodes: filteredNodes, edges: filteredEdges };
    }

    function App() {
      const [data, setData] = useState(null);
      const [selected, setSelected] = useState(null);
      const [showPrivateComponents, setShowPrivateComponents] = useState(false);
      const [enabledGroups, setEnabledGroups] = useState(new Set());

      // Resizable panels
      const sidebar = useResizable(400, 200, 600);
      const details = useResizableRight(300, 200, 500);

      useEffect(() => {
        fetch('/api/components').then(r => r.json()).then(d => {
          setData(d);
          // Initialize all groups as enabled by default
          const allGroups = new Set();
          d.nodes.forEach(node => {
            const groupType = node.component_type || 'Unknown';
            allGroups.add(groupType);
          });
          setEnabledGroups(allGroups);
        });
      }, []);

      const toggleGroup = (groupType) => {
        setEnabledGroups(prev => {
          const newSet = new Set(prev);
          if (newSet.has(groupType)) {
            newSet.delete(groupType);
          } else {
            newSet.add(groupType);
          }
          return newSet;
        });
      };

      if (!data) return <div className="loading">Loading...</div>;

      // Filter nodes based on private component visibility
      const filteredNodes = filterPrivateComponents(data.nodes, showPrivateComponents);
      
      // Filter nodes and edges based on enabled groups for tree view
      const { nodes: treeNodes, edges: treeEdges } = filterTreeByGroups(
        filteredNodes, 
        data.edges, 
        enabledGroups
      );

      const tree = buildTree(treeNodes, treeEdges);
      const groups = groupByType(filteredNodes);
      const filteredGroups = filterPrivateGroups(groups, showPrivateComponents);

      return (
        <div style={{display:'flex', height:'100%', width:'100%'}}>
          <div id="sidebar" style={{ 
            width: `${sidebar.width}px`,
            position: 'relative'
          }}>
            <div 
              className={`resize-handle resize-handle-right ${sidebar.isResizing ? 'resizing' : ''}`}
              onMouseDown={sidebar.handleMouseDown}
            />
            <h3>Semantiva Components</h3>
            {Object.entries(filteredGroups).map(([type, list]) => (
              <div key={type} className={`component-group ${getGroupClass(type)}`}>
                <h4>
                  <span>{type || 'Unknown Type'}</span>
                  <input 
                    type="checkbox" 
                    className="group-checkbox"
                    checked={enabledGroups.has(type)}
                    onChange={() => toggleGroup(type)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </h4>
                <div>
                  {list.map(item => (
                    <div 
                      key={item.id} 
                      className={`node-item ${selected && selected.id===item.id ? 'selected' : ''}`} 
                      onClick={() => setSelected(item)}
                    >
                      <div style={{ fontWeight: 'bold', marginBottom: '2px' }}>
                        {item.label}
                      </div>
                      <div style={{ fontSize: '11px', color: '#666' }}>
                        {item.input_type && `${item.input_type} →`} {item.output_type}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div id="graph">
            <div className="graph-header">
              <div className="graph-header-content">
                <h3>Semantiva Component Hierarchy</h3>
                <p>Interactive visualization of the component ontology structure and relationships</p>
              </div>
              <div className="header-controls">
                <div className="checkbox-container">
                  <input 
                    type="checkbox" 
                    id="showPrivate" 
                    checked={showPrivateComponents}
                    onChange={(e) => setShowPrivateComponents(e.target.checked)}
                  />
                  <label htmlFor="showPrivate">Show private components</label>
                </div>
              </div>
            </div>
            <div className="tree-container">
              {tree.map(node => (
                <TreeNode key={node.id} node={node} depth={0} onSelect={setSelected} selectedId={selected && selected.id} />
              ))}
            </div>
          </div>
          <div id="details" style={{ 
            width: `${details.width}px`,
            position: 'relative'
          }}>
            <div 
              className={`resize-handle resize-handle-left ${details.isResizing ? 'resizing' : ''}`}
              onMouseDown={details.handleMouseDown}
            />
            {selected ? (
              <div>
                <h3>{selected.label}</h3>
                <div className="details-section">
                  <p><b>Component Type:</b> {selected.component_type}</p>
                  {selected.input_type && <p><b>Input Type:</b> {selected.input_type}</p>}
                  {selected.output_type && <p><b>Output Type:</b> {selected.output_type}</p>}
                  {selected.parameters && selected.parameters !== 'None' && (
                    <p><b>Parameters:</b> {selected.parameters}</p>
                  )}
                </div>
                {selected.docstring && (
                  <div>
                    <h4 style={{ color: '#007acc', marginBottom: '8px' }}>Documentation</h4>
                    <pre>{selected.docstring}</pre>
                  </div>
                )}
              </div>
            ) : (
              <div className="no-selection">
                Select a component to view detailed information
              </div>
            )}
          </div>
        </div>
      );
    }

    ReactDOM.render(React.createElement(App), document.getElementById('root'));
