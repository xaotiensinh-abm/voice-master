import { useState, useCallback } from 'react';
import type { HealthState } from '../hooks/useHealth';

interface AgentConnectProps {
  health: HealthState;
}

const BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'http://127.0.0.1:8757';
const MCP_HTTP_URL = `${BASE_URL}/mcp`; // Streamable HTTP (recommended)
const MCP_SSE_URL = `${BASE_URL}/mcp/sse`; // legacy SSE

const TOOLS: { name: string; desc: string }[] = [
  { name: 'list_voices', desc: 'Liệt kê giọng (id, engine, styles, emotions)' },
  { name: 'get_model_status', desc: 'Trạng thái tải model VieNeu' },
  { name: 'ensure_model_ready', desc: 'Tải model nếu chưa có (mặc định không chờ)' },
  { name: 'synthesize', desc: 'Tạo job từ kịch bản → {job_id,status}' },
  { name: 'get_job_status', desc: 'Tiến độ + audio_url khi xong' },
  { name: 'wait_for_job', desc: 'Chờ tới khi job hoàn thành / timeout' },
  { name: 'download_job_audio', desc: 'Lấy MP3 (copy ra dest_path hoặc base64)' },
  { name: 'get_history', desc: 'Các job đã hoàn thành gần đây' },
  { name: 'cancel_job', desc: 'Hủy job đang chạy/chờ' },
];

const CLI_CMD = `claude mcp add --transport http voice-master ${MCP_HTTP_URL}`;

const MCP_JSON = `{
  "mcpServers": {
    "voice-master": {
      "url": "${MCP_HTTP_URL}"
    }
  }
}`;

const LOOP_EXAMPLE = `from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import json

async def call(s, tool, args):
    r = await s.call_tool(tool, args)
    return json.loads(r.content[0].text)

async with streamablehttp_client("${MCP_HTTP_URL}") as (read, write, *_):
    async with ClientSession(read, write) as s:
        await s.initialize()
        vid = (await call(s, "list_voices", {}))["voices"][0]["voice_id"]
        await call(s, "ensure_model_ready", {})
        for script in scripts:
            job = await call(s, "synthesize", {"text": script, "voice_id": vid})
            await call(s, "wait_for_job", {"job_id": job["job_id"], "timeout_sec": 240})
            await call(s, "download_job_audio",
                       {"job_id": job["job_id"], "dest_path": r"C:\\\\out\\\\%s.mp3" % job["job_id"]})`;

const EMOTION_TAGS: { tag: string; fx: string }[] = [
  { tag: '[cười]', fx: 'cười / vui vẻ' },
  { tag: '[thở dài]', fx: 'thở dài / mệt mỏi, hụt hơi' },
  { tag: '[hắng giọng]', fx: 'hắng giọng, lấy hơi' },
];

const EMOTION_EXAMPLE = `{
  "text": "[cười] Chào cả nhà, rất vui được gặp lại! Hôm nay trời thật đẹp.\\n\\n[thở dài] Nhưng mình vẫn phải bắt tay vào công việc thôi.",
  "voice_id": "vieneu:ngoc_lan",
  "mode": "story",
  "emotion": "warm",
  "speed": 1.0
}`;

function CopyButton({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const onCopy = useCallback(() => {
    navigator.clipboard?.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [value]);
  return (
    <button type="button" className="btn btn-secondary btn-sm" onClick={onCopy} aria-label={label || 'Copy'}>
      {copied ? '✓ Đã chép' : '📋 Copy'}
    </button>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <div className="agent-codeblock">
      <pre><code>{code}</code></pre>
      <div className="agent-codeblock-copy">
        <CopyButton value={code} />
      </div>
    </div>
  );
}

function EndpointRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="agent-endpoint">
      <div className="agent-endpoint-label">{label}</div>
      <code className="agent-endpoint-url">{value}</code>
      <CopyButton value={value} label={`Copy ${label}`} />
    </div>
  );
}

export default function AgentConnect({ health }: AgentConnectProps) {
  const port = health.data?.port ?? 8757;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Kết nối Agent / API</h1>
        <p className="page-subtitle">
          Cho phép agent tạo voice, theo dõi tiến độ và tải file qua MCP hoặc REST (chỉ localhost)
        </p>
      </div>

      <div className="agent-layout">
        {/* Backend status */}
        <div className="card">
          <div className="flex items-center justify-between">
            <h3 className="card-title">Trạng thái backend</h3>
            <span className={`badge ${health.connected ? 'badge-success' : 'badge-error'}`}>
              {health.connected ? '● Đang chạy' : '● Mất kết nối'}
            </span>
          </div>
          <p className="text-sm text-muted" style={{ marginTop: 'var(--space-2)' }}>
            {health.connected
              ? `Cổng ${port}. Agent chỉ kết nối được khi backend đang chạy.`
              : 'Backend chưa chạy — agent sẽ không kết nối được. Mở app Electron hoặc chạy backend.'}
          </p>
        </div>

        {/* Endpoints */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-4)' }}>Endpoint</h3>
          <EndpointRow label="MCP (HTTP) ★" value={MCP_HTTP_URL} />
          <EndpointRow label="MCP (SSE, cũ)" value={MCP_SSE_URL} />
          <EndpointRow label="REST base" value={BASE_URL} />
          <p className="text-xs text-muted" style={{ marginTop: 'var(--space-3)' }}>
            REST: <code>POST /v1/tts/jobs</code> → <code>GET /v1/tts/jobs/{'{id}'}</code> →{' '}
            <code>GET /v1/tts/jobs/{'{id}'}/audio</code>. Model: <code>/models/status</code>,{' '}
            <code>/models/download</code>.
          </p>
        </div>

        {/* Connect MCP client */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-3)' }}>Nối MCP client</h3>
          <div className="input-label" style={{ marginBottom: 'var(--space-1)' }}>Claude Code (CLI)</div>
          <CodeBlock code={CLI_CMD} />
          <div className="input-label" style={{ margin: 'var(--space-3) 0 var(--space-1)' }}>
            Cursor / Claude Desktop (cấu hình SSE)
          </div>
          <CodeBlock code={MCP_JSON} />
        </div>

        {/* Tools */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-3)' }}>Tool có sẵn (9)</h3>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr><th>Tool</th><th>Mô tả</th></tr>
              </thead>
              <tbody>
                {TOOLS.map((t) => (
                  <tr key={t.name}>
                    <td><code>{t.name}</code></td>
                    <td className="text-sm text-muted">{t.desc}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Emotion authoring */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-3)' }}>Thêm cảm xúc vào script</h3>
          <p className="text-sm text-muted" style={{ marginBottom: 'var(--space-2)' }}>
            3 lớp kết hợp được, đều truyền qua tool <code>synthesize</code>:
          </p>
          <ol style={{ paddingLeft: '1.2rem', fontSize: 'var(--font-size-sm)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1)', marginBottom: 'var(--space-3)' }}>
            <li><strong>Thẻ inline trong <code>text</code></strong> (mạnh nhất, chỉ giọng <code>vieneu:*</code>): đặt ngay trước cụm cần biểu cảm.</li>
            <li><strong><code>emotion</code></strong>: neutral / warm / serious / storytelling / excited / sad — ngữ điệu & tốc độ tổng thể.</li>
            <li><strong><code>mode</code></strong> + <code>speed</code>: phong cách đọc (news / story / podcast…).</li>
          </ol>
          <div className="table-wrapper" style={{ marginBottom: 'var(--space-3)' }}>
            <table className="table">
              <thead><tr><th>Thẻ cảm xúc</th><th>Hiệu ứng</th></tr></thead>
              <tbody>
                {EMOTION_TAGS.map((t) => (
                  <tr key={t.tag}><td><code>{t.tag}</code></td><td className="text-sm text-muted">{t.fx}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="input-label" style={{ marginBottom: 'var(--space-1)' }}>Ví dụ synthesize có cảm xúc</div>
          <CodeBlock code={EMOTION_EXAMPLE} />
          <p className="text-xs text-muted" style={{ marginTop: 'var(--space-2)' }}>
            Thẻ inline là tính năng thử nghiệm — đặt thưa, mỗi cụm 1 thẻ, ở đầu câu. ElevenLabs bỏ qua thẻ.
          </p>
        </div>

        {/* Loop example */}
        <div className="card">
          <h3 className="card-title" style={{ marginBottom: 'var(--space-3)' }}>Ví dụ vòng lặp (Python · MCP)</h3>
          <CodeBlock code={LOOP_EXAMPLE} />
          <p className="text-xs text-muted" style={{ marginTop: 'var(--space-3)' }}>
            Hướng dẫn đầy đủ: <code>docs/agent-api.md</code>. Mẫu chạy thật:{' '}
            <code>backend/scripts/agent_smoke.py</code>. Lưu ý: backend chỉ bind localhost, không cần API key.
          </p>
        </div>
      </div>
    </div>
  );
}
