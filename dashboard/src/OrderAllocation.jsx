import React, {useEffect,useState} from 'react';
import {MapContainer,Marker,Popup,TileLayer} from 'react-leaflet';
import L from 'leaflet';
import {FileUp,MapPin,Package,CheckCircle2,AlertTriangle} from 'lucide-react';

const pin=new L.Icon({iconUrl:'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',shadowUrl:'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',iconSize:[25,41],iconAnchor:[12,41]});
const COLUMNS=['order_reference','title','pickup_address','pickup_lat','pickup_lng','delivery_address','delivery_lat','delivery_lng','customer_name','customer_phone','due_at','priority','vehicle_type','instructions'];
const required=COLUMNS.slice(0,12);
async function api(path,token,options={}){
 const res=await fetch('/api'+path,{...options,headers:{'Content-Type':'application/json',Authorization:'Bearer '+token,...(options.headers||{})}});
 const result=await res.json().catch(()=>({}));
 if(!res.ok)throw Error(typeof result.detail==='string'?result.detail:'Request failed ('+res.status+')');
 return result;
}
// RFC4180-style parser for quoted fields, embedded commas, and escaped quotes.
export function parseCSV(text){
 const lines=[];let row=[],cell='',quoted=false;const input=text.replace(/^\uFEFF/,'');
 for(let i=0;i<input.length;i++){
  const ch=input[i];
  if(ch==='"'){
   if(quoted&&input[i+1]==='"'){cell+='"';i++;}
   else quoted=!quoted;
  }else if(ch===','&&!quoted){row.push(cell);cell='';}
  else if((ch==='\n'||ch==='\r')&&!quoted){if(ch==='\r'&&input[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v.trim()))lines.push(row);row=[];cell='';}
  else cell+=ch;
 }
 if(quoted)throw Error('Unclosed quoted CSV field');
 row.push(cell);if(row.some(v=>v.trim()))lines.push(row);
 if(lines.length<2)throw Error('CSV requires a header and at least one order');
 const columns=lines.shift().map(v=>v.trim().toLowerCase());
 if(new Set(columns).size!==columns.length)throw Error('Duplicate CSV header names');
 const missing=required.filter(c=>!columns.includes(c));
 if(missing.length)throw Error('Missing required columns: '+missing.join(', '));
 if(lines.length>100)throw Error('Maximum 100 orders per import');
 return lines.map((values,i)=>{
  if(values.length!==columns.length)throw Error('Row '+(i+2)+' has a different number of columns');
  const order=Object.fromEntries(columns.map((name,k)=>[name,values[k].trim()]));
  for(const field of ['pickup_lat','pickup_lng','delivery_lat','delivery_lng']){
   if(order[field]==='')throw Error('Row '+(i+2)+' is missing '+field);
   order[field]=Number(order[field]);if(!Number.isFinite(order[field]))throw Error('Row '+(i+2)+' has invalid '+field);
  }
  return {...order,priority:order.priority||'normal',vehicle_type:order.vehicle_type||'',instructions:order.instructions||''};
 });
}
function template(){
 const future=new Date(Date.now()+3*24*3600000).toISOString();
 const row=['DEMO-ORDER-001','Sample package','Office pickup, Bengaluru','13.011568','77.668173','Sample delivery entrance, Bengaluru','13.015','77.675','Demo recipient','9876543210',future,'normal','Truck','Demo only'];
 const csv=[COLUMNS,row].map(line=>line.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n');
 const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='KRIYA360_unassigned_orders_template.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
const fmtTime=v=>v?new Date(v).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'}):'—';
function PickupMap({order,drivers,selected}){
 return <div style={{height:270,borderRadius:12,overflow:'hidden',marginTop:12}}>
 <MapContainer center={[order.pickup_lat,order.pickup_lng]} zoom={12} style={{height:'100%',width:'100%'}} scrollWheelZoom={false}>
 <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors"/>
 <Marker icon={pin} position={[order.pickup_lat,order.pickup_lng]}><Popup>Pickup: {order.pickup_address}</Popup></Marker>
 <Marker icon={pin} position={[order.delivery_lat,order.delivery_lng]}><Popup>Delivery: {order.delivery_address}</Popup></Marker>
 {drivers.filter(d=>d.lat!=null&&d.lng!=null).map(d=><Marker key={d.driver_id} icon={pin} position={[d.lat,d.lng]}><Popup>{d.name}<br/>{d.location_source==='fresh_gps'?'Fresh driver GPS':'Estimated after active task'}<br/>{d.distance_to_pickup_km??'Unknown'} km straight-line to pickup</Popup></Marker>)}
 </MapContainer>
 </div>;
}
export default function OrderAllocation({token,onAssigned}){
 const [fileName,setFileName]=useState(''),[items,setItems]=useState([]),[preview,setPreview]=useState(null),[orders,setOrders]=useState([]),[chosen,setChosen]=useState(null),[recommendations,setRecommendations]=useState([]),[selectedDriver,setSelectedDriver]=useState(''),[error,setError]=useState(''),[info,setInfo]=useState(''),[busy,setBusy]=useState(false);
 async function refresh(){try{setOrders(await api('/orders?status=all',token))}catch(e){setError(e.message)}}
 useEffect(()=>{refresh()},[token]);
 async function upload(file){if(!file)return;setError('');setInfo('');setPreview(null);setFileName(file.name);
  try{const parsed=parseCSV(await file.text());setItems(parsed);setPreview(await api('/orders/bulk-preview',token,{method:'POST',body:JSON.stringify({orders:parsed})}));}
  catch(e){setItems([]);setError(e.message)}
 }
 async function importBatch(){if(!preview||preview.invalid||!items.length)return;setBusy(true);setError('');try{const r=await api('/orders/bulk-import',token,{method:'POST',body:JSON.stringify({orders:items})});setInfo(r.imported+' orders imported as Unassigned; no driver notified.');setPreview(null);setItems([]);setFileName('');await refresh()}catch(e){setError(e.message)}finally{setBusy(false)}}
 async function selectOrder(o){setChosen(o);setSelectedDriver('');setRecommendations([]);setError('');try{const r=await api('/orders/'+encodeURIComponent(o.id)+'/recommendations',token);setRecommendations(r.recommendations||[])}catch(e){setError(e.message)}}
 async function assign(){if(!chosen||!selectedDriver)return;setBusy(true);setError('');try{await api('/orders/'+encodeURIComponent(chosen.id)+'/assign',token,{method:'POST',body:JSON.stringify({driver_id:selectedDriver})});setInfo('Order assigned successfully; driver task queued.');setChosen(null);setSelectedDriver('');await refresh();onAssigned?.()}catch(e){setError(e.message)}finally{setBusy(false)}}
 const pending=orders.filter(o=>o.status==='unassigned');const assigned=orders.filter(o=>o.status==='assigned');
 return <section className="card allocation-panel" aria-label="Intelligent bulk order allocation">
  <div className="card-heading"><div><h3>Intelligent Order Allocation</h3><p>Import orders without drivers. Review eligibility and GPS-based suggestions, then assign manually.</p></div><button type="button" className="small-btn muted" onClick={template}>Download orders CSV template</button></div>
  <div className="allocation-stats"><div><strong>{orders.length}</strong><span>Total imported</span></div><div><strong>{pending.length}</strong><span>Unassigned</span></div><div><strong>{assigned.length}</strong><span>Assigned</span></div></div>
  <div className="bulk-upload-area"><div className="bulk-upload-intro"><FileUp size={23}/><div><b>Upload orders CSV</b><small>No driver ID · Maximum 100 orders · Preview before importing</small></div></div><input id="unassigned-order-csv" className="bulk-hidden-file" type="file" accept=".csv,text/csv" onChange={e=>upload(e.target.files?.[0])}/><label htmlFor="unassigned-order-csv" className="bulk-file-select">Choose CSV file</label><span className="bulk-file-name">{fileName||'No file selected'}</span></div>
  {error&&<p className="bulk-upload-error" role="alert">{error}</p>}{info&&<p className="allocation-success" role="status"><CheckCircle2 size={16}/>{info}</p>}
  {preview&&<div className="bulk-preview"><div className="bulk-preview-summary"><strong>{preview.total} orders</strong><span className="bulk-count-good">{preview.valid} ready</span><span className="bulk-count-bad">{preview.invalid} need correction</span></div>{preview.invalid>0&&<div className="bulk-preview-errors">{preview.rows.filter(r=>!r.valid).map(r=><div key={r.row}><b>Row {r.row} · {r.order_reference}</b><span>{r.errors.join(' · ')}</span></div>)}</div>}<div className="bulk-preview-actions"><span>Preview does not assign drivers or send messages.</span><button type="button" className="btn primary" disabled={busy||preview.invalid>0} onClick={importBatch}>Import {preview.valid} unassigned orders</button></div></div>}
  <div className="allocation-list-heading"><h3>Imported orders</h3><button className="small-btn muted" onClick={refresh}>Refresh list</button></div>
  <div className="allocation-list">{orders.map(o=><article className="allocation-order" key={o.id}><div><b>{o.order_reference} · {o.title}</b><small>Pickup: {o.pickup_address} → Delivery: {o.delivery_address}</small><small>Due {fmtTime(o.due_at)} · {o.vehicle_type||'Any compatible vehicle'}</small></div><div className="allocation-order-action"><span className={'tag '+(o.status==='assigned'?'green':'orange')}>{o.status}</span>{o.status==='unassigned'&&<button type="button" className="small-btn" onClick={()=>selectOrder(o)}>Recommend & assign</button>}</div></article>)}{!orders.length&&<p className="allocation-empty">No orders imported yet. Upload the official CSV template to begin.</p>}</div>
  {chosen&&<div className="allocation-shade" onMouseDown={e=>{if(e.target===e.currentTarget)setChosen(null)}}><section className="allocation-dialog" role="dialog" aria-modal="true" aria-label="Assign order"><div className="allocation-dialog-top"><div><h3>Assign {chosen.order_reference}</h3><p>{chosen.title}</p></div><button className="small-btn muted" onClick={()=>setChosen(null)}>Close</button></div><p><b>Pickup:</b> {chosen.pickup_address}</p><p><b>Destination:</b> {chosen.delivery_address}</p><PickupMap order={chosen} drivers={recommendations}/><p className="allocation-map-note"><MapPin size={15}/> Distances are straight-line estimates, not live traffic ETAs. Stale GPS cannot be treated as a current location.</p><h4>Recommended eligible drivers</h4>{recommendations.length?recommendations.map((d,i)=><label key={d.driver_id} className={'allocation-driver '+(selectedDriver===d.driver_id?'selected':'')}><input type="radio" name="allocation-driver" checked={selectedDriver===d.driver_id} onChange={()=>setSelectedDriver(d.driver_id)}/><span><b>#{i+1} {d.name}</b><small>{d.vehicle} · {d.on_shift?'On shift':'Off shift'} · {d.distance_to_pickup_km==null?'Pickup distance unavailable':d.distance_to_pickup_km+' km straight line'}</small><small>{d.reasons.join(' · ')}</small></span></label>):<p className="allocation-empty"><AlertTriangle size={17}/> No eligible drivers found. Verify licence/approval and GPS before assigning.</p>}<div className="allocation-actions"><button className="btn secondary" onClick={()=>setChosen(null)}>Cancel</button><button className="btn primary" disabled={busy||!selectedDriver} onClick={assign}>{busy?'Assigning…':'Confirm selected driver'}</button></div></section></div>}
 </section>;
}
