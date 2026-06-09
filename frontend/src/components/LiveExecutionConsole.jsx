import React, { useEffect, useRef } from 'react';
import { Activity, CheckCircle, Clock, MessageSquare, Radio, ShieldCheck, Terminal } from 'lucide-react';

function truncate(value, max = 900) {
  const text = typeof value === 'string' ? value : JSON.stringify(value ?? {}, null, 2);
  if (text.length <= max) return text;
  return `${text.slice(0, max - 3)}...`;
}

function eventLabel(event) {
  const labels = {
    stream_opened: 'Stream opened',
    run_started: 'Run started',
    workflow_step: 'Workflow step emitted',
    tpcs_message: 'TPCS routed message',
    llm_call_started: 'MiMo call started',
    llm_response_delta: 'MiMo text delta',
    llm_call_completed: 'MiMo call completed',
    run_completed: 'Run completed',
    error: 'Error',
  };
  return labels[event.type] || event.type;
}

function eventIcon(type) {
  if (type === 'run_completed') return '✅';
  if (type === 'error') return '❌';
  if (type === 'workflow_step') return '⚡';
  if (type === 'tpcs_message') return '🔄';
  if (type === 'llm_call_started') return '🧠';
  if (type === 'llm_call_completed') return '✨';
  if (type === 'run_started') return '🚀';
  if (type === 'stream_opened') return '📡';
  return '📌';
}

export default function LiveExecutionConsole({
  conversations = [],
  events = [],
  pipelineData,
  running,
  streamStatus,
}) {
  const eventFeedRef = useRef(null);
  const dialogueListRef = useRef(null);
  const stepCount = pipelineData?.workflow_steps?.length || 0;

  // Auto-scroll event feed to bottom when new events arrive
  useEffect(() => {
    if (eventFeedRef.current) {
      const el = eventFeedRef.current;
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [events.length]);

  // Auto-scroll dialogue list to bottom when new conversations arrive
  useEffect(() => {
    if (dialogueListRef.current) {
      const el = dialogueListRef.current;
      el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
    }
  }, [conversations.length, conversations[conversations.length - 1]?.responseText?.length]);

  // Show events in chronological order (oldest first, newest at bottom)
  const displayEvents = events.filter((e) => e.type !== 'llm_response_delta');

  return (
    <div className={`live-console-grid ${running ? 'streaming-active' : ''}`}>
      <div className="live-console-card">
        <div className="live-console-title">
          <Radio size={16} />
          <span>Live Execution Stream</span>
          <span className={`live-pill ${running ? 'active' : streamStatus === 'completed' ? 'done' : 'idle'}`}>
            {running ? 'Streaming' : streamStatus || 'Idle'}
          </span>
        </div>

        <div className="live-stat-row">
          <div className="live-stat">
            <Activity size={14} />
            <span>{stepCount}/12 workflow steps</span>
          </div>
          <div className="live-stat">
            <MessageSquare size={14} />
            <span>{conversations.length} agent calls</span>
          </div>
          <div className="live-stat">
            <ShieldCheck size={14} />
            <span>{pipelineData?.communication_logs?.length || 0} TPCS messages</span>
          </div>
        </div>

        <div className="event-feed" ref={eventFeedRef}>
          {displayEvents.length ? displayEvents.map((event, index) => {
            const isLatest = index === displayEvents.length - 1;
            return (
              <div
                key={`${event.timestamp}-${index}`}
                className={`event-feed-row event-${event.type} event-animate-in ${isLatest && running ? 'event-latest' : ''}`}
                style={{ animationDelay: `${Math.min(index * 50, 300)}ms` }}
              >
                <span className="event-icon-emoji">{eventIcon(event.type)}</span>
                <div>
                  <strong>{eventLabel(event)}</strong>
                  <span>
                    {event.step?.step_name || event.agent_name || event.message?.message_type || event.error || event.knowledge_point || ''}
                  </span>
                </div>
                {isLatest && running && <span className="event-live-dot" />}
              </div>
            );
          }) : (
            <div className="empty-live-state">Click Run Protected Flow to start streaming backend events.</div>
          )}
        </div>
      </div>

      <div className="live-console-card">
        <div className="live-console-title">
          <Terminal size={16} />
          <span>Dynamic MiMo Agent Dialogue</span>
        </div>

        <div className="dialogue-list" ref={dialogueListRef}>
          {conversations.length ? conversations.map((call) => (
            <div key={call.call_id} className={`dialogue-card ${call.status} dialogue-animate-in`}>
              <div className="dialogue-header">
                <strong>{call.agent_name}</strong>
                <span className={`live-pill ${call.status === 'completed' ? 'done' : 'active'}`}>
                  {call.mode || call.status}
                </span>
              </div>

              <div className="dialogue-section">
                <span>Prompt payload</span>
                <pre>{truncate(call.payload, 700)}</pre>
              </div>

              <div className="dialogue-section response">
                <span>Streaming response</span>
                <pre className={call.status === 'streaming' ? 'typewriter-active' : ''}>
                  {call.responseText || (call.status === 'streaming' ? 'Waiting for MiMo response...' : '')}
                  {call.status === 'streaming' && <span className="typewriter-cursor">▊</span>}
                </pre>
              </div>

              {call.error && (
                <div className="dialogue-error">
                  <CheckCircle size={14} />
                  <span>{call.error}</span>
                </div>
              )}
            </div>
          )) : (
            <div className="empty-live-state">MiMo dialogue will appear here as each controlled agent starts.</div>
          )}
        </div>
      </div>
    </div>
  );
}
