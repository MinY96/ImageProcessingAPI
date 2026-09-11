import { Badge, Button, Panel } from '../components/ui';
import { models } from '../mocks/data';

export function SettingsPage() {
  return <div className="page">
    <div className="page-toolbar"><div className="page-title">설정</div><span className="page-subtitle">Frontend 환경, Runtime, Model Registry, Developer</span></div>
    <div className="page-content" style={{overflow:'hidden'}}>
      <div className="settings-layout">
        <Panel className="settings-nav" flush><div className="settings-item active">General</div><div className="settings-item">Runtime</div><div className="settings-item">Model Registry</div><div className="settings-item">Developer</div></Panel>
        <Panel><div className="settings-section"><div className="settings-title">General</div><div className="settings-desc">화면 표시 및 기본 실행 옵션을 설정합니다.</div>
          <div className="setting-row"><div><div className="setting-name">Theme</div><div className="setting-help">Application theme</div></div><select className="select"><option>Dark</option></select></div>
          <div className="setting-row"><div><div className="setting-name">Canvas Grid</div><div className="setting-help">Recipe Canvas grid 표시</div></div><select className="select"><option>On</option><option>Off</option></select></div>
          <div className="setting-row"><div><div className="setting-name">Auto Fit</div><div className="setting-help">Recipe를 열 때 전체 Graph 자동 맞춤</div></div><select className="select"><option>On</option><option>Off</option></select></div>
          <div className="setting-row"><div><div className="setting-name">Default Response Format</div><div className="setting-help">Recipe 실행 기본 결과 형식</div></div><select className="select"><option>JSON</option><option>ZIP</option></select></div>
          <div className="setting-row"><div><div className="setting-name">Evaluation Polling</div><div className="setting-help">Job 상태 조회 주기</div></div><select className="select"><option>2 seconds</option><option>1 second</option></select></div>
          <div style={{marginTop:14}}><Button variant="primary">Save Settings</Button></div>
          <div className="divider"/><div className="settings-title" style={{marginTop:14}}>Runtime</div><div className="settings-desc">현재 Backend 연결 상태입니다.</div>
          <div className="setting-row"><div><div className="setting-name">Backend</div><div className="setting-help">http://localhost:8000</div></div><Badge status="completed">Connected</Badge></div>
          <div className="setting-row"><div><div className="setting-name">API Version</div><div className="setting-help">Evaluation Job Queue v1</div></div><span style={{fontSize:10}}>v0.6.0</span></div>
          <div className="divider"/><div className="settings-title" style={{marginTop:14}}>Model Registry</div><div className="settings-desc">현재 Backend에 등록된 모델은 읽기 전용입니다.</div>
          <table><thead><tr><th>Model ID</th><th>Version</th><th>Algorithm</th><th>Labels</th><th>Features</th></tr></thead><tbody>{models.map(m=><tr key={m.id}><td>{m.id}</td><td>{m.version}</td><td>{m.algorithm}</td><td>{m.labels}</td><td>{m.features}</td></tr>)}</tbody></table>
          <div className="divider"/><div className="settings-title" style={{marginTop:14}}>Developer</div><div className="settings-desc">FastAPI에서 제공하는 개발 문서로 이동합니다.</div><div style={{display:'flex',gap:6}}><Button>Swagger UI</Button><Button>ReDoc</Button><Button>OpenAPI JSON</Button></div>
        </div></Panel>
      </div>
    </div>
  </div>;
}
