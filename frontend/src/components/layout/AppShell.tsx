import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { systemApi } from '../../api';

const navItems = [
  { to: '/recipe-studio', label: 'Recipe Studio', icon: '◆' },
  { to: '/image-lab', label: '이미지 실험실', icon: '▣' },
  { to: '/synthetic-ng', label: 'Synthetic NG', icon: '✦' },
  { to: '/datasets', label: '데이터셋', icon: '▤' },
  { to: '/evaluations', label: '평가', icon: '▥' },
];

const pageNames: Record<string, string> = {
  '/recipe-studio': 'Recipe Studio',
  '/image-lab': '이미지 실험실',
  '/synthetic-ng': 'Synthetic NG Generator',
  '/datasets': '데이터셋',
  '/evaluations': '평가',
  '/settings': '설정',
};

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const base = Object.keys(pageNames).find((p) => location.pathname.startsWith(p)) ?? '/recipe-studio';
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    const check = async () => {
      try {
        const result = await systemApi.health();
        if (active) setConnected(result.status === 'ok');
      } catch {
        if (active) setConnected(false);
      }
    };
    void check();
    const timer = window.setInterval(check, 10000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">IP</div>
        <div><div className="brand-title">Image Processing Studio</div><div className="brand-sub">Vision Recipe IDE</div></div>
      </div>
      <nav className="nav">
        {navItems.map((item) => <NavLink key={item.to} to={item.to} className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}>
          <span className="nav-icon">{item.icon}</span><span>{item.label}</span>
        </NavLink>)}
      </nav>
      <div className="nav-bottom">
        <NavLink to="/settings" className={({isActive}) => `nav-link ${isActive ? 'active' : ''}`}><span className="nav-icon">⚙</span><span>설정</span></NavLink>
      </div>
    </aside>
    <main className="main-shell">
      <header className="app-header">
        <div className="breadcrumb"><strong>{pageNames[base]}</strong><span>›</span><span>Workspace</span></div>
        <div className="header-actions">
          <div className={`connection ${connected === false ? 'disconnected' : ''}`}><span className="connection-dot"/>{connected == null ? 'Checking' : connected ? 'Connected' : 'Disconnected'} <span style={{color:'var(--text-3)'}}>API v0.6.x</span></div>
          <button className="icon-btn" title="Swagger UI" onClick={() => window.open('/docs', '_blank')}>?</button>
          <button className="icon-btn" title="Settings" onClick={() => navigate('/settings')}>⚙</button>
        </div>
      </header>
      <Outlet />
    </main>
  </div>;
}
