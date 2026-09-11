import { Badge, Button, Field, Panel, SearchInput, Tabs } from '../components/ui';
import { operationGroups, recipes } from '../mocks/data';

function OperationLibrary() {
  return <Panel title="Operation Library" actions={<span className="panel-subtitle">64 ops</span>} flush>
    <div style={{padding:8}}><SearchInput placeholder="Operation 검색" /></div>
    <div style={{overflow:'auto', height:'calc(100% - 46px)'}}>
      {operationGroups.map(([group, items]) => <div key={group}>
        <div className="section-label">▾ {group}</div>
        {items.map((item) => <div className="list-item" key={item}><span style={{color:'#72869f'}}>◇</span>{item}<span className="list-meta">+</span></div>)}
      </div>)}
    </div>
  </Panel>;
}

function RecipeExplorer() {
  return <Panel title="Recipes" actions={<Button variant="ghost">＋</Button>} flush>
    <div style={{padding:8}}><SearchInput placeholder="Recipe 검색" /></div>
    <div className="list" style={{overflow:'auto', height:'calc(100% - 46px)'}}>
      {recipes.map((r, i) => <div className={`list-item ${i===0?'active':''}`} key={r.name}>
        <span style={{color:i===0?'#75a5f4':'#6f7b88'}}>◆</span>
        <div style={{minWidth:0}}><div style={{overflow:'hidden',textOverflow:'ellipsis'}}>{r.name}</div><div style={{fontSize:9,color:'var(--text-3)',marginTop:2}}>{r.type} · {r.source} · v{r.version}</div></div>
      </div>)}
    </div>
  </Panel>;
}

function CanvasNode({ title, detail, left, top, selected, decision }: { title:string; detail:string; left:number; top:number; selected?:boolean; decision?:boolean }) {
  return <div className={`node ${selected?'selected':''} ${decision?'decision':''}`} style={{left,top}}>
    <span className="node-port in"/><span className="node-port out"/>
    <div className="node-title">{title}</div><div className="node-body">{detail}</div>
  </div>;
}

function Edge({ x, y, width, rotate=0 }: {x:number;y:number;width:number;rotate?:number}) {
  return <div className="canvas-edge" style={{left:x,top:y,width,transform:`rotate(${rotate}deg)`}}/>;
}

function RecipeCanvas() {
  return <Panel title="Graph Canvas" subtitle="wafer_defect_detection · rev 12" actions={<><Button variant="ghost">Fit</Button><Button variant="ghost">100%</Button></>} flush>
    <div className="recipe-canvas" style={{height:'100%'}}>
      <div className="canvas-toolbar"><Button variant="ghost">↶</Button><Button variant="ghost">↷</Button><Button variant="ghost">⌖</Button></div>
      <Edge x={157} y={207} width={85}/><Edge x={387} y={207} width={90}/><Edge x={620} y={207} width={85}/>
      <Edge x={540} y={235} width={135} rotate={24}/><Edge x={540} y={264} width={135} rotate={-24}/>
      <CanvasNode title="Input Image" detail={'image\nsource: input_image'} left={35} top={165}/>
      <CanvasNode title="Gaussian Blur" detail={'kernel: 5 × 5\nsigma: 1.2'} left={242} top={165}/>
      <CanvasNode title="Global Threshold" detail={'mode: OTSU\nmax: 255'} left={477} top={165} selected/>
      <CanvasNode title="ROI Left" detail={'roi: left_area\noutput: mask'} left={675} top={92}/>
      <CanvasNode title="ROI Right" detail={'roi: right_area\noutput: mask'} left={675} top={255}/>
      <CanvasNode title="Feature Compare" detail={'mask_similarity\nweighted_mean'} left={900} top={165}/>
      <CanvasNode title="Decision" detail={'score >= 0.75\nNG / OK'} left={1100} top={165} decision/>
    </div>
  </Panel>;
}

function NodeInspector() {
  return <Panel title="Node Inspector" subtitle="Global Threshold" flush>
    <Tabs items={['Parameters','Binding','Info']} active="Parameters"/>
    <div className="inspector-section">
      <div className="inspector-heading">General</div>
      <Field label="Mode"><select className="select"><option>OTSU</option><option>BINARY</option></select></Field>
      <Field label="Threshold"><input className="input" value="0" readOnly /></Field>
      <Field label="Max Value"><input className="input" value="255" readOnly /></Field>
    </div>
    <div className="inspector-section">
      <div className="inspector-heading">Input</div>
      <Field label="image"><select className="select"><option>gaussian_blur.image</option></select></Field>
    </div>
    <div className="inspector-section">
      <div className="inspector-heading">Output</div>
      <Field label="binary"><input className="input" value="threshold.binary" readOnly /></Field>
    </div>
    <div className="inspector-section">
      <div className="inspector-heading">Validation</div>
      <div style={{fontSize:10,color:'#7ec9a3'}}>✓ Parameters valid</div>
    </div>
  </Panel>;
}

function PreviewPanel() {
  return <Panel className="preview-panel" flush>
    <Tabs items={['Preview','Intermediate','Analysis','Metrics','Logs']} active="Preview"/>
    <div className="preview-grid">
      {['Input','Gray','Threshold'].map((x,i)=><div className="preview-card" key={x}><div className="preview-image" style={{filter:i===1?'grayscale(1)':'none'}}/><div className="preview-caption"><span>{x}</span><span>{i===0?'2048×1536':i===1?'8-bit':'Binary'}</span></div></div>)}
      <div className="preview-card"><div className="log-view">Run completed in 81.4 ms<br/>7 nodes executed<br/>0 validation errors<br/><span style={{color:'#7ec9a3'}}>Decision: OK</span><br/>Score: 0.8412</div></div>
    </div>
  </Panel>;
}

export function RecipeStudioPage() {
  return <div className="page">
    <div className="page-toolbar">
      <div className="page-title">Recipe Studio</div><Badge status="running">Graph</Badge><span className="page-subtitle">wafer_defect_detection</span>
      <Button>New</Button><Button>Clone</Button><Button>Validate</Button><Button variant="primary">Run</Button><Button>Save</Button><Button variant="danger">Delete</Button>
    </div>
    <div className="page-content" style={{overflow:'hidden'}}>
      <div className="recipe-layout">
        <div className="recipe-left"><RecipeExplorer/><OperationLibrary/></div>
        <RecipeCanvas/><NodeInspector/><PreviewPanel/>
      </div>
    </div>
  </div>;
}
