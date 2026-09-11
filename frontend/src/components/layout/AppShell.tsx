import { NavLink, Outlet, useLocation } from 'react-router-dom';

const navItems = [
  { to: '/recipe-studio', label: 'Recipe Studio', icon: '◆' },
  { to: '/image-lab', label: '이미지 실험실', icon: '▣' },
  { to: '/datasets', label: '데이터셋', icon: '▤' },
  { to: '/evaluations', label: '평가', icon: '▥' },
];

const pageNames: Record<string, string> = {
  '/recipe-studio': 'Recipe Studio',
  '/image-lab': '이미지 실험실',
  '/datasets': '데이터셋',
  '/evaluations': '평가',
  '/settings': '설정',
};

export function AppShell() {
  const location = useLocation();
  const base = Object.keys(pageNames).find((p) => location.pathname.startsWith(p)) ?? '/recipe-studio';
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
          <div className="connection"><span className="connection-dot"/>Connected <span style={{color:'var(--text-3)'}}>v0.6.0</span></div>
          <button className="icon-btn" title="Help">?</button>
          <button className="icon-btn" title="Settings">⚙</button>
        </div>
      </header>
      <Outlet />
    </main>
  </div>;
}
