import { useState, useCallback } from 'react';
import { useVoices } from '../hooks/useVoices';
import { apiClient } from '../lib/apiClient';
import type { Voice, EngineName, VoiceStyle } from '../types';

const ENGINE_LABELS: Record<EngineName, string> = {
  vieneu: 'VieNeu',
  elevenlabs: 'ElevenLabs',
};

const STYLE_LABELS: Record<VoiceStyle, string> = {
  neutral: 'Trung tính',
  news: 'Tin tức',
  story: 'Đọc truyện',
  podcast: 'Podcast',
};

export default function VoiceLibrary() {
  const [engineFilter, setEngineFilter] = useState<EngineName | ''>('');
  const [styleFilter, setStyleFilter] = useState<VoiceStyle | ''>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [previewAudio, setPreviewAudio] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);

  const filters = {
    ...(engineFilter ? { engine: engineFilter as EngineName } : {}),
    ...(styleFilter ? { style: styleFilter as VoiceStyle } : {}),
  };
  const { voices, loading } = useVoices(Object.keys(filters).length > 0 ? filters : undefined);

  const filteredVoices = voices.filter((v) =>
    v.display_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleFavorite = useCallback((voiceId: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(voiceId)) {
        next.delete(voiceId);
      } else {
        next.add(voiceId);
      }
      return next;
    });
  }, []);

  const handlePreview = useCallback(async (voice: Voice) => {
    setPreviewingId(voice.voice_id);
    try {
      const result = await apiClient.previewVoice({
        voice_id: voice.voice_id,
        text: 'Xin chào, đây là giọng đọc mẫu.',
        output_format: 'mp3',
      });
      setPreviewAudio(apiClient.getPreviewAudioUrl(result.preview_id));
    } catch {
      // ignore
    } finally {
      setPreviewingId(null);
    }
  }, []);

  const getStatusBadge = (voice: Voice) => {
    if (!voice.available) {
      return <span className="badge badge-warning">Chưa sẵn sàng</span>;
    }
    return <span className="badge badge-success">Sẵn sàng</span>;
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Thư viện giọng</h1>
        <p className="page-subtitle">Khám phá và quản lý tất cả giọng nói có sẵn</p>
      </div>

      {/* Filters Bar */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="flex items-center gap-4" style={{ flexWrap: 'wrap' }}>
          {/* Search */}
          <div className="search-box" style={{ flex: 1, minWidth: 220 }}>
            <span className="search-box-icon">🔍</span>
            <input
              type="text"
              className="input"
              placeholder="Tìm theo tên giọng..."
              aria-label="Search voices"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Engine */}
          <select
            className="select"
            style={{ width: 180 }}
            value={engineFilter}
            aria-label="Filter voices by engine"
            onChange={(e) => setEngineFilter(e.target.value as EngineName | '')}
          >
            <option value="">Tất cả engine</option>
            <option value="vieneu">VieNeu</option>
            <option value="elevenlabs">ElevenLabs</option>
          </select>

          {/* Style */}
          <select
            className="select"
            style={{ width: 180 }}
            value={styleFilter}
            aria-label="Filter voices by style"
            onChange={(e) => setStyleFilter(e.target.value as VoiceStyle | '')}
          >
            <option value="">Tất cả phong cách</option>
            <option value="neutral">Trung tính</option>
            <option value="news">Tin tức</option>
            <option value="story">Đọc truyện</option>
            <option value="podcast">Podcast</option>
          </select>

          <span className="text-sm text-muted">
            {filteredVoices.length} giọng
          </span>
        </div>
      </div>

      {/* Voices Table */}
      {loading ? (
        <div className="card">
          <div className="skeleton" style={{ height: 40, marginBottom: 'var(--space-3)' }} />
          <div className="skeleton" style={{ height: 40, marginBottom: 'var(--space-3)' }} />
          <div className="skeleton" style={{ height: 40, marginBottom: 'var(--space-3)' }} />
          <div className="skeleton" style={{ height: 40, marginBottom: 'var(--space-3)' }} />
          <div className="skeleton" style={{ height: 40 }} />
        </div>
      ) : filteredVoices.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📚</div>
            <div className="empty-state-title">Chưa có giọng nào</div>
            <div className="empty-state-text">
              Không tìm thấy giọng nào phù hợp. Thử thay đổi bộ lọc hoặc kiểm tra kết nối backend.
            </div>
          </div>
        </div>
      ) : (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }} />
                <th>Tên giọng</th>
                <th>Engine</th>
                <th>Phong cách</th>
                <th>Cảm xúc</th>
                <th>License</th>
                <th>Trạng thái</th>
                <th style={{ width: 100 }}>Xem trước</th>
              </tr>
            </thead>
            <tbody>
              {filteredVoices.map((voice) => (
                <tr key={voice.voice_id}>
                  <td>
                    <button
                      type="button"
                      className={`star-btn ${favorites.has(voice.voice_id) ? 'active' : ''}`}
                      onClick={() => toggleFavorite(voice.voice_id)}
                      title={favorites.has(voice.voice_id) ? 'Bỏ yêu thích' : 'Yêu thích'}
                      aria-label={`${favorites.has(voice.voice_id) ? 'Remove favorite' : 'Add favorite'} ${voice.display_name}`}
                      aria-pressed={favorites.has(voice.voice_id)}
                    >
                      {favorites.has(voice.voice_id) ? '★' : '☆'}
                    </button>
                  </td>
                  <td>
                    <span style={{ fontWeight: 600, color: 'var(--color-gray-800)' }}>
                      {voice.display_name}
                    </span>
                  </td>
                  <td>
                    <span className={`badge badge-engine-${voice.engine}`}>
                      {ENGINE_LABELS[voice.engine]}
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                      {voice.styles.map((s) => (
                        <span key={s} className="badge badge-neutral">
                          {STYLE_LABELS[s] || s}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    <div className="flex gap-2" style={{ flexWrap: 'wrap' }}>
                      {voice.emotions && voice.emotions.length > 0 ? (
                        voice.emotions.map((e) => (
                          <span key={e} className="badge badge-info" style={{ fontSize: '0.7rem' }}>
                            {e}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-muted">—</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className="text-sm text-muted">{voice.license || '—'}</span>
                  </td>
                  <td>{getStatusBadge(voice)}</td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-sm btn-ghost"
                      onClick={() => handlePreview(voice)}
                      disabled={previewingId === voice.voice_id || !voice.available}
                      aria-label={`Preview voice ${voice.display_name}`}
                      title={voice.available ? `Preview ${voice.display_name}` : `${voice.display_name} is not available`}
                    >
                      {previewingId === voice.voice_id ? (
                        <span className="spinner" style={{ width: 14, height: 14 }} />
                      ) : (
                        '▶ Nghe'
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Hidden audio */}
      {previewAudio && (
        <audio
          src={previewAudio}
          autoPlay
          onEnded={() => setPreviewAudio(null)}
          style={{ display: 'none' }}
        />
      )}
    </div>
  );
}
