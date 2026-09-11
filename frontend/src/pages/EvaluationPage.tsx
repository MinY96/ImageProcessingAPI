import { useState } from 'react';
import { Badge, Button, Kpi, Modal, Panel, ProgressBar, SearchInput } from '../components/ui';
import { evaluations } from '../mocks/data';

function EvaluationWizard({ onClose }: { onClose: () => void }) {
  return <Modal title="New Evaluation" onClose={onClose} footer={<><Button onClick={onClose}>Cancel</Button><Button variant="primary">Run Evaluation</Button></>}>
    <div className="wizard-steps">{['Dataset','Recipe','Binding','Labels','Inputs','Options','Submit'].map((s,i)=><div className={`wizard-step ${i===0?'active':''}`} key={s}>{i+1}. {s}</div>)}</div>
    <div className="form-grid">
      <div className="form-group"><label>Test Dataset</label><select className="select"><option>SEM_Wafer_Test_V3</option><option>Pattern_Scratch_Set</option></select></div>
      <div className="form-group"><label>Decision Recipe</label><select className="select"><option>wafer_defect_detection</option><option>binary_contour_inspection</option></select></div>
      <div className="form-group"><label>Image Input</label><select className="select"><option>input_image</option></select></div>
      <div className="form-group"><label>Decision Output</label><select className="select"><option>decision.result</option></select></div>
      <div className="form-group"><label>Score Output</label><select className="select"><option>decision.score</option></select></div>
      <div className="form-group"><label>OK Label</label><input className="input" value="OK" readOnly/></div>
      <div className="form-group"><label>NG Label</label><input className="input" value="NG" readOnly/></div>
      <div className="form-group"><label>Shared Image Inputs</label><input className="input" placeholder="Optional"/></div>
    </div>
    <div className="divider"/>
    <div className="checkbox-row"><label><input type="checkbox"/> Capture Node Values</label><label><input type="checkbox" defaultChecked/> Fail On Unlabeled</label></div>
    <div style={{marginTop:12,fontSize:9,color:'var(--text-3)',lineHeight:1.6}}>Submit 시 Dataset/Recipe revision이 snapshot으로 저장되며, Queue 대기 중 변경되면 Job이 failed 처리됩니다.</div>
  </Modal>;
}

export function EvaluationPage() {
  const [wizardOpen, setWizardOpen] = useState(false);
  return <div className="page">
    {wizardOpen && <EvaluationWizard onClose={()=>setWizardOpen(false)}/>} 
    <div className="page-toolbar">
      <div className="page-title">평가</div><span className="page-subtitle">Dataset + Decision Recipe 성능 검증</span>
      <div style={{width:210}}><SearchInput placeholder="Evaluation 검색"/></div><Button variant="primary" onClick={()=>setWizardOpen(true)}>New Evaluation</Button>
    </div>
    <div className="page-content" style={{overflow:'hidden'}}>
      <div className="eval-layout">
        <div className="active-jobs">
          <div className="job-card"><div className="job-top"><div className="job-title">SEM_Wafer_Test_V3</div><Badge status="running">Running</Badge></div><div className="job-meta">wafer_defect_detection · EV-260910-0043</div><div className="job-progress"><ProgressBar value={43.7}/><strong style={{fontSize:10}}>43.7%</strong></div><div className="job-meta">437 / 1,000 images <span style={{float:'right',color:'#dda961'}}>Cancel</span></div></div>
          <div className="job-card"><div className="job-top"><div className="job-title">Hole_CD_Evaluation</div><Badge status="queued">Queued</Badge></div><div className="job-meta">binary_contour_inspection · EV-260910-0044</div><div style={{height:18}}/><div className="job-meta">Waiting for worker · Queue #1</div></div>
          <div className="job-card"><div className="job-top"><div className="job-title">Worker</div><Badge status="completed">Healthy</Badge></div><div className="job-meta">1 worker · checkpoint every 50 images</div><div style={{height:18}}/><div className="job-meta">Interactive Recipe Run remains available</div></div>
        </div>
        <div className="eval-main">
          <Panel title="Evaluation History" actions={<select className="select" style={{width:110}}><option>All Status</option><option>Completed</option><option>Failed</option></select>} flush>
            <div className="table-wrap"><table><thead><tr><th>Evaluation ID</th><th>Status</th><th>Dataset</th><th>Recipe</th><th>Progress</th><th>Accuracy</th><th>F1</th><th>Created</th></tr></thead><tbody>{evaluations.map((e,i)=><tr key={e.id} className={i===0?'selected':''}><td>{e.id}</td><td><Badge status={e.status}>{e.status}</Badge></td><td>{e.dataset}</td><td>{e.recipe}</td><td>{e.progress}%</td><td>{e.accuracy}</td><td>{e.f1}</td><td>{e.created}</td></tr>)}</tbody></table></div>
          </Panel>
          <Panel title="Evaluation Detail" subtitle="EV-260910-0042" flush>
            <div style={{padding:10}}>
              <div className="kpi-grid" style={{gridTemplateColumns:'repeat(3,1fr)'}}><Kpi label="Accuracy" value="98.2%"/><Kpi label="Recall" value="96.9%"/><Kpi label="F1" value="97.6%"/></div>
              <div className="divider"/><div className="inspector-heading">Confusion Matrix</div>
              <div className="matrix"><div className="axis"></div><div className="axis">Pred OK</div><div className="axis">Pred NG</div><div className="axis">GT OK</div><div className="good">TN<br/><strong>948</strong></div><div className="bad">FP<br/><strong>17</strong></div><div className="axis">GT NG</div><div className="bad">FN<br/><strong>9</strong></div><div className="good">TP<br/><strong>266</strong></div></div>
              <div className="divider"/><div className="inspector-heading">Execution</div>
              <div style={{fontSize:10,lineHeight:1.9,color:'var(--text-2)'}}>Evaluated Images <span style={{float:'right'}}>1,240</span><br/>Errors <span style={{float:'right'}}>0</span><br/>Mean Latency <span style={{float:'right'}}>84.1 ms</span><br/>P95 Latency <span style={{float:'right'}}>110.8 ms</span></div>
              <div style={{display:'flex',gap:6,marginTop:10}}><Button>View Results</Button><Button>False NG</Button><Button>Missed NG</Button></div>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  </div>;
}
