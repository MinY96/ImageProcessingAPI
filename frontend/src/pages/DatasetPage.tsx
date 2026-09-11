import { useState } from 'react';
import { Badge, Button, Panel, SearchInput, Tabs } from '../components/ui';
import { datasets } from '../mocks/data';

const images = Array.from({length:18},(_,i)=>({name:`SEM_${String(i+1).padStart(4,'0')}.png`,label:i%5===0?'NG':'OK'}));

function TestDatasetView() {
  return <div className="dataset-layout">
    <Panel title="Datasets" actions={<Button variant="ghost">＋</Button>} flush>
      <div style={{padding:8}}><SearchInput placeholder="Dataset 검색"/></div>
      <div className="list" style={{overflow:'auto',height:'calc(100% - 46px)'}}>
        {datasets.map((d,i)=><div className={`list-item ${i===0?'active':''}`} key={d.name}><div><div>{d.name}</div><div style={{fontSize:9,color:'var(--text-3)',marginTop:2}}>{d.images.toLocaleString()} images · rev {d.revision}</div></div><span className="list-meta">›</span></div>)}
      </div>
    </Panel>
    <Panel title="SEM_Wafer_Test_V3" subtitle="1,240 images · revision 9" actions={<><Button>Edit</Button><Button variant="danger">Delete</Button></>} flush>
      <div className="dataset-browser">
        <div className="dataset-browser-toolbar"><div style={{width:220}}><SearchInput placeholder="이미지 검색"/></div><select className="select" style={{width:110}}><option>All Labels</option><option>OK</option><option>NG</option></select><Button>Set OK</Button><Button>Set NG</Button><Button>Clear</Button><span style={{marginLeft:'auto',fontSize:9,color:'var(--text-3)'}}>0 selected</span></div>
        <div className="thumb-grid">
          {images.map((img)=><div className={`thumb ${img.label==='NG'?'ng':''}`} key={img.name}><div className="thumb-img"/><div className="thumb-footer"><input type="checkbox"/><span style={{overflow:'hidden',textOverflow:'ellipsis'}}>{img.name}</span><Badge status={img.label==='NG'?'failed':'completed'}>{img.label}</Badge></div></div>)}
        </div>
      </div>
    </Panel>
  </div>;
}

function AnnotationView() {
  return <div className="annotation-layout">
    <Panel title="Images" actions={<Button variant="ghost">＋</Button>} flush>
      <div style={{padding:8}}><SearchInput placeholder="Label Document 검색"/></div>
      <div className="list">
        {['SEM_0001.png','SEM_0002.png','SEM_0003.png','SEM_0004.png','SEM_0005.png'].map((x,i)=><div key={x} className={`list-item ${i===0?'active':''}`}><span>▧</span><div><div>{x}</div><div style={{fontSize:9,color:'var(--text-3)',marginTop:2}}>{i===0?'2 annotations':'No annotation'}</div></div></div>)}
      </div>
    </Panel>
    <Panel title="Annotation Editor" subtitle="SEM_0001.png · 2048 × 1536" flush>
      <div style={{height:'100%',display:'grid',gridTemplateRows:'43px 1fr'}}>
        <div className="annotation-toolbar"><Button variant="primary">BBox</Button><Button>Polygon</Button><Button>Point</Button><Button>Polyline</Button><span style={{flex:1}}/><Button>Fit</Button><Button>1:1</Button></div>
        <div className="annotation-stage"><div className="annotation-image"><div className="annotation-box"/><div className="annotation-poly"/></div></div>
      </div>
    </Panel>
    <Panel title="Annotations" subtitle="2 objects" flush>
      <div className="list"><div className="list-item active"><span style={{color:'#d98b6c'}}>□</span><div><div>scratch</div><div style={{fontSize:9,color:'var(--text-3)'}}>bbox · ann_001</div></div></div><div className="list-item"><span style={{color:'#7da3d8'}}>◇</span><div><div>pattern</div><div style={{fontSize:9,color:'var(--text-3)'}}>polygon · ann_002</div></div></div></div>
      <div className="inspector-section"><div className="inspector-heading">Selected Annotation</div><div className="field"><div className="field-label">Class</div><select className="select"><option>scratch</option><option>particle</option><option>pattern</option></select></div><div className="field"><div className="field-label">Tag</div><input className="input" value="surface" readOnly/></div><div style={{display:'flex',gap:6,marginTop:10}}><Button>Update</Button><Button variant="danger">Delete</Button></div></div>
      <div className="inspector-section"><div className="inspector-heading">Class Summary</div><div style={{fontSize:10,lineHeight:2,color:'var(--text-2)'}}>scratch <span style={{float:'right'}}>1,250</span><br/>particle <span style={{float:'right'}}>820</span><br/>pattern <span style={{float:'right'}}>150</span></div></div>
    </Panel>
  </div>;
}

export function DatasetPage() {
  const [tab, setTab] = useState('Test Dataset');
  return <div className="page">
    <div className="page-toolbar">
      <div className="page-title">데이터셋</div><span className="page-subtitle">Test Dataset · Ground Truth · Annotation</span>
      {tab === 'Test Dataset' ? <><Button>Import Folder</Button><Button variant="primary">New Dataset</Button></> : <><Button>Class Summary</Button><Button variant="primary">New Label Document</Button></>}
    </div>
    <Tabs items={['Test Dataset','Annotation']} active={tab} onChange={setTab}/>
    <div className="page-content" style={{overflow:'hidden'}}>{tab === 'Test Dataset' ? <TestDatasetView/> : <AnnotationView/>}</div>
  </div>;
}
