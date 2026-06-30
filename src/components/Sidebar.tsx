interface SidebarProps {
  activeScreen: string;
  onNavigate: (screen: 'create' | 'library' | 'history' | 'settings' | 'diagnostics' | 'agent') => void;
  connected: boolean;
  version: string;
}

const navItems = [
  { id: 'create' as const, icon: '🎤', label: 'Tạo giọng nói' },
  { id: 'library' as const, icon: '📚', label: 'Thư viện giọng' },
  { id: 'history' as const, icon: '📋', label: 'Lịch sử' },
  { id: 'agent' as const, icon: '🔌', label: 'Kết nối Agent / API' },
  { id: 'settings' as const, icon: '⚙️', label: 'Cài đặt' },
  { id: 'diagnostics' as const, icon: '🔧', label: 'Chẩn đoán' },
];

export default function Sidebar({ activeScreen, onNavigate, connected, version }: SidebarProps) {
  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">🎙</div>
          <div className="sidebar-logo-text">
            <span className="sidebar-logo-title">Voice-Master</span>
            <span className="sidebar-logo-subtitle">Vietnamese TTS</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <button
            type="button"
            key={item.id}
            className={`sidebar-nav-item ${activeScreen === item.id ? 'active' : ''}`}
            aria-current={activeScreen === item.id ? 'page' : undefined}
            aria-label={item.label}
            onClick={() => onNavigate(item.id)}
          >
            <span className="sidebar-nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="sidebar-status">
          <span className={`sidebar-status-dot ${connected ? 'connected' : 'disconnected'}`} />
          <span>{connected ? 'Backend sẵn sàng' : 'Mất kết nối backend'}</span>
        </div>
        {version && (
          <div className="sidebar-version">v{version}</div>
        )}
        <div className="sidebar-author">
          <div className="sidebar-author-name">Tác giả: ABM · DũngTQ</div>
          <a className="sidebar-author-phone" href="tel:0976202028">📞 0976202028</a>
          <div className="sidebar-author-note">Liên hệ nếu cần thêm thông tin</div>
        </div>
      </div>
    </aside>
  );
}
