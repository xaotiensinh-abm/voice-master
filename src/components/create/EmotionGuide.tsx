/**
 * Static help panel documenting the inline emotion cues supported by VieNeu
 * (experimental). Source: pnnbao97/VieNeu-TTS.
 */
export default function EmotionGuide() {
  return (
    <div className="emotion-guide">
      <div style={{ fontWeight: 600, marginBottom: 'var(--space-2)' }}>
        Tạo cảm xúc bằng thẻ trong văn bản (VieNeu · thử nghiệm)
      </div>
      <p className="text-sm text-muted" style={{ marginBottom: 'var(--space-2)' }}>
        Chèn thẻ cảm xúc ngay trong câu, đặt trước đoạn cần biểu cảm. Ví dụ:
      </p>
      <code className="emotion-guide-example">
        [cười] Trời ơi, cái giọng nó tự nhiên mà mượt mà dã man!
      </code>
      <ul className="emotion-guide-list">
        <li><code>[cười]</code> — cười / vui vẻ</li>
        <li><code>[thở dài]</code> — thở dài / mệt mỏi</li>
        <li><code>[hắng giọng]</code> — hắng giọng</li>
      </ul>
      <p className="text-xs text-muted">
        Mẹo: kết hợp với "Phong cách đọc" và "Cảm xúc" bên dưới để điều chỉnh tốc độ & ngữ điệu tổng thể.
      </p>
    </div>
  );
}
