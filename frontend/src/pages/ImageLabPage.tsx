import { Button, Field, Kpi, Panel, Tabs } from '../components/ui';

export function ImageLabPage() {
  return <div className="page">
    <div className="page-toolbar">
      <div className="page-title">이미지 실험실</div><span className="page-subtitle">단일 이미지 분석 및 Operation/Recipe 빠른 실험</span>
      <Button>Open Image</Button><Button variant="primary">Run</Button>
    </div>
    <div className="page-content" style={{overflow:'hidden'}}>
      <div className="lab-layout">
        <Panel title="Image Viewer" subtitle="SEM_sample_001.png" actions={<><Button variant="ghost">1:1</Button><Button variant="ghost">Fit</Button></>} flush>
          <div className="image-stage" style={{height:'100%'}}><div className="image-placeholder"/><div className="stage-meta">2048 × 1536 · Gray8 · 3.0 MB</div></div>
        </Panel>
        <Panel title="Experiment" flush>
          <Tabs items={['Image Analysis','Operation','Quick Run']} active="Operation"/>
          <div style={{padding:10}}>
            <Field label="Operation"><select className="select"><option>Gaussian Blur</option><option>Global Threshold</option></select></Field>
            <div className="divider"/>
            <div className="inspector-heading">Parameters</div>
            <Field label="Kernel X"><input className="input" value="5" readOnly/></Field>
            <Field label="Kernel Y"><input className="input" value="5" readOnly/></Field>
            <Field label="Sigma X"><input className="input" value="1.2" readOnly/></Field>
            <Field label="Border"><select className="select"><option>DEFAULT</option></select></Field>
            <div style={{display:'flex',gap:6,marginTop:12}}><Button variant="primary">Run Operation</Button><Button>Reset</Button></div>
            <div className="divider"/>
            <div className="inspector-heading">Last Run</div>
            <div style={{fontSize:10,lineHeight:1.7,color:'var(--text-2)'}}>Duration <strong style={{float:'right'}}>12.8 ms</strong><br/>Output <strong style={{float:'right'}}>2048 × 1536</strong><br/>Status <strong style={{float:'right',color:'#7ec9a3'}}>Success</strong></div>
          </div>
        </Panel>
        <div className="analysis-bottom">
          <Panel title="Histogram" subtitle="Gray · 256 bins"><div className="chart-placeholder"/></Panel>
          <Panel title="Image Statistics"><div className="kpi-grid" style={{gridTemplateColumns:'repeat(2,1fr)'}}><Kpi label="Mean" value="126.4"/><Kpi label="Std" value="34.8"/><Kpi label="Min" value="12"/><Kpi label="Max" value="246"/></div></Panel>
          <Panel title="Image Features"><div style={{fontSize:10,lineHeight:2.1,color:'var(--text-2)'}}>Entropy <span style={{float:'right'}}>6.82</span><br/>RMS Contrast <span style={{float:'right'}}>0.213</span><br/>Laplacian Var. <span style={{float:'right'}}>184.7</span><br/>Edge Density <span style={{float:'right'}}>0.081</span><br/>Tenengrad <span style={{float:'right'}}>312.5</span></div></Panel>
        </div>
      </div>
    </div>
  </div>;
}
