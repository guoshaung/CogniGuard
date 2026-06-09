import React, { useState } from 'react';
import { GitBranch, Shield, Cpu, RefreshCw, Clock } from 'lucide-react';
import DecisionBadge from './DecisionBadge';

export default function AgentCommunicationGraph({ communicationLogs, pipelineData }) {
  const [selectedRow, setSelectedRow] = useState(null);
  
  const logs = communicationLogs || pipelineData?.communication_logs || [];

  // SVG Coordinates for Diamond Topology Graph
  const center = { x: 250, y: 150, label: 'TPCS Controller', color: 'var(--color-yellow)' };
  
  const nodes = [
    { id: 'profile_diagnosis_agent', x: 100, y: 50, label: 'ProfileDiagnosisAgent', color: 'var(--color-blue)' },
    { id: 'copyright_aware_resource_agent', x: 400, y: 50, label: 'CopyrightAwareResourceAgent', color: 'var(--color-purple)' },
    { id: 'pedagogical_teaching_agent', x: 400, y: 250, label: 'PedagogicalTeachingAgent', color: '#10b981' },
    { id: 'learning_assessment_agent', x: 100, y: 250, label: 'LearningAssessmentAgent', color: '#ec4899' }
  ];

  return (
    <section className="content-stack communications-panel-container">
      {/* Title */}
      <div className="section-header" style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <GitBranch size={28} style={{ color: 'var(--color-yellow)' }} />
          <span>TPCS Governed Multi-Agent Communications (横向主动调配治理大屏)</span>
        </h1>
        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
          Strict network node isolation: cloud-based execution agents are prohibited from direct peer-to-peer data transfers. All intermediate message payloads are horizontally routed and verified by the central TPCSController.
        </p>
      </div>

      {/* SVG Topology Graph Box */}
      <div className="data-panel-card" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div className="data-panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
          <Shield size={16} style={{ color: 'var(--color-yellow)' }} />
          <span>多智能体横向主动监管拓扑网 (TPCS Controlled Diamond Agent Topology Map)</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1.5fr 1fr', gap: '1.5rem', alignItems: 'center' }}>
          
          {/* Left Side: SVG Diamond Graph */}
          <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.25)', border: '1px dashed var(--border-color)', borderRadius: '8px', padding: '1rem', display: 'flex', justifyContent: 'center' }}>
            <svg width="500" height="300" viewBox="0 0 500 300" style={{ width: '100%', maxHeight: '300px' }}>
              {/* Lines from Nodes to Center TPCS */}
              {nodes.map(node => (
                <g key={`line-${node.id}`}>
                  <line
                    x1={node.x}
                    y1={node.y}
                    x2={center.x}
                    y2={center.y}
                    stroke="rgba(255, 255, 255, 0.08)"
                    strokeWidth="2"
                    strokeDasharray="4,4"
                  />
                  <line
                    x1={node.x}
                    y1={node.y}
                    x2={center.x}
                    y2={center.y}
                    stroke={node.color}
                    strokeWidth="1.5"
                    opacity="0.35"
                  />
                  {/* Glowing pulses */}
                  <circle cx={(node.x + center.x)/2} cy={(node.y + center.y)/2} r="3" fill={node.color}>
                    <animate attributeName="r" values="2;5;2" dur="3s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.3;1;0.3" dur="3s" repeatCount="indefinite" />
                  </circle>
                </g>
              ))}

              {/* Central Controller TPCS */}
              <g transform={`translate(${center.x}, ${center.y})`}>
                <circle cx="0" cy="0" r="28" fill="var(--bg-primary)" stroke="var(--color-yellow)" strokeWidth="2.5" style={{ filter: 'drop-shadow(0 0 6px rgba(245,158,11,0.3))' }} />
                <Shield x="-10" y="-10" size={20} style={{ color: 'var(--color-yellow)', transform: 'translate(-10px, -10px)' }} />
                <text x="0" y="38" textAnchor="middle" fill="#ffffff" style={{ fontSize: '10px', fontWeight: 'bold' }}>TPCS Controller</text>
              </g>

              {/* Four Exec Agent Nodes */}
              {nodes.map(node => {
                const isActive = logs.some(l => l.sender === node.label || l.receiver === node.label);
                
                return (
                  <g key={`node-${node.id}`} transform={`translate(${node.x}, ${node.y})`}>
                    <circle
                      cx="0"
                      cy="0"
                      r="18"
                      fill="var(--bg-primary)"
                      stroke={node.color}
                      strokeWidth={isActive ? '2' : '1'}
                      style={{ opacity: isActive ? 1 : 0.6 }}
                    />
                    <Cpu size={14} style={{ color: node.color, transform: 'translate(-7px, -7px)' }} />
                    <text x="0" y={node.y > 150 ? '30' : '-24'} textAnchor="middle" fill="#ffffff" style={{ fontSize: '9px', fontWeight: '500' }}>
                      {node.label.replace('Agent', '')}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Right Side: Educational Principle Card */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.75rem', color: 'var(--color-text-muted)', lineHeight: '1.4' }}>
            <div style={{ borderLeft: '3px solid var(--color-yellow)', paddingLeft: '0.75rem', fontStyle: 'italic' }}>
              “多智能体系统不仅是执行节点的简单串联。各节点间私自、无阻断的数据共享是泄露隐私与教案版权的根源。CogniGuard 横向强力阻断直接串联，确保每次通信都是安全准入的。”
            </div>
            <p style={{ margin: 0 }}>
              在没有 TPCS 主动监管的 Plain RAG 基线系统中，智能体之间可直接发送高敏感的 Prompt 提示词栈。攻击者可以通过其中任意一个后门节点，诱导读取其他节点的画像缓存。
            </p>
            <p style={{ margin: 0, color: 'var(--color-yellow)' }}>
              ✔️ <strong>Diamond 节点安全防护：</strong> TPCS 控制器对每一次智能体握手都会核算 disclosure 画像泄露开销，并动态签发加密流转准入证书，阻止私自直连。
            </p>
          </div>
        </div>
      </div>

      {/* Communications Table */}
      <div className="data-panel" style={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '1.5rem' }}>
        <div className="data-panel-title" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem', marginBottom: '1rem', fontWeight: 700, fontSize: '0.95rem' }}>
          📜 智能体握手与流转报文审计日志 ( Handshake Communication Log Table )
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem', alignItems: 'start' }}>
          {/* Table */}
          <div style={{ overflowX: 'auto' }}>
            <table className="cg-table" style={{ margin: 0 }}>
              <thead>
                <tr>
                  <th>发信源 (Sender)</th>
                  <th>收信源 (Receiver)</th>
                  <th>报文类型 (Type)</th>
                  <th>隐私等级</th>
                  <th>画像开销 (Risk)</th>
                  <th>TPCS 准入 (Decision)</th>
                </tr>
              </thead>
              <tbody>
                {logs.length > 0 ? (
                  logs.map((log, idx) => {
                    const isSelected = selectedRow === idx;
                    return (
                      <tr
                        key={idx}
                        onClick={() => setSelectedRow(isSelected ? null : idx)}
                        style={{
                          cursor: 'pointer',
                          backgroundColor: isSelected ? 'rgba(245,158,11,0.08)' : undefined
                        }}
                      >
                        <td style={{ fontWeight: '500', color: '#ffffff', fontSize: '0.75rem' }}>{log.sender?.replace('Agent', '')}</td>
                        <td style={{ fontWeight: '500', color: '#ffffff', fontSize: '0.75rem' }}>{log.receiver?.replace('Agent', '')}</td>
                        <td style={{ fontSize: '0.7rem' }}>{log.message_type}</td>
                        <td>
                          <span className="risk-badge low" style={{ fontSize: '0.65rem' }}>{log.privacy_level}</span>
                        </td>
                        <td style={{ fontWeight: 'bold', color: log.disclosure_score > 0.3 ? 'var(--color-red)' : 'var(--color-green)', fontSize: '0.75rem' }}>
                          {Number(log.disclosure_score ?? 0).toFixed(2)}
                        </td>
                        <td>
                          <DecisionBadge decision={log.tpcs_decision || 'allow'} />
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="6" style={{ textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.8rem' }}>
                      No active communication logs. Please run a case flow first.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {/* Row Details Panel */}
          <div style={{ backgroundColor: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '1rem', minHeight: '200px' }}>
            {selectedRow !== null && logs[selectedRow] ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.75rem' }}>
                <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                  <strong style={{ color: 'var(--color-yellow)' }}>Handshake Details (握手报文详情)</strong>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)' }}>发信智能体:</span>
                  <div style={{ color: '#ffffff', fontWeight: 'bold' }}>{logs[selectedRow].sender}</div>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)' }}>收信智能体:</span>
                  <div style={{ color: '#ffffff', fontWeight: 'bold' }}>{logs[selectedRow].receiver}</div>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)' }}>握手载荷类别 (Message type):</span>
                  <div style={{ color: '#ffffff' }}>{logs[selectedRow].message_type}</div>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)' }}>横向传输泄露评级 (Disclosure score):</span>
                  <strong style={{ color: logs[selectedRow].disclosure_score > 0.3 ? 'var(--color-red)' : 'var(--color-green)' }}>
                    {Number(logs[selectedRow].disclosure_score ?? 0).toFixed(2)} / 0.75 Budget
                  </strong>
                </div>
                <div>
                  <span style={{ color: 'var(--color-text-muted)' }}>TPCS Controller Routing decision:</span>
                  <div>
                    <DecisionBadge decision={logs[selectedRow].tpcs_decision || 'allow'} />
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '180px', color: 'var(--color-text-muted)', fontSize: '0.8rem', textAlign: 'center' }}>
                <Clock size={20} style={{ marginBottom: '0.5rem', opacity: 0.5 }} />
                <span>点击左侧列表中的行，即可抓取并解密该次智能体握手的横向流转报文详情。</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
