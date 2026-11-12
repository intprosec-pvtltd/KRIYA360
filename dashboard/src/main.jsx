import {AttendanceReports,BulkDriverImport,LayerTiles,SOSLocation} from './nextFeatures.jsx';
import React,{useState,useEffect,useCallback} from 'react';import{createRoot}from'react-dom/client';import{MapContainer,TileLayer,Marker,Popup,Polyline,useMapEvents,useMap}from'react-leaflet';import L from 'leaflet';import 'leaflet/dist/leaflet.css';import './style.css';import{LayoutDashboard,UsersRound,Package,MapPinned,Wallet,ChartNoAxesCombined,BellRing,CalendarClock,LogOut,Plus,ShieldAlert,Navigation,Clock3,CheckCircle2,AlertTriangle,Truck,UserRound,Search,RefreshCcw,Receipt,Camera,Phone,Menu,Route,MapPin,ArrowRight,LockKeyhole,Send,Activity,ShieldCheck,ExternalLink,X,HeartPulse}from'lucide-react';
// Leaflet marker assets are served by CDN; map tiles require internet.
const markerIcon=new L.Icon({iconUrl:'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',shadowUrl:'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',iconSize:[25,41],iconAnchor:[12,41]});
const API='/api';async function request(path,opts={},token){const res=await fetch(API+path,{...opts,headers:{...(opts.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(token?{Authorization:'Bearer '+token}:{}),...(opts.headers||{})}});const body=await res.json().catch(()=>({}));if(!res.ok){const error=new Error(typeof body.detail==='string'?body.detail:`Request failed (${res.status})`);error.status=res.status;throw error;}return body;}
const money=v=>'₹'+Number(v||0).toLocaleString('en-IN');const dt=v=>v?new Date(v).toLocaleString('en-IN',{dateStyle:'medium',timeStyle:'short'}):'—';const capital=v=>(v||'').replaceAll('_',' ').replace(/\b\w/g,x=>x.toUpperCase());
const nav=[['Overview',LayoutDashboard],['Drivers',UsersRound],['Assignments',Package],['Live Tracking',MapPinned],['Expenses',Wallet],['Performance',ChartNoAxesCombined],['Attendance',CalendarClock],['Alerts & SOS',BellRing]];
function Tag({children,tone='blue'}){return <span className={'tag '+tone}>{children}</span>};function Empty({text='No records yet'}){return <div className="empty"><Package size={30}/><p>{text}</p></div>};
function Stats({icon:Icon,label,value,accent='blue',small}){return <div className="stat"><div className={'stat-icon '+accent}><Icon size={21}/></div><div><p>{label}</p><strong>{value}</strong>{small&&<small>{small}</small>}</div></div>}
function PickMapEvents({onPick}){useMapEvents({click:e=>onPick(e.latlng.lat,e.latlng.lng)});return null}
function MapFlyTo({lat,lng}){const map=useMap();useEffect(()=>{if(Number.isFinite(Number(lat))&&Number.isFinite(Number(lng)))map.flyTo([Number(lat),Number(lng)],Math.max(map.getZoom(),12))},[map,lat,lng]);return null}
function DestinationSearch({onChoose,token}){
 const[query,Q]=useState(''),[results,R]=useState([]),[busy,B]=useState(false),[error,E]=useState('');
 async function search(){if(query.trim().length<3)return;B(true);E('');R([]);try{const x=await request('/geocode/search?q='+encodeURIComponent(query.trim()),{},token);R(x.results||[]);if(!x.results?.length)E('No matching locations found')}catch(e){E(e.message)}finally{B(false)}}
 return <div className="destination-search"><div className="destination-search-form" role="search"><Search size={17}/><input type="search" value={query} onChange={e=>Q(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();e.stopPropagation();search()}}} placeholder="Search company, building, shop, landmark or address" aria-label="Search delivery destination"/><button type="button" className="small-btn" onClick={search} disabled={busy||query.trim().length<3}>{busy?'Searching…':'Search'}</button></div>{error&&<p role="alert" className="search-error">{error}</p>}{results.length>0&&<div className="destination-results" role="listbox">{results.map((x,i)=><button type="button" key={i} role="option" aria-selected="false" onClick={e=>{e.preventDefault();e.stopPropagation();onChoose(x);R([]);Q(x.label)}}><MapPin size={15}/><span>{x.label}</span></button>)}</div>}</div>
}
function DestinationPicker({lat,lng,onPick}){return <div className="destination-map"><div className="map-hint"><MapPin size={16}/> Click anywhere on the map to pin the exact delivery destination</div><MapContainer center={[Number(lat)||12.9716,Number(lng)||77.5946]} zoom={12} scrollWheelZoom style={{height:285,width:'100%'}}><LayerTiles/><PickMapEvents onPick={onPick}/><MapFlyTo lat={lat} lng={lng}/><Marker position={[Number(lat)||12.9716,Number(lng)||77.5946]} icon={markerIcon}><Popup>Selected delivery destination</Popup></Marker></MapContainer><div className="map-coordinates">Pinned destination: {Number(lat).toFixed(5)}, {Number(lng).toFixed(5)}</div></div>}
function AttendanceMap({rows,drivers}){const places=rows.filter(a=>a.lat!=null&&a.lng!=null);const recent=places.slice(0,80);return <div className="evidence-map"><MapContainer center={recent.length?[recent[0].lat,recent[0].lng]:[12.9716,77.5946]} zoom={12} scrollWheelZoom style={{height:380,width:'100%'}}><LayerTiles/>{recent.map(a=><Marker key={a.id} position={[a.lat,a.lng]} icon={markerIcon}><Popup><b>{drivers.find(d=>d.id===a.driver_id)?.name||'Driver'}</b><br/>Punch {a.kind.toUpperCase()}<br/>{dt(a.at)}<br/>{a.vehicle||'Vehicle not specified'}<br/>{a.lat.toFixed(5)}, {a.lng.toFixed(5)}</Popup></Marker>)}</MapContainer></div>}

// Pair the chronological attendance events per driver. An unmatched punch-out is
// retained as its own record rather than silently attributed to the wrong shift.
function attendanceShifts(events,drivers){
 const ordered=[...events].sort((a,b)=>new Date(a.at)-new Date(b.at));
 const open=new Map(),shifts=[];
 for(const e of ordered){
  if(e.kind==='in'){
   if(open.has(e.driver_id))shifts.push({start:open.get(e.driver_id),end:null});
   open.set(e.driver_id,e);
  }else if(e.kind==='out'){
   const start=open.get(e.driver_id)||null;
   shifts.push({start,end:e});
   open.delete(e.driver_id);
  }
 }
 for(const start of open.values())shifts.push({start,end:null});
 return shifts.map((pair,i)=>{
  const event=pair.start||pair.end;
  const driver=drivers.find(d=>d.id===event.driver_id);
  return {...pair,key:(pair.start?.id||'missing')+'-'+(pair.end?.id||'open')+'-'+i,
   driver:driver?.name||event.driver_id,vehicle:pair.start?.vehicle||pair.end?.vehicle||driver?.vehicle||'—',
   sortAt:pair.end?.at||pair.start?.at||''};
 }).sort((a,b)=>new Date(b.sortAt)-new Date(a.sortAt));
}
function validEvidence(e){return Boolean(e&&Number.isFinite(Number(e.lat))&&Number.isFinite(Number(e.lng))&&Math.abs(Number(e.lat))<=90&&Math.abs(Number(e.lng))<=180)}
function shortTime(iso){return iso?new Date(iso).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true}):'—'}
function EvidenceThumbnail({event,driver,onOpen}){
 if(!event)return <span className="no-evidence">—</span>;
 if(!validEvidence(event))return <span className="no-evidence">GPS unavailable</span>;
 const lat=Number(event.lat),lng=Number(event.lng);
 return <button type="button" className="gps-thumbnail" onClick={()=>onOpen({event,driver})} aria-label={`Open ${event.kind==='in'?'punch-in':'punch-out'} map evidence for ${driver}`} title="Enlarge location evidence inside KRIYA360">
   <span className="gps-mini-map"><MapContainer center={[lat,lng]} zoom={15} zoomControl={false} dragging={false} scrollWheelZoom={false} doubleClickZoom={false} touchZoom={false} boxZoom={false} keyboard={false} attributionControl={false} style={{width:'100%',height:'100%',pointerEvents:'none'}}><LayerTiles controls={false}/><Marker position={[lat,lng]} icon={markerIcon}/></MapContainer></span>
   <span className="gps-thumb-caption"><MapPin size={12}/> GPS snapshot <span className="gps-zoom-hint">Enlarge</span></span>
  </button>;
}
function AttendanceEvidenceDialog({selection,onClose}){
 const {event,driver}=selection,lat=Number(event.lat),lng=Number(event.lng);
 return <div className="gps-evidence-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}} role="presentation"><section className="gps-evidence-dialog" role="dialog" aria-modal="true" aria-label="Attendance GPS evidence">
  <header className="gps-evidence-header"><div><div className="eyebrow">KRIYA360 / ATTENDANCE EVIDENCE</div><h2>{driver} · Punch-{event.kind==='in'?'in':'out'}</h2></div><button className="icon-btn" type="button" onClick={onClose} title="Close"><X size={23}/></button></header>
  <div className="gps-evidence-details"><span><Clock3 size={15}/> {dt(event.at)}</span><span><Truck size={15}/> {event.vehicle||'Vehicle not recorded'}</span><span><MapPin size={15}/> {lat.toFixed(6)}, {lng.toFixed(6)}</span></div>
  <div className="gps-evidence-large"><MapContainer center={[lat,lng]} zoom={16} scrollWheelZoom={true} style={{width:'100%',height:'100%'}}><LayerTiles/><Marker position={[lat,lng]} icon={markerIcon}><Popup><b>{driver}</b><br/>Punch-{event.kind}<br/>{dt(event.at)}<br/>{lat.toFixed(6)}, {lng.toFixed(6)}</Popup></Marker></MapContainer></div>
  <p className="evidence-note">Recorded device GPS evidence. Map tiles require internet access. This is not independently verified location attestation.</p>
  <div className="gps-evidence-actions"><button type="button" className="btn secondary" onClick={onClose}>Close</button></div>
 </section></div>
}
function AttendanceRegister({events,drivers}){
 const [selection,setSelection]=useState(null),[search,setSearch]=useState('');
 const rows=attendanceShifts(events,drivers).filter(r=>r.driver.toLowerCase().includes(search.trim().toLowerCase()));
 return <section className="card attendance-register"><div className="card-heading"><div><h3><CalendarClock size={19}/> Driver attendance register</h3><p>Actual punch-in and punch-out GPS thumbnails displayed in this dashboard.</p></div><label className="attendance-filter"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Find driver" aria-label="Find driver"/></label></div>
 <div className="table-wrap"><table className="attendance-evidence-table"><thead><tr><th>Driver / Vehicle</th><th>Punch-in</th><th>Punch-in location</th><th>Punch-out</th><th>Punch-out location</th><th>Status</th></tr></thead><tbody>{rows.slice(0,40).map(row=><tr key={row.key}>
  <td><b>{row.driver}</b><small>{row.vehicle}</small></td>
  <td><b>{shortTime(row.start?.at)}</b><small>{row.start?new Date(row.start.at).toLocaleDateString('en-IN'):'—'}</small></td>
  <td><EvidenceThumbnail event={row.start} driver={row.driver} onOpen={setSelection}/></td>
  <td><b>{shortTime(row.end?.at)}</b><small>{row.end?new Date(row.end.at).toLocaleDateString('en-IN'):'—'}</small></td>
  <td><EvidenceThumbnail event={row.end} driver={row.driver} onOpen={setSelection}/></td>
  <td><Tag tone={row.start&&!row.end?'green':row.start&&row.end?'blue':'orange'}>{row.start&&!row.end?'On duty':row.start&&row.end?'Completed':'Unmatched punch-out'}</Tag></td>
 </tr>)}</tbody></table>{!rows.length&&<Empty text="No attendance events match your search"/>}</div>
 <p className="evidence-note">Showing the newest {Math.min(rows.length,40)} of {rows.length} shift records from the latest 300 attendance events. Map thumbnails and expanded evidence remain inside KRIYA360.</p>
 {selection&&<AttendanceEvidenceDialog selection={selection} onClose={()=>setSelection(null)}/>}
 </section>;
}
// Overview deliberately shows ONE marker per driver and only their CURRENT delivery.
// Historical completed/cancelled tasks are not represented as driver jobs here.
function currentDriverTask(tasks,id){
 return tasks.find(t=>t.driver_id===id&&t.status==='in_progress')||null;
}
function overviewGpsState(driver){
 if(driver.lat==null||driver.lng==null)return {label:'No GPS',color:'#64748b',stale:true};
 const age=Date.now()-new Date(driver.last_gps).getTime();
 if(!Number.isFinite(age)||age<0)return {label:'GPS timestamp unavailable',color:'#64748b',stale:true};
 if(age>120000)return {label:'GPS offline · last '+dt(driver.last_gps),color:'#64748b',stale:true};
 if(age>30000)return {label:'GPS stale · '+dt(driver.last_gps),color:'#64748b',stale:true};
 return {label:'GPS '+Math.max(0,Math.floor(age/1000))+'s ago',color:'#16a34a',stale:false};
}
// These images are fetched with the manager's bearer token and never exposed in a public URL.
// Only manager-approved face photographs are eligible; errors fall back to initials.
function useApprovedDriverPhotos(drivers,token){
 const [photos,setPhotos]=useState({});
 const key=drivers.map(d=>`${d.id}:${d.face_review_status}:${d.face_url||''}`).join('|');
 useEffect(()=>{
  if(!token){setPhotos({});return;}
  let cancelled=false;const urls=[];
  const sources=drivers.filter(d=>d.face_review_status==='approved'&&d.face_url&&d.face_url.startsWith('/api/files/'));
  Promise.all(sources.map(async d=>{
   try{
    const response=await fetch(d.face_url,{headers:{Authorization:'Bearer '+token}});
    if(!response.ok)throw Error('Photo unavailable');
    const blob=await response.blob();if(!blob.type.startsWith('image/'))throw Error('Not an image');
    const url=URL.createObjectURL(blob);if(cancelled){URL.revokeObjectURL(url);return null;}urls.push(url);return [d.id,url];
   }catch{return null;}
  })).then(result=>{if(!cancelled)setPhotos(Object.fromEntries(result.filter(Boolean)))});
  return()=>{cancelled=true;urls.forEach(url=>URL.revokeObjectURL(url));};
 },[key,token]);
 return photos;
}
function driverPhotoMarker(d,photo,stale){
 const color=stale?'#64748b':d.on_shift?'#16a34a':'#f97316';
 const initials=String(d.name||'D').trim().split(/\s+/).slice(0,2).map(x=>x[0]||'').join('').replace(/[^a-zA-Z0-9]/g,'').toUpperCase()||'D';
 const inside=photo?`<img src="${photo}" alt="" style="width:100%;height:100%;object-fit:cover;border-radius:50%"/>`:`<span style="font-size:12px;font-weight:800;color:#163451">${initials}</span>`;
 return L.divIcon({html:`<div style="height:40px;width:40px;border:4px solid ${color};background:#f2f6fa;border-radius:50%;display:flex;align-items:center;justify-content:center;overflow:hidden;box-shadow:0 2px 9px #0005">${inside}</div>`,className:'fleet-driver-photo-marker',iconSize:[44,44],iconAnchor:[22,22]});
}
function OverviewFleetViewport({drivers,selectedId,routeCoords=[],destination=null}){
 const map=useMap();
 const ids=drivers.map(d=>d.id).join('|');
 useEffect(()=>{
  const chosen=drivers.find(d=>d.id===selectedId);
  const coords=chosen?[[Number(chosen.lat),Number(chosen.lng)],...(destination?[[Number(destination.lat),Number(destination.lng)]]:[]),...(routeCoords.length>1?[routeCoords[0],routeCoords[routeCoords.length-1]]:[])]:drivers.map(d=>[Number(d.lat),Number(d.lng)]);
  const valid=coords.filter(c=>c.every(Number.isFinite));
  if(valid.length>1)map.fitBounds(L.latLngBounds(valid),{padding:[45,45],maxZoom:14});
  else if(valid.length===1)map.setView(valid[0],14);
  const id=setTimeout(()=>map.invalidateSize(),80);
  return()=>clearTimeout(id);
 },[map,selectedId,ids,Boolean(destination),routeCoords.length]);
 return null;
}
function OverviewFleetMap({drivers=[],tasks=[],height=390,onViewTracking,token}){
 const [filter,F]=useState('all'),[selectedId,S]=useState(null),[showDestination,SD]=useState(false),[showRoute,SR]=useState(false),[routeData,RD]=useState(null),[routeError,RE]=useState('');
 const photos=useApprovedDriverPhotos(drivers,token);
 const delivering=drivers.filter(d=>!!currentDriverTask(tasks,d.id));
 const visible=drivers.filter(d=>filter==='all'||(filter==='onshift'&&d.on_shift)||(filter==='delivering'&&!!currentDriverTask(tasks,d.id)));
 const located=visible.filter(d=>d.lat!=null&&d.lng!=null&&Number.isFinite(Number(d.lat))&&Number.isFinite(Number(d.lng)));
 const selected=visible.find(d=>d.id===selectedId)||null;
 const task=selected?currentDriverTask(tasks,selected.id):null;
 const selectedDestination=showDestination&&task&&Number.isFinite(Number(task.lat))&&Number.isFinite(Number(task.lng))?task:null;
 const control={padding:'7px 9px',border:'1px solid #d7e2ef',background:'#fff',borderRadius:8,color:'#16304e',fontSize:12,maxWidth:'100%'};
 const selectDriver=id=>{S(id||null);SD(false);SR(false);RD(null);RE('');};
 useEffect(()=>{
  if(!selectedId||!task?.id||!showRoute){RD(null);return;}
  let live=true;
  request('/tasks/'+encodeURIComponent(task.id)+'/route',{},token).then(r=>{if(live){RD(r);RE('')}}).catch(e=>{if(live){RD(null);RE('Route unavailable: '+e.message)}});
  return()=>{live=false};
 },[selectedId,task?.id,showRoute,token]);
 const routeCoords=(showRoute?routeData?.coordinates||[]:[]).map(c=>[Number(c[1]),Number(c[0])]).filter(c=>c.every(Number.isFinite));
 return <div className="overview-fleet" style={{display:'grid',gap:10}}>
  <div style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center',justifyContent:'space-between'}}>
   <label style={{fontSize:12,color:'#526781'}}>Show <select aria-label="Filter overview drivers" value={filter} onChange={e=>{F(e.target.value);selectDriver(null)}} style={control}><option value="all">All drivers ({drivers.length})</option><option value="onshift">On shift ({drivers.filter(d=>d.on_shift).length})</option><option value="delivering">On delivery ({delivering.length})</option></select></label>
   <label style={{fontSize:12,color:'#526781'}}>Driver <select aria-label="Select driver to inspect current task" value={selected?.id||''} onChange={e=>selectDriver(e.target.value)} style={control}><option value="">All visible drivers</option>{visible.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
   <button type="button" className="small-btn" onClick={()=>selectDriver(null)} disabled={!selectedId}>Show all drivers</button>
  </div>
  <div style={{height,position:'relative',borderRadius:12,overflow:'hidden'}}>
   <MapContainer center={[12.9716,77.5946]} zoom={11} scrollWheelZoom style={{width:'100%',height:'100%'}}>
    <LayerTiles/>
    <OverviewFleetViewport drivers={located} selectedId={selected?.id||null} destination={selectedDestination} routeCoords={routeCoords}/>
    {located.map(d=>{const state=overviewGpsState(d);const current=currentDriverTask(tasks,d.id);return <Marker key={d.id} position={[Number(d.lat),Number(d.lng)]} icon={driverPhotoMarker(d,photos[d.id],state.stale)} eventHandlers={{click:()=>selectDriver(d.id)}}><Popup><strong>{d.name}</strong><div>{d.vehicle||'Vehicle not assigned'}</div><div>{state.label}</div><div>{current?'Current delivery: '+current.title:'No current delivery'}</div><button type="button" style={{...control,marginTop:7}} onClick={()=>selectDriver(d.id)}>Select driver</button></Popup></Marker>})}
    {selectedDestination&&<Marker position={[Number(selectedDestination.lat),Number(selectedDestination.lng)]} icon={endMarker}><Popup><b>Current delivery destination</b><div>{selectedDestination.title}</div><div>{selectedDestination.address}</div></Popup></Marker>}
    {selected&&routeCoords.length>1&&<Polyline positions={routeCoords} pathOptions={{color:'#ef741c',weight:5,opacity:.9}}/>}
   </MapContainer>
  </div>
  <div style={{fontSize:12,color:'#526781'}}>Photo borders: green = on shift, orange = off shift, grey = stale GPS. Actual uploaded face photos appear only after manager approval.</div>
  {selected?<div style={{background:'#f2f6fb',borderRadius:10,padding:12,fontSize:13}}>
   <b>{selected.name}</b> · {selected.vehicle||'No vehicle'} <span style={{color:'#64748b'}}>· {overviewGpsState(selected).label}</span>
   <div style={{margin:'7px 0'}}>{task?<><b>Current delivery: {task.title}</b> · {task.address||'Destination unavailable'} · Due {dt(task.due_at)}</>:'No delivery currently in progress.'}</div>
   <div style={{display:'flex',gap:8,flexWrap:'wrap'}}><button className="small-btn" type="button" disabled={!task} onClick={()=>SD(x=>!x)}>{showDestination?'Hide destination':'Destination'}</button><button className="small-btn" type="button" disabled={!task} onClick={()=>SR(x=>!x)}>{showRoute?'Hide route':'Show route'}</button><button className="small-btn" type="button" onClick={()=>onViewTracking?.()}>Detailed tracking</button></div>
   {showRoute&&routeData&&<div style={{marginTop:7}}>Planned route: {routeData.distance_km} km · {routeData.duration_min} min · {routeData.source||'Road routing'}{routeData.traffic_aware?' · Traffic-aware':' · No live traffic'}</div>}
   {routeError&&<div role="alert" style={{marginTop:7,color:'#b91c1c'}}>{routeError}</div>}
  </div>:<div style={{fontSize:12,color:'#64748b'}}>{located.length} of {visible.length} drivers have recorded GPS locations. No delivery pins or routes shown until you select a driver. Locations refresh on dashboard polling; stale GPS is not live.</div>}
 </div>;
}

// Fleet map: locations are historical device-reported GPS points, not guarantees of real-time position.
const truckMarker=new L.DivIcon({html:'<div class="fleet-truck-pin">🚚</div>',className:'fleet-icon',iconSize:[38,42],iconAnchor:[19,38]});
const startMarker=new L.DivIcon({html:'<div class="fleet-start-pin">S</div>',className:'fleet-icon',iconSize:[26,26],iconAnchor:[13,13]});
const endMarker=new L.DivIcon({html:'<div class="fleet-end-pin">D</div>',className:'fleet-icon',iconSize:[28,28],iconAnchor:[14,14]});
function FleetMapViewport({drivers,selected,routeCoords,start,destination}){
 const map=useMap();
 const key=selected?`${selected.id}:${routeCoords.length}:${start?.lat}:${destination?.lat}`:drivers.map(d=>`${d.id}:${d.lat}:${d.lng}`).join('|');
 useEffect(()=>{
   const locations=selected?[
     ...(selected.lat!=null&&selected.lng!=null?[[selected.lat,selected.lng]]:[]),
     ...(start?[[start.lat,start.lng]]:[]),
     ...(destination?[[destination.lat,destination.lng]]:[]),
     ...(routeCoords.length>1?[routeCoords[0],routeCoords[routeCoords.length-1]]:[])
   ]:drivers.filter(d=>Number.isFinite(Number(d.lat))&&Number.isFinite(Number(d.lng))&&d.lat!=null&&d.lng!=null).map(d=>[d.lat,d.lng]);
   if(locations.length>1)map.fitBounds(L.latLngBounds(locations),{padding:[42,42],maxZoom:14});
   else if(locations.length===1)map.setView(locations[0],13);
   setTimeout(()=>map.invalidateSize(),80);
 },[map,key]);
 return null;
}
function gpsFreshness(value){if(!value)return {label:'Never reported',tone:'gray'};const age=Date.now()-new Date(value).getTime();if(!Number.isFinite(age)||age<0)return {label:'Recorded GPS',tone:'gray'};if(age<90000)return {label:'Updated recently',tone:'green'};if(age<600000)return {label:'Updated '+Math.max(1,Math.floor(age/60000))+' min ago',tone:'orange'};return {label:'Last reported '+dt(value),tone:'gray'};}
function LiveTracking({drivers,tasks,token,onError}){
 const photos=useApprovedDriverPhotos(drivers,token);
 const[selectedId,SS]=useState(null),[route,SR]=useState(null),[history,SH]=useState([]),[routeError,SE]=useState('');
 const selected=drivers.find(d=>d.id===selectedId)||null;
 const task=selected?tasks.find(t=>t.driver_id===selected.id&&t.status==='in_progress')||null:null;
 useEffect(()=>{
  if(!selected){SR(null);SH([]);SE('');return;}
  let active=true;SR(null);SH([]);SE('');
  const updateHistory=()=>request('/gps/'+encodeURIComponent(selected.id),{},token).then(rows=>{if(active)SH(rows||[])}).catch(e=>{if(active)SE('GPS history unavailable: '+e.message)});
  updateHistory();
  const timer=setInterval(updateHistory,8000);
  if(task)request('/tasks/'+encodeURIComponent(task.id)+'/route',{},token).then(data=>{if(active)SR(data)}).catch(e=>{if(active)SE('Road route unavailable: '+e.message)});
  return()=>{active=false;clearInterval(timer)};
 },[selectedId,task?.id,token]);
 const tripPoints=task?history.filter(p=>p.task_id===task.id).sort((a,b)=>new Date(a.at)-new Date(b.at)):[];
 const start=tripPoints.length?tripPoints[0]:null;
 const destination=task?{lat:task.lat,lng:task.lng}:null;
 const routeCoords=(route?.coordinates||[]).map(c=>[Number(c[1]),Number(c[0])]).filter(pair=>pair.every(Number.isFinite));
 const allLocated=drivers.filter(d=>d.lat!=null&&d.lng!=null&&Number.isFinite(Number(d.lat))&&Number.isFinite(Number(d.lng)));
 const noGps=drivers.length-allLocated.length;
 return <div className="live-tracking-workspace">
  <div className="fleet-headline"><div><h3>Live fleet operations</h3><p>Latest device-reported locations, vehicle details, and active delivery routes in one view</p></div><div className="fleet-counters"><Tag tone="blue">{allLocated.length} located</Tag><Tag tone="gray">{noGps} awaiting GPS</Tag></div></div>
  <div className="fleet-layout">
   <section className="card fleet-map-card"><div className="card-heading"><div><h3>{selected?`${selected.name} · Journey map`:'All drivers · Fleet map'}</h3><p>{selected?'Start, current vehicle position and delivery destination':'Select any driver marker or name to inspect their delivery'}</p></div>{selected&&<button type="button" className="small-btn muted" onClick={()=>SS(null)}>Show all drivers</button>}</div>
    <div className="fleet-map-stage"><MapContainer center={[12.9716,77.5946]} zoom={11} style={{height:'100%',width:'100%'}} scrollWheelZoom>
      <LayerTiles/>
      <FleetMapViewport drivers={allLocated} selected={selected} start={start} destination={destination} routeCoords={routeCoords}/>
      {allLocated.filter(d=>!selected||d.id===selected.id).map(d=><Marker key={d.id} position={[d.lat,d.lng]} icon={driverPhotoMarker(d,photos[d.id],gpsFreshness(d.last_gps).tone!=='green')} eventHandlers={{click:()=>SS(d.id)}}><Popup><strong>{d.name}</strong><div>{d.vehicle||'Vehicle not assigned'} · {d.vehicle_plate||'No plate recorded'}</div><div>{d.on_shift?'On shift':'Off shift'} · {gpsFreshness(d.last_gps).label}</div><div>{(tasks.find(t=>t.driver_id===d.id&&t.status==='in_progress')||{}).title||'No active delivery'}</div><button type="button" className="small-btn" onClick={()=>SS(d.id)}>Show journey</button></Popup></Marker>)}
      {selected&&start&&<Marker position={[start.lat,start.lng]} icon={startMarker}><Popup>Recorded start of delivery GPS history<br/>{dt(start.at)}</Popup></Marker>}
      {selected&&destination&&<Marker position={[destination.lat,destination.lng]} icon={endMarker}><Popup><b>Delivery destination</b><br/>{task.title}<br/>{task.address}</Popup></Marker>}
      {selected&&routeCoords.length>1&&<Polyline positions={routeCoords} pathOptions={{color:'#ff7417',weight:6,opacity:.92}}/>}
      {selected&&tripPoints.length>1&&<Polyline positions={tripPoints.map(p=>[p.lat,p.lng])} pathOptions={{color:'#1675d1',weight:3,opacity:.8,dashArray:'5 7'}}/>}
    </MapContainer></div>
    <div className="fleet-map-legend"><span><i className="legend-dot blue"/> Vehicle GPS</span><span><i className="legend-dot orange"/> Road route (current → destination)</span><span><i className="legend-dot green"/> Recorded journey start</span></div>
   </section>
   <section className="card fleet-side-panel"><div className="card-heading"><div><h3>Drivers on map</h3><p>Choose a driver to view detailed operations</p></div><Tag>{drivers.length} drivers</Tag></div>
    <div className="fleet-driver-list">{drivers.map(d=>{const active=tasks.find(t=>t.driver_id===d.id&&t.status==='in_progress');const freshness=gpsFreshness(d.last_gps);return <button type="button" key={d.id} className={'fleet-driver-option '+(selectedId===d.id?'selected':'')} onClick={()=>SS(d.id)}><span className="driver-initial">{photos[d.id]?<img src={photos[d.id]} alt="" style={{width:34,height:34,borderRadius:'50%',objectFit:'cover'}}/>:<Truck size={18}/>}</span><span className="fleet-driver-copy"><b>{d.name}</b><small>{d.vehicle||'No vehicle'}{d.vehicle_plate?' · '+d.vehicle_plate:''}</small><small>{active?'Delivering: '+active.title:freshness.label}</small></span><Tag tone={d.lat==null?'gray':freshness.tone}>{d.lat==null?'No GPS':d.on_shift?'On duty':'Off shift'}</Tag></button>})}{!drivers.length&&<Empty text="No drivers registered"/>}</div>
    {selected&&<div className="fleet-selected-details"><h3>Driver & delivery details</h3><div className="fleet-detail-grid"><div><small>Driver</small><b>{selected.name}</b></div><div><small>Phone</small><b>{selected.phone||'—'}</b></div><div><small>Vehicle</small><b>{selected.vehicle||'Not assigned'}</b></div><div><small>Plate</small><b>{selected.vehicle_plate||'—'}</b></div><div><small>Shift</small><b>{selected.on_shift?'On duty':'Off shift'}</b></div><div><small>GPS status</small><b>{gpsFreshness(selected.last_gps).label}</b></div></div>
       <div className="fleet-task-summary"><h4>{task?'Current / next delivery':'Delivery status'}</h4>{task?<><b>{task.title}</b><p><MapPin size={14}/>{task.address}</p><p>Due: {dt(task.due_at)} · {capital(task.status)}</p><p>Customer: {task.customer||'Not provided'}</p>{route&&<p>Road route: {route.distance_km} km · {route.duration_min} min estimated</p>}</>:<p>No current or upcoming assignment.</p>}{start?<p>Recorded journey start: {dt(start.at)}</p>:<p>Journey start GPS not recorded for this task.</p>}{selected.lat!=null&&<p>Vehicle GPS: {Number(selected.lat).toFixed(5)}, {Number(selected.lng).toFixed(5)}</p>}{routeError&&<p className="fleet-route-warning">{routeError}</p>}</div>
      </div>}
   </section>
  </div>
 </div>;
}

function downloadPerformanceCsv(records,driver=null,attendance=[]){
 const chosen=driver?records.filter(x=>x.driver_id===driver):records;
 const columns=['Driver','Assigned','Completed','In progress / remaining','On time','Completion %','Punctuality %','Late deliveries','Average late delivery delay (min)','Attendance punches','Late punch-ins','Recorded missed punch-ins','Attendance on time %','Approved expenses (INR)'];
 const values=chosen.map(x=>[x.name,x.total||0,x.completed||0,Math.max(0,(x.total||0)-(x.completed||0)),x.on_time||0,(x.total||0)?((100*(x.completed||0)/(x.total||1)).toFixed(1)):'0',x.on_time_rate??'N/A',x.late_deliveries??'N/A',x.avg_delay_min??'N/A',attendance.find(a=>a.driver_id===x.driver_id)?.punch_ins??'N/A',attendance.find(a=>a.driver_id===x.driver_id)?.late_punch_ins??'N/A',attendance.find(a=>a.driver_id===x.driver_id)?.missed_punch_ins??'N/A',attendance.find(a=>a.driver_id===x.driver_id)?.on_time_percent??'N/A',x.approved_expenses||0]);
 const csv=[columns,...values].map(row=>row.map(value=>'"'+String(value??'').replaceAll('"','""')+'"').join(',')).join('\r\n');
 const blob=new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`KRIYA360_${driver?'driver':'fleet'}_performance_${new Date().toISOString().slice(0,10)}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function PerformanceWorkspace({records,tasks,token}){
 const [selected,S]=useState('all');const [attendanceSummary,AS]=useState([]);useEffect(()=>{let live=true;request('/reports/attendance',{},token).then(r=>{if(live)AS(r.drivers||[])}).catch(()=>{});return()=>{live=false}},[token]);
 const chosen=selected==='all'?records:records.filter(r=>r.driver_id===selected);
 const total=chosen.reduce((v,r)=>v+Number(r.total||0),0),completed=chosen.reduce((v,r)=>v+Number(r.completed||0),0),onTime=chosen.reduce((v,r)=>v+Number(r.on_time||0),0),expense=chosen.reduce((v,r)=>v+Number(r.approved_expenses||0),0);
 const colors=['#1b77d2','#ff851f','#1ca56a','#b4c4d8'];const slices=[completed,total-completed].map(v=>Math.max(0,v));
 const fraction=total?completed/total:0;const completedDegrees=fraction*360;const completion=total?Math.round(100*fraction):0;const punctuality=completed?Math.round(onTime/completed*100):null;
 const chartMax=Math.max(1,...chosen.map(r=>r.total||0));
 return <div className="performance-workspace">
  <section className="perf-toolbar"><div><h3>Driver performance analytics</h3><p>Compare assigned, completed and on-time deliveries. Reports reflect recorded tasks, not GPS-independent proof.</p></div><div className="perf-actions"><select aria-label="Select driver" value={selected} onChange={e=>S(e.target.value)}><option value="all">All drivers</option>{records.map(r=><option key={r.driver_id} value={r.driver_id}>{r.name}</option>)}</select><button type="button" className="small-btn" onClick={()=>downloadPerformanceCsv(records,selected==='all'?null:selected,attendanceSummary)}><Receipt size={15}/> Download {selected==='all'?'fleet':'driver'} CSV</button><button type="button" className="small-btn muted" onClick={()=>window.print()}>Print / Save PDF</button></div></section>
  <div className="perf-kpis"><div><span>Assigned deliveries</span><strong>{total}</strong><small>Across selected drivers</small></div><div><span>Completed deliveries</span><strong>{completed}</strong><small>{completion}% completion rate</small></div><div><span>On-time completion</span><strong>{punctuality==null?'—':punctuality+'%'}</strong><small>{onTime} recorded on-time</small></div><div><span>Approved expenses</span><strong>{money(expense)}</strong><small>Verified expense totals</small></div></div>
  <div className="perf-charts"><section className="card perf-chart-card"><div className="card-heading"><div><h3><ChartNoAxesCombined size={19}/> Driver delivery comparison</h3><p>Assigned, completed and on-time deliveries per driver</p></div></div><div className="perf-bars">{chosen.length?chosen.map(r=><div className="perf-bar-line" key={r.driver_id}><div className="perf-bar-title"><b>{r.name}</b><small>{r.completed||0} / {r.total||0} completed</small></div><div className="perf-bar-stack">{[['Assigned',r.total||0,'#a9c9ec'],['Completed',r.completed||0,'#1b77d2'],['On time',r.on_time||0,'#1aa46d']].map(([label,value,color])=><div key={label} className="perf-bar-track" title={`${label}: ${value}`}><div style={{width:`${100*Number(value)/chartMax}%`,background:color}}/><small>{value}</small></div>)}</div></div>):<Empty text="No driver performance recorded"/>}</div><div className="perf-legend"><span><i style={{background:'#a9c9ec'}}/> Assigned</span><span><i style={{background:'#1b77d2'}}/> Completed</span><span><i style={{background:'#1aa46d'}}/> On time</span></div></section>
  <section className="card perf-chart-card"><div className="card-heading"><div><h3><Activity size={19}/> Delivery completion</h3><p>Share of assigned deliveries completed</p></div></div><div className="perf-donut-wrap"><div role="img" aria-label={`${completed} completed out of ${total} assigned`} className="perf-donut" style={{background:total?`conic-gradient(#1aa46d ${completedDegrees}deg, #e8edf5 ${completedDegrees}deg 360deg)`:'#e8edf5'}}><div><strong>{completion}%</strong><small>completed</small></div></div><div className="perf-donut-key"><p><i style={{background:'#1aa46d'}}/> Completed <b>{completed}</b></p><p><i style={{background:'#e8edf5'}}/> Remaining <b>{Math.max(0,total-completed)}</b></p><p><i style={{background:'#ff851f'}}/> On time <b>{onTime}</b></p></div></div></section></div>
  <section className="card"><div className="card-heading"><div><h3>Detailed driver scorecard</h3><p>Choose one driver above to focus their analytics or download an individual report below</p></div></div><div className="table-wrap"><table className="perf-table"><thead><tr><th>Driver</th><th>Assigned</th><th>Completed</th><th>On time</th><th>Completion</th><th>Punctuality</th><th>Approved costs</th><th>Report</th></tr></thead><tbody>{chosen.map(d=><tr key={d.driver_id}><td><b>{d.name}</b></td><td>{d.total}</td><td>{d.completed}</td><td>{d.on_time}</td><td>{d.total?Math.round(100*d.completed/d.total)+'%':'—'}</td><td>{d.on_time_rate==null?'—':<div className="progressrow"><span className="bar"><i style={{width:d.on_time_rate+'%'}}/></span>{d.on_time_rate}%</div>}</td><td>{money(d.approved_expenses)}</td><td><button type="button" className="small-btn" onClick={()=>downloadPerformanceCsv(records,d.driver_id,attendanceSummary)}>CSV</button></td></tr>)}{!chosen.length&&<tr><td colSpan="8">No driver records</td></tr>}</tbody></table></div></section>
  <p className="perf-disclaimer">Punctuality is measured against the assigned deadline. Pending or missing completion times are not counted as on-time. CSV data is exported from the currently loaded report.</p>
 </div>;
}
function AttendancePerformance({token,records}){const [report,R]=useState(null);useEffect(()=>{let active=true;request('/reports/attendance',{},token).then(x=>{if(active)R(x)}).catch(()=>{});return()=>{active=false}},[token]);return <section className="card next-attendance-perf"><div className="card-heading"><div><h3>Driver attendance & late delivery performance</h3><p>Daily punch-in history compared with scheduled start times; missing shifts require a roster.</p></div></div><div className="table-wrap"><table><thead><tr><th>Driver</th><th>Recorded punches</th><th>Late punch-ins</th><th>Recorded missed punches</th><th>On-time attendance</th><th>Late deliveries</th><th>Average delivery delay</th></tr></thead><tbody>{(report?.drivers||[]).map(a=>{const d=records.find(x=>x.driver_id===a.driver_id)||{};return <tr key={a.driver_id}><td><b>{a.name}</b></td><td>{a.punch_ins}</td><td>{a.late_punch_ins}</td><td>{a.missed_punch_ins??0}</td><td>{a.on_time_percent==null?'—':a.on_time_percent+'%'}</td><td>{d.late_deliveries??'—'}</td><td>{d.avg_delay_min==null?'—':d.avg_delay_min+' min'}</td></tr>})}</tbody></table></div><p className="next-disclaimer">Missed punch-in counts reflect only recorded KRIYA360 system alerts; full absence counts require an approved duty calendar.</p></section>}
function AlertWorkspace({alerts,onAction,onMap}){
 const [filter,F]=useState('open'),[severity,V]=useState('all');
 const open=alerts.filter(a=>a.status==='open').length,critical=alerts.filter(a=>a.severity==='critical'&&a.status!=='resolved').length,ack=alerts.filter(a=>a.status==='acknowledged').length,done=alerts.filter(a=>a.status==='resolved').length;
 const shown=alerts.filter(a=>(filter==='all'||a.status===filter)&&(severity==='all'||a.severity===severity));
 return <div className="alerts-workspace"><div className="alert-kpis"><div><span className="alert-count-icon danger"><ShieldAlert/></span><div><small>Critical unresolved</small><strong>{critical}</strong></div></div><div><span className="alert-count-icon amber"><AlertTriangle/></span><div><small>Open alerts</small><strong>{open}</strong></div></div><div><span className="alert-count-icon blue"><BellRing/></span><div><small>Acknowledged</small><strong>{ack}</strong></div></div><div><span className="alert-count-icon green"><CheckCircle2/></span><div><small>Resolved</small><strong>{done}</strong></div></div></div>
  <section className="card"><div className="card-heading alert-heading"><div><h3>Operations alert center</h3><p>Review emergency SOS, delivery deadlines, route deviations and attendance exceptions</p></div><div className="alert-controls"><select aria-label="Alert status" value={filter} onChange={e=>F(e.target.value)}><option value="open">Open</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option><option value="all">All statuses</option></select><select aria-label="Alert severity" value={severity} onChange={e=>V(e.target.value)}><option value="all">All severities</option><option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Information</option></select></div></div>
  <div className="alert-modern-list">{shown.map(a=><div className={'alert-modern-row '+(a.severity==='critical'?'is-critical':'')} key={a.id}><div className={'alert-count-icon '+(a.severity==='critical'?'danger':'amber')}>{a.severity==='critical'?<HeartPulse size={21}/>:<AlertTriangle size={21}/>}</div><div className="alert-modern-body"><div className="alert-modern-title"><strong>{capital(a.kind)}</strong><Tag tone={a.severity==='critical'?'red':'orange'}>{capital(a.severity)}</Tag><Tag tone={a.status==='open'?'red':a.status==='resolved'?'green':'blue'}>{capital(a.status)}</Tag></div><p>{a.message}</p><small><UserRound size={13}/> {a.driver_name||'System'} <Clock3 size={13}/> {dt(a.at)}</small>{a.lat!=null&&<div className="alert-location"><MapPin size={14}/> Location: {Number(a.lat).toFixed(5)}, {Number(a.lng).toFixed(5)} <button className="small-btn" type="button" onClick={()=>onMap(a)}>View SOS / alert map</button></div>}</div><div className="alert-actions">{a.status==='open'&&<button type="button" className="small-btn" onClick={()=>onAction('/alerts/'+a.id,'PATCH',{status:'acknowledged'})}>Acknowledge</button>}{a.status!=='resolved'&&<button type="button" className="small-btn muted" onClick={()=>onAction('/alerts/'+a.id,'PATCH',{status:'resolved'})}>Resolve</button>}</div></div>)}{!shown.length&&<Empty text="No alerts match these filters"/>}</div></section>
 </div>;
}
function SOSCommandAlert({token,onNavigate,onMap,onRefresh,mapOpen=false}){
 const [alerts,setAlerts]=useState([]);
 const [opened,setOpened]=useState(false);
 const [soundReady,setSoundReady]=useState(false);
 const [soundWanted,setSoundWanted]=useState(()=>localStorage.getItem('kriya-sos-audio')==='enabled');
 const [audioError,setAudioError]=useState('');
 const audioRef=React.useRef(null),knownAll=React.useRef(null),playingRef=React.useRef(false);
 const openSOS=alerts.filter(a=>String(a.kind).toLowerCase()==='sos'&&a.status==='open');
 const otherOpen=alerts.filter(a=>String(a.kind).toLowerCase()!=='sos'&&a.status==='open');
 const activeSOS=openSOS[0]||null;
 const audio=()=>{
  if(!audioRef.current){
   const a=new Audio('/sos-alarm.mp3');a.loop=true;a.preload='auto';a.volume=.8;
   audioRef.current=a;
  }
  return audioRef.current;
 };
 useEffect(()=>{
  if(!token)return;
  let alive=true;
  const check=async()=>{
   try{
    const rows=await request('/alerts',{},token);
    if(!alive)return;
    const list=Array.isArray(rows)?rows:[];
    if(knownAll.current!==null&&'Notification' in window&&Notification.permission==='granted'){
     list.filter(a=>a.status==='open'&&!knownAll.current.has(String(a.id))).forEach(a=>{
      try{
       const n=new Notification(String(a.kind).toLowerCase()==='sos'?'KRIYA360 EMERGENCY SOS':'KRIYA360 '+capital(a.kind),{
        body:(a.driver_name?a.driver_name+' — ':'')+(a.message||'New alert'),tag:'kriya-alert-'+a.id,silent:true,requireInteraction:String(a.kind).toLowerCase()==='sos'
       });
       n.onclick=()=>{window.focus();setOpened(true);n.close()};
      }catch(_){/* Notification API is optional. */}
     });
    }
    knownAll.current=new Set(list.map(a=>String(a.id)));
    setAlerts(list);
   }catch(_){/* Transient backend errors do not clear active SOS messages. */}
  };
  check();const id=setInterval(check,3000);
  return()=>{alive=false;clearInterval(id);knownAll.current=null};
 },[token]);
 // Chrome can prohibit autoplay until a user interaction. We activate audio from
 // the actual pointer/key event, never an effect that runs later.
 const enableAudio=()=>{
  const el=audio();el.muted=false;el.volume=.8;
  try{
   const attempt=el.play();
   Promise.resolve(attempt).then(()=>{
    localStorage.setItem('kriya-sos-audio','enabled');setSoundWanted(true);setSoundReady(true);setAudioError('');
    if(!openSOS.length){el.pause();el.currentTime=0;playingRef.current=false}
    else playingRef.current=true;
   }).catch(()=>{
    setSoundReady(false);setAudioError('Chrome blocked autoplay. Click Enable alarm sound to activate SOS audio.');
   });
   if('Notification' in window&&Notification.permission==='default')Notification.requestPermission().catch(()=>{});
  }catch(e){setAudioError(e.message)}
 };
 // Once enabled, any first click/keyboard action in a new tab session can unlock
 // playback. A visible activation button remains available if Chrome blocks it.
 useEffect(()=>{
  if(soundReady||!token)return;
  const wake=()=>enableAudio();
  window.addEventListener('pointerdown',wake,{once:true});
  window.addEventListener('keydown',wake,{once:true});
  return()=>{window.removeEventListener('pointerdown',wake);window.removeEventListener('keydown',wake)};
 },[soundReady,token,openSOS.length]);
 useEffect(()=>{
  const el=audio();
  if(soundReady&&openSOS.length){
   if(el.paused){el.play().then(()=>{playingRef.current=true}).catch(()=>{
    playingRef.current=false;setSoundReady(false);
    setAudioError('Audio requires one click in Chrome. Select Enable alarm sound.');
   })}
  }else{
   el.pause();el.currentTime=0;playingRef.current=false;
  }
 },[soundReady,openSOS.length]);
 useEffect(()=>()=>{if(audioRef.current){audioRef.current.pause();audioRef.current.src=''}},[]);
 async function acknowledge(a){
  try{
   await request('/alerts/'+a.id,{method:'PATCH',body:JSON.stringify({status:'acknowledged'})},token);
   setAlerts(old=>old.map(x=>x.id===a.id?{...x,status:'acknowledged'}:x));
   setAudioError('');onRefresh?.();
  }catch(e){setAudioError(e.message)}
 }
 const showSOS=!!activeSOS&&!opened&&!mapOpen;
 return <>
  <button type="button" className={'sos-toolbar '+(openSOS.length?'sos-toolbar-active':'')} onClick={()=>setOpened(v=>!v)} aria-label={`Notifications: ${openSOS.length} emergencies, ${otherOpen.length} other open alerts`} aria-expanded={opened} title="Notifications and emergencies"><BellRing size={18}/>{openSOS.length+otherOpen.length>0&&<span className="sos-counter">{openSOS.length+otherOpen.length}</span>}</button>
  {showSOS&&<aside className="sos-compact-toast sos-persistent" role="alert" aria-label="Unacknowledged SOS emergency">
   <div className="sos-compact-top"><ShieldAlert size={17}/><strong>Emergency SOS — response needed</strong><span className="sos-unacked">Unacknowledged</span></div>
   <p><b>{activeSOS.driver_name||'Driver'}</b> · {activeSOS.message||'Emergency assistance requested'}</p>
   <small className="sos-time">{dt(activeSOS.at)} {openSOS.length>1?` · ${openSOS.length} active SOS incidents`:''}</small>
   <div className="sos-compact-actions"><button type="button" onClick={()=>setOpened(true)}>View alerts</button><button type="button" onClick={()=>onMap(activeSOS)} disabled={activeSOS.lat==null||activeSOS.lng==null}>SOS map</button><button type="button" className="sos-ack-btn" onClick={()=>acknowledge(activeSOS)}>Acknowledge</button></div>
   {!soundReady&&<button type="button" className="sos-toast-sound" onClick={enableAudio}><BellRing size={14}/> Enable alarm sound</button>}
   {audioError&&<p className="sos-sound-error">{audioError}</p>}
  </aside>}
  {opened&&!mapOpen&&<section className="sos-command" role="region" aria-label="Notifications" aria-live="off">
   <header><div><ShieldAlert size={21}/><strong>Notification center</strong><span>{openSOS.length} SOS · {otherOpen.length} other</span></div><button type="button" onClick={()=>setOpened(false)} title="Close notifications" aria-label="Close notifications"><X size={18}/></button></header>
   <div className="sos-command-body">
    {openSOS.length>0&&<div className="sos-section-title danger"><ShieldAlert size={15}/> EMERGENCY SOS — immediate response</div>}
    {openSOS.map(a=><article className="sos-emergency-row" key={a.id}><strong>{a.driver_name||'Driver'}</strong><small>{a.vehicle||'Vehicle unavailable'} · {a.driver_phone||'No phone'} · {dt(a.at)}</small><p>{a.message||'Emergency assistance requested'}</p><div className="sos-command-actions">{a.lat!=null&&a.lng!=null&&<button type="button" onClick={()=>{setOpened(false);onMap(a)}}><MapPin size={14}/> SOS map</button>}<button type="button" onClick={()=>acknowledge(a)}>Acknowledge</button></div></article>)}
    {otherOpen.length>0&&<div className="sos-section-title"><BellRing size={15}/> Operational alerts (silent)</div>}
    {otherOpen.slice(0,8).map(a=><article className="sos-normal-row" key={a.id}><strong>{capital(a.kind||'Alert')}</strong><small>{a.driver_name||'System'} · {dt(a.at)}</small><p>{a.message}</p></article>)}
    {!openSOS.length&&!otherOpen.length&&<p className="sos-empty">No open notifications.</p>}
   </div>
   <footer className="sos-command-footer">
    {!soundReady?<button type="button" className="sos-sound" onClick={enableAudio}><BellRing size={15}/> Enable SOS alarm</button>:<span className="sos-sound-status"><CheckCircle2 size={15}/> Alarm enabled for this tab</span>}
    <button type="button" className="sos-view-all" onClick={()=>{setOpened(false);onNavigate('Alerts & SOS')}}>View all alerts</button>
    {audioError&&<p className="sos-sound-error">{audioError}</p>}
   </footer>
  </section>}
 </>;
}
function Login({onLogin}){
 const[email,Eml]=useState(''),[password,Pwd]=useState(''),[err,E]=useState(''),[busy,B]=useState(false);
 async function submit(e){e.preventDefault();B(true);E('');try{
  const x=await request('/auth/admin/login',{method:'POST',body:JSON.stringify({email,password})});
  if(x.user.role!=='manager')throw Error('Manager account required');onLogin(x)
 }catch(ex){E(ex.message)}finally{B(false)}}
 return <div className="login-wrap"><div className="login-panel"><img src="/login-product-logo.png" className="login-logo" alt="KRIYA360"/><div className="eyebrow">OPERATIONS MANAGEMENT PLATFORM</div><h1>Everything in motion.<br/><span>Everything under control.</span></h1><p>Track drivers, automate delivery operations, respond to emergencies and measure performance in one intelligent command center.</p><div className="login-benefits"><div><MapPinned/> Real-time fleet visibility</div><div><ShieldCheck/> Verified delivery proofs</div><div><Activity/> Actionable operations insights</div></div></div>
 <form onSubmit={submit} className="login-form"><div className="circle-icon"><LockKeyhole/></div><h2>Welcome back</h2><p>Sign in with your management email and password</p>
 <label>Admin email<input type="email" autoComplete="username" required value={email} onChange={e=>Eml(e.target.value)}/></label>
 <label>Password<input type="password" autoComplete="current-password" required value={password} onChange={e=>Pwd(e.target.value)}/></label>
 {err&&<div className="error" role="alert">{err}</div>}<button className="btn primary" disabled={busy}>{busy?'Please wait…':'Sign in to Dashboard'} <ArrowRight size={18}/></button>
</form></div>
}
function App(){const[auth,A]=useState(()=>{try{return JSON.parse(sessionStorage.getItem('kriya-auth'))}catch{return null}}),[page,P]=useState('Overview'),[data,D]=useState({drivers:[],tasks:[],expenses:[],alerts:[],performance:[],attendance:[],overview:{}}),[loading,L]=useState(false),[message,M]=useState(''),[modal,Q]=useState(''),[selected,T]=useState(null),[evidencePreview,EP]=useState(null),[routePreview,RP]=useState(null),[sidebar,SB]=useState(false),[accountMenu,AM]=useState(false),[sosSelection,SO]=useState(null);const token=auth?.access_token;const load=useCallback(async()=>{if(!token)return;try{const names=['drivers','tasks','expenses','alerts','performance','attendance','overview'];const result=await Promise.all(names.map(n=>request('/'+n,{},token)));D(Object.fromEntries(names.map((n,i)=>[n,result[i]])));}catch(e){if(e.status===401){sessionStorage.removeItem('kriya-auth');A(null);M('');return;}M(e.message)}},[token]);useEffect(()=>{load();if(!token)return;const id=setInterval(load,8000);return()=>clearInterval(id)},[load,token]);const login=x=>{sessionStorage.setItem('kriya-auth',JSON.stringify(x));A(x)};const logout=()=>{sessionStorage.removeItem('kriya-auth');AM(false);A(null);P('Overview')};async function action(path,method='POST',body){try{L(true);const x=await request(path,{method,...(body?{body:JSON.stringify(body)}:{})},token);await load();return x}catch(e){M(e.message);return null}finally{L(false)}}if(!auth)return <Login onLogin={login}/>;const {drivers,tasks,expenses,alerts,performance,attendance,overview}=data;const openAlerts=alerts.filter(a=>a.status==='open');return <div className="shell"><aside className={'sidebar '+(sidebar?'show':'')}><img src="/logo-sidebar.png" className="brand" alt="KRIYA360 product logo"/><div className="workspace"><span className="dot green"/> OPERATIONAL WORKSPACE</div><div className="nav-heading">MAIN MENU</div><nav>{nav.map(([name,Icon])=><button key={name} className={'navitem '+(page===name?'active':'')} onClick={()=>{P(name);SB(false)}}><Icon size={19}/><span>{name}</span>{name==='Alerts & SOS'&&openAlerts.length>0&&<em>{openAlerts.length}</em>}</button>)}</nav><div className="sidebar-company"><span>POWERED BY</span><img src="/company-logo.png" alt="IntProSec company logo"/></div></aside><main className="content"><header className="topbar"><button className="icon-btn mobile-menu" onClick={()=>SB(!sidebar)}><Menu/></button><div className="breadcrumbs">Workspace <span>/</span> <b>{page}</b></div><div className="top-right"><span className="live-pill"><span className="dot green"/> LIVE SYSTEM</span><button className="icon-btn" onClick={load} title="Refresh"><RefreshCcw size={19}/></button><SOSCommandAlert token={token} onNavigate={P} onMap={SO} onRefresh={load} mapOpen={!!sosSelection}/><div className="account-menu-wrap"><button type="button" className="avatar admin-avatar-button" onClick={()=>AM(v=>!v)} aria-haspopup="menu" aria-expanded={accountMenu} title="Account menu">{auth.user.name?.slice(0,2).toUpperCase()||'OM'}</button>{accountMenu&&<div className="account-menu" role="menu"><div className="account-menu-name"><b>{auth.user.name}</b><small>Management account</small></div><button type="button" role="menuitem" onClick={()=>{P('Management Users');AM(false)}}><UserRound size={16}/> Profile & management users</button><button type="button" role="menuitem" className="menu-logout" onClick={logout}><LogOut size={16}/> Log out</button></div>}</div></div></header><div className="main-inner"><div className="page-heading"><div><div className="eyebrow">KRIYA360 / {page.toUpperCase()}</div><h1>{page==='Overview'?'Operations overview':page}</h1><p>{page==='Overview'?'Visibility and control over every delivery, driver and decision.':`Manage your ${page.toLowerCase()} in one place.`}</p></div><div className="heading-actions"><span className="date-chip"><CalendarClock size={17}/>{new Date().toLocaleDateString('en-IN',{dateStyle:'medium'})}</span>{page==='Assignments'&&<button className="btn primary" onClick={()=>Q('task')}><Plus size={18}/> New Assignment</button>}{page==='Drivers'&&<button className="btn primary" onClick={()=>Q('driver')}><Plus size={18}/> Add Driver</button>}</div></div>{page==='Overview'&&<><div className="stats-grid"><Stats icon={UsersRound} label="Active Drivers" value={`${overview.active_drivers||0} / ${overview.drivers||0}`} small="Drivers on duty"/><Stats icon={Truck} label="Deliveries in Progress" value={overview.in_progress||0} accent="orange" small={`${overview.completed||0} completed`}/><Stats icon={Clock3} label="Delayed Deliveries" value={overview.delayed||0} accent="red" small="Requires attention"/><Stats icon={CheckCircle2} label="Completed Deliveries" value={overview.completed||0} accent="green" small="Successfully completed tasks"/></div><div className="cols-two"><section className="card"><div className="card-heading"><div><h3>All-driver live fleet map</h3><p>Latest GPS and each driver’s current in-progress delivery only</p></div><button className="text-button" onClick={()=>P('Live Tracking')}>View tracking <ArrowRight size={16}/></button></div><OverviewFleetMap drivers={drivers} tasks={tasks} token={token} height={390} onViewTracking={()=>P('Live Tracking')}/></section><section className="card"><div className="card-heading"><div><h3>Alerts & activity</h3><p>Operations needing your attention</p></div><Tag tone={overview.critical_alerts?'red':'blue'}>{openAlerts.length} Open</Tag></div><div className="alert-list">{openAlerts.length?openAlerts.slice(0,6).map(a=><div className="alert-card" key={a.id}><div className={'alert-icon '+(a.severity==='critical'?'red':'orange')}><AlertTriangle size={19}/></div><div><b>{capital(a.kind)}</b><p>{a.message}</p><small>{dt(a.at)}</small></div></div>):<Empty text="No open alerts"/>}</div><button className="view-all" onClick={()=>P('Alerts & SOS')}>View all alerts <ArrowRight size={17}/></button></section></div><div className="cols-two lower"><section className="card"><div className="card-heading"><div><h3>Latest assignments</h3><p>Current delivery progress</p></div><button className="text-button" onClick={()=>P('Assignments')}>View all</button></div><RecentAssignments rows={tasks.slice(0,5)} onRoute={RP}/></section><section className="card"><div className="card-heading"><div><h3>Driver availability</h3><p>Real-time shift attendance</p></div><button className="text-button" onClick={()=>P('Drivers')}>All drivers</button></div>{drivers.length?drivers.slice(0,6).map(d=><div className="driver-line" key={d.id}><span className="driver-initial">{d.name.split(' ').map(x=>x[0]).slice(0,2).join('')}</span><div><b>{d.name}</b><small>{d.vehicle||'Vehicle not assigned'}</small></div><Tag tone={d.on_shift?'green':'gray'}>{d.on_shift?'On shift':'Off shift'}</Tag></div>):<Empty/>}</section></div></>}
{page==='Drivers'&&<><BulkDriverImport token={token} onImported={load}/><section className="card"><div className="card-heading"><div><h3>Driver directory & licence verification</h3><p>Management creates drivers. Assignments unlock only after licence-number match and document review.</p></div></div><div className="table-wrap"><table><thead><tr><th>Driver / Phone</th><th>Vehicle</th><th>Licence number</th><th>Documents</th><th>Verification</th><th>Actions</th></tr></thead><tbody>{drivers.map(d=><tr key={d.id}><td><b>{d.name}</b><small>{d.phone}</small><small>Shift {d.shift_expected||'09:00'}</small></td><td>{d.vehicle||'—'}<small>{d.vehicle_plate||'—'}</small></td><td><b>{d.license_no||'—'}</b></td><td><div className="row-actions">{d.face_url?<button className="small-btn" onClick={()=>EP({title:`${d.name} • enrollment face image`,url:d.face_url,faceDriver:d})}>Face</button>:<Tag tone="orange">Face missing</Tag>}{d.license_url?<button className="small-btn" onClick={()=>EP({title:`${d.name} • driving licence proof`,url:d.license_url})}>Licence proof</button>:<Tag tone="orange">Licence missing</Tag>}</div></td><td><Tag tone={d.active===false?'red':d.approved&&d.license_verified?'green':'orange'}>{d.active===false?'Inactive':d.approved&&d.license_verified?'Approved + matched':'Pending verification'}</Tag>{d.license_review_note&&<small>{d.license_review_note}</small>}</td><td><div className="row-actions"><button className="small-btn" onClick={()=>Q({type:'edit-driver',driver:d})}>Edit</button>{d.active!==false&&d.license_url&&(!d.approved||!d.license_verified)&&<button className="small-btn" onClick={()=>Q({type:'review-driver',driver:d})}>Review licence</button>}{d.active!==false&&<button className="small-btn muted" onClick={async()=>{if(window.confirm(`Deactivate ${d.name}? Existing history remains.`))await action('/drivers/'+d.id,'DELETE')}}>Deactivate</button>}</div></td></tr>)}</tbody></table>{!drivers.length&&<Empty text="No drivers yet. Add one to begin."/>}</div></section></>}
{page==='Assignments'&&<section className="card"><div className="card-heading"><div><h3>Delivery assignments</h3><p>Route, timing, proof of delivery and verification — destination pin sent to driver app</p></div></div><TaskTable rows={tasks} onRoute={RP}/></section>}
{page==='Live Tracking'&&<LiveTracking drivers={drivers} tasks={tasks} token={token} onError={M}/> }
{page==='Expenses'&&<ExpenseGroups expenses={expenses} tasks={tasks} pendingTotal={overview.pending_expenses} onInspect={EP} onAction={action}/>}
{page==='Performance'&&<><PerformanceWorkspace records={performance} tasks={tasks} token={token} onSelectDriver={name=>{}}/><AttendancePerformance token={token} records={performance}/></>}
{page==='Attendance'&&<div className="attendance-layout"><AttendanceReports token={token} drivers={drivers}/><AttendanceRegister events={attendance} drivers={drivers}/></div>}
{page==='Management Users'&&<AdminUsers token={token} current={auth.user} onError={M} onProfileChange={u=>{const updated={...auth,user:u};sessionStorage.setItem('kriya-auth',JSON.stringify(updated));A(updated)}}/>}
{page==='Alerts & SOS'&&<AlertWorkspace alerts={alerts} onAction={action} onMap={SO}/>}
</div></main>{message&&<div className="toast"><span>{message}</span><button onClick={()=>M('')}><X size={16}/></button></div>}{sosSelection&&<SOSLocation alert={sosSelection} token={token} onClose={()=>SO(null)}/>} {routePreview&&<RouteDetail task={routePreview} token={token} onClose={()=>RP(null)}/>} {evidencePreview&&<EvidenceDialog item={evidencePreview} token={token} onClose={()=>EP(null)} onReviewed={async(approved)=>{if(evidencePreview.faceDriver){const result=await action('/drivers/'+evidencePreview.faceDriver.id+'/face-review','PATCH',{approved,review_note:approved?'Manager visually reviewed submitted face photo':'Rejected: please upload a new face photo'});if(result){EP(null);M(approved?'Face photo reviewed (not biometric verification)':'Driver can now resubmit their face photo.')}}else if(evidencePreview.expense){const result=await action('/expenses/'+evidencePreview.expense.id+'/mark-reviewed');if(result){EP(null);M('Payment evidence reviewed; approve or reject from the table.')}}}}/>}{modal&&(typeof modal==='object'?<DriverEditDialog selection={modal} onClose={()=>Q('')} onSave={async(payload,kind)=>{const d=modal.driver;let r;if(kind==='approve'||kind==='reject')r=await action('/drivers/'+d.id+'/approval','PATCH',payload);else r=await action('/drivers/'+d.id,'PATCH',payload);if(r)Q('')}}/>:<Modal kind={modal} token={token} drivers={drivers.filter(d=>d.active!==false&&d.approved&&d.license_verified)} onClose={()=>Q('')} onSubmit={async x=>{const result=await action(modal==='driver'?'/drivers':'/tasks','POST',x);if(result){Q('');M(modal==='driver'?'Driver created: pending licence verification':'Task assigned successfully')}}} onSuggest={async(lat,lng)=>request(`/driver-suggestions?lat=${lat}&lng=${lng}`,{},token)}/>)}</div>}
function ExpenseGroups({expenses,tasks,pendingTotal,onInspect,onAction}){
 const [expanded,SE]=useState({});
 const groups=Object.values(expenses.reduce((acc,e)=>{const key=e.task_id||'unassigned';if(!acc[key])acc[key]={key,items:[]};acc[key].items.push(e);return acc;},{}));
 groups.sort((a,b)=>String(b.items[0]?.created_at||'').localeCompare(String(a.items[0]?.created_at||'')));
 return <section className="card"><div className="card-heading"><div><h3>Delivery expense register</h3><p>One delivery per card. Expand to review each payment and its evidence.</p></div><Tag tone="orange">{money(pendingTotal)} pending</Tag></div>
  <div className="delivery-expense-list">{groups.map(g=>{const t=tasks.find(x=>x.id===g.key);const total=g.items.reduce((n,e)=>n+Number(e.amount||0),0);const pending=g.items.filter(e=>e.status==='pending').length;const opened=!!expanded[g.key];return <article className="delivery-expense-group" key={g.key}>
    <button type="button" className="delivery-expense-header" aria-expanded={opened} onClick={()=>SE(prev=>({...prev,[g.key]:!prev[g.key]}))}>
     <span className="delivery-expense-icon"><Truck size={20}/></span><span className="delivery-expense-summary"><strong>{t?.title||`Delivery ${String(g.key).slice(0,8)}`}</strong><small>{g.items[0]?.driver_name||'Driver unavailable'} · {t?.address||'Delivery expenses'}</small><small>{g.items.length} expense{g.items.length===1?'':'s'} · {t?.status?capital(t.status):'Delivery status unavailable'}</small></span>
     <span className="delivery-expense-total"><b>{money(total)}</b><small>{pending?`${pending} pending review`:'No pending items'}</small></span><ArrowRight className={opened?'expense-expand-arrow expanded':'expense-expand-arrow'} size={20}/>
    </button>
    {opened&&<div className="delivery-expense-entries">{g.items.map((e,i)=><div className="delivery-expense-entry" key={e.id}>
       <span className="expense-number">{i+1}</span><div className="expense-description"><b>{capital(e.category)}</b><small>{dt(e.created_at)}</small>{(e.fraud_flags||[]).length>0&&<span className="fraud-flags"><AlertTriangle size={13}/> Review flag: {(e.fraud_flags||[]).join(' · ')} (not a fraud finding)</span>}</div>
       <strong className="expense-amount">{money(e.amount)}</strong><Tag tone={e.status==='approved'?'green':e.status==='rejected'?'red':'orange'}>{capital(e.status)}</Tag>
       <div className="expense-entry-actions">{e.receipt_url?<button className="small-btn" onClick={()=>onInspect({title:`Payment evidence • ${e.driver_name} • ${money(e.amount)}`,url:e.receipt_url,expense:e})}><Camera size={14}/> {e.evidence_reviewed?'View receipt':'Inspect receipt'}</button>:<Tag tone="red">No evidence</Tag>}
       {e.status==='pending'&&<div className="row-actions"><button className="small-btn" disabled={!e.receipt_url||!e.evidence_reviewed} onClick={()=>onAction('/expenses/'+e.id,'PATCH',{status:'approved'})}>Approve</button><button className="small-btn muted" disabled={!e.receipt_url||!e.evidence_reviewed} onClick={()=>onAction('/expenses/'+e.id,'PATCH',{status:'rejected'})}>Reject</button></div>}</div>
      </div>)}</div>}
   </article>})}{!groups.length&&<Empty text="No expenses submitted yet"/>}</div>
 </section>;
}
function DriverEditDialog({selection,onClose,onSave}){
 const d=selection.driver,review=selection.type==='review-driver';
 const [f,F]=useState({name:d.name,phone:d.phone,license_no:d.license_no||'',vehicle:d.vehicle||'',vehicle_plate:d.vehicle_plate||'',shift_expected:d.shift_expected||'09:00',active:d.active!==false});
 const [matches,SM]=useState(false),[note,SN]=useState(''),[busy,B]=useState(false);
 const set=(k,v)=>F(x=>({...x,[k]:v}));
 return <div className="modal-backdrop" role="dialog" aria-modal="true"><form className="modal" onSubmit={async e=>{e.preventDefault();B(true);try{if(review){if(!matches){alert('Compare the original licence image with its typed number before confirming.');return;}await onSave({approved:true,license_matches:true,review_note:note||'Original document visually compared against licence number'},'approve');}else await onSave(f,'edit');}finally{B(false)}}}>
 <div className="modal-heading"><div><div className="eyebrow">DRIVER ADMINISTRATION</div><h2>{review?'Verify driver licence':'Edit driver details'}</h2></div><button type="button" className="icon-btn" onClick={onClose}><X/></button></div>
 {review?<><p><b>{d.name}</b> • {d.phone}</p><div className="review-number">Typed licence number: <b>{d.license_no}</b></div><p>First open the licence image from the driver directory. Compare the complete number, name and visible document details. The check is human-reviewed, not automatic OCR.</p><label className="review-confirm"><input type="checkbox" checked={matches} onChange={e=>SM(e.target.checked)}/> I personally inspected the uploaded licence image and confirmed its number exactly matches <b>{d.license_no}</b>.</label><label>Review note<textarea value={note} onChange={e=>SN(e.target.value)} placeholder="Optional discrepancies or verification notes"/></label></>:<div className="form-grid">{[['name','Full name'],['phone','Mobile number'],['license_no','Licence number'],['vehicle_plate','Vehicle plate'],['shift_expected','Shift time HH:MM']].map(([k,l])=><label key={k}>{l}<input value={f[k]} onChange={e=>set(k,k==='license_no'?e.target.value.toUpperCase():e.target.value)} required={k!=='vehicle_plate'} pattern={k==='license_no'?'[A-Za-z]{2}[0-9]{2}(19|20)[0-9]{2}[0-9]{7}':k==='phone'?'[6-9][0-9]{9}':undefined} title={k==='license_no'?'Format KA0120230001234':undefined}/></label>)}<label>Truck / Lorry<select value={f.vehicle} onChange={e=>set('vehicle',e.target.value)}>{['','Lorry','Truck','Heavy Truck','Container Truck'].map(v=><option key={v} value={v}>{v||'Unassigned'}</option>)}</select></label><label>Status<select value={f.active?'active':'inactive'} onChange={e=>set('active',e.target.value==='active')}><option value="active">Active</option><option value="inactive">Inactive</option></select></label></div>}
 <div className="modal-footer"><button type="button" className="btn secondary" onClick={onClose}>Cancel</button>{review&&<button type="button" className="btn license-reject-btn" disabled={busy} onClick={async()=>{B(true);try{await onSave({approved:false,license_matches:false,review_note:note.trim()||"Rejected: invalid or unreadable licence evidence; submit a genuine driving licence image"},"reject")}finally{B(false)}}}>Reject / request resubmission</button>}<button className="btn primary" disabled={busy||(review&&!matches)}>{review?'Approve verified driver':'Save driver details'}</button></div></form></div>
}
function EvidenceDialog({item,token,onClose,onReviewed}){
 const[url,U]=useState(null),[error,E]=useState(''),[busy,B]=useState(false);
 useEffect(()=>{let active=true,link=null;fetch(item.url,{headers:{Authorization:'Bearer '+token}}).then(r=>{if(!r.ok)throw new Error('Unable to open authorized evidence');return r.blob()}).then(b=>{link=URL.createObjectURL(b);if(active)U(link)}).catch(e=>{if(active)E(e.message)});return()=>{active=false;if(link)URL.revokeObjectURL(link)}},[item.url,token]);
 return <div className="modal-backdrop" role="dialog" aria-modal="true"><div className="modal evidence-dialog"><div className="modal-heading"><h2>{item.title}</h2><button className="icon-btn" onClick={onClose}><X/></button></div>{error&&<p className="fraud-flags">{error}</p>}{url?<img className="evidence-image" alt="Authorized submitted evidence" src={url}/>:!error&&<p>Loading evidence securely...</p>}{item.faceDriver&&<div className="evidence-details"><p><b>Face-photo review:</b> {item.faceDriver.face_review_status||'pending'}</p><p>This confirms that management visually reviewed the uploaded photo. It is NOT biometric face matching or identity verification.</p>{item.faceDriver.face_review_note&&<small>{item.faceDriver.face_review_note}</small>}{item.faceDriver.face_review_status!=='approved'&&<div className="modal-footer"><button className="btn secondary" disabled={!url||busy} onClick={async()=>{B(true);try{await onReviewed(false)}finally{B(false)}}}>Reject / request new photo</button><button className="btn primary" disabled={!url||busy} onClick={async()=>{B(true);try{await onReviewed(true)}finally{B(false)}}}>Mark photo reviewed</button></div>}</div>}{item.expense&&<><div className="evidence-details"><b>Amount: {money(item.expense.amount)}</b><p>Category: {capital(item.expense.category)} • Submitted: {dt(item.expense.created_at)}</p>{(item.expense.fraud_flags||[]).map((f,i)=><p className="fraud-flags" key={i}><AlertTriangle size={15}/>{f}</p>)}<small>Flags are heuristic risk indicators, not proof of fraud. Check the actual receipt against the amount and payment.</small></div><button className="btn primary" disabled={!url||busy} onClick={async()=>{B(true);await onReviewed();B(false)}}><ShieldCheck size={16}/> Mark evidence reviewed</button></>}</div></div>
}
function RouteFit({positions}){const map=useMap();useEffect(()=>{if(positions.length>1){map.fitBounds(L.latLngBounds(positions),{padding:[25,25]});setTimeout(()=>map.invalidateSize(),100)}},[map,positions]);return null}
function RouteDetail({task,token,onClose}){
 const[route,R]=useState(null),[error,E]=useState(''),[mode,SM]=useState('fastest');
 useEffect(()=>{let live=true;R(null);E('');request('/tasks/'+task.id+'/route?mode='+mode,{},token).then(data=>{if(live)R(data)}).catch(e=>{if(live)E(e.message)});return()=>{live=false}},[task.id,token,mode]);
 const positions=(route?.coordinates||[]).map(c=>[c[1],c[0]]).filter(p=>p.every(Number.isFinite));
 const road=route?.source?.startsWith('OSRM')||route?.source?.startsWith('TomTom');
 return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}} role="dialog" aria-modal="true"><div className="modal route-dialog"><div className="modal-heading"><div><div className="eyebrow">DRIVING ROUTE</div><h2>{task.title}</h2><p>{task.address}</p></div><button className="icon-btn" onClick={onClose}><X/></button></div>
 {error&&<p className="fraud-flags">{error}</p>}{!route&&!error&&<p>Calculating route from the driver's latest GPS position...</p>}
 <div className="route-summary"><label>Route preference <select value={mode} onChange={e=>SM(e.target.value)}><option value="fastest">Fastest (traffic-aware if enabled)</option><option value="shortest">Shortest (when supported)</option></select></label></div>
 {route&&<><div className="route-summary"><b>{route.distance_km} km</b><b>{route.duration_min} min estimated</b><Tag tone={road?'green':'orange'}>{route.traffic_aware?'Traffic-aware road route':road?'Road route • no live traffic':'Straight-line estimate only'}</Tag></div>
 <div className="route-map-panel"><MapContainer center={positions[0]||[task.lat,task.lng]} zoom={12} style={{width:'100%',height:350}} scrollWheelZoom><LayerTiles/>{positions.length>1&&<>{(route?.alternative_routes||[]).map((alt,i)=><Polyline key={i} positions={(alt.coordinates||[]).map(c=>[c[1],c[0]])} pathOptions={{color:'#2563eb',weight:3,opacity:.65,dashArray:'6 7'}}/>)}<Polyline positions={positions} pathOptions={{color:'#ff761c',weight:6}}/><Marker position={positions[0]} icon={markerIcon}><Popup>Driver's last reported GPS</Popup></Marker><Marker position={positions[positions.length-1]} icon={markerIcon}><Popup>Delivery destination</Popup></Marker><RouteFit positions={positions}/></>}</MapContainer></div>
 {route?.traffic_aware&&<p>Current traffic delay estimate: {route.traffic_delay_min??0} minutes. The ETA may change.</p>}{!route?.traffic_aware&&road&&<p className="evidence-note">Traffic data is not enabled. ETA is based on road routing estimates only.</p>}{!road&&<p className="fraud-flags">Road routing is currently unavailable. The line shown is not a drivable navigation path; do not follow it as driving instructions.</p>}</>}
 <div className="modal-footer"><button className="btn primary" onClick={onClose}>Close</button></div></div></div>
}
function AdminUsers({token,current,onError,onProfileChange}){
 const [users,U]=useState([]),[form,F]=useState({name:'',phone:'',email:'',password:''}),[editing,E]=useState(null),[busy,B]=useState(false);
 const reload=useCallback(async()=>{try{U(await request('/management/users',{},token))}catch(e){onError(e.message)}},[token,onError]);
 useEffect(()=>{reload()},[reload]);
 async function submit(e){e.preventDefault();B(true);try{if(editing){const user=await request('/management/users/'+editing.id,{method:'PATCH',body:JSON.stringify({name:form.name,phone:form.phone,email:form.email,...(form.password?{password:form.password}:{})})},token);if(user.id===current.id)onProfileChange(user)}else await request('/management/users',{method:'POST',body:JSON.stringify(form)},token);E(null);F({name:'',phone:'',email:'',password:''});await reload()}catch(err){onError(err.message)}finally{B(false)}}
 async function deactivate(u){if(!window.confirm(`Deactivate ${u.name}? Their access will be removed.`))return;try{await request('/management/users/'+u.id,{method:'DELETE'},token);await reload()}catch(e){onError(e.message)}}
 return <section className="card admin-management"><div className="card-heading"><div><h3>Dashboard administrators</h3><p>Create and manage authorized KRIYA360 management logins. Deactivation preserves existing operations history.</p></div></div><div className="admin-user-grid"><form onSubmit={submit} className="admin-user-form"><h3>{editing?'Edit manager':'Add management user'}</h3><label>Full name<input required minLength="2" value={form.name} onChange={e=>F({...form,name:e.target.value})}/></label><label>Phone number<input required pattern="[6-9][0-9]{9}" title="10-digit Indian phone number" value={form.phone} onChange={e=>F({...form,phone:e.target.value})}/></label><label>Email address<input type="email" required value={form.email} onChange={e=>F({...form,email:e.target.value})}/></label><label>{editing?'New password (optional)':'Password (minimum 12 characters)'}<input type="password" minLength={12} required={!editing} autoComplete="new-password" value={form.password} onChange={e=>F({...form,password:e.target.value})}/></label><div className="row-actions"><button className="btn primary" disabled={busy}>{busy?'Saving…':editing?'Save changes':'Add manager'}</button>{editing&&<button type="button" className="small-btn muted" onClick={()=>{E(null);F({name:'',phone:'',email:'',password:''})}}>Cancel edit</button>}</div></form><div className="table-wrap"><table><thead><tr><th>Manager</th><th>Phone</th><th>Status</th><th>Actions</th></tr></thead><tbody>{users.map(u=><tr key={u.id}><td><b>{u.name}</b>{u.id===current.id&&<small>Your account</small>}</td><td>{u.phone}<small>{u.email||"Email setup pending"}</small></td><td><Tag tone={u.active?'green':'red'}>{u.active?'Active':'Inactive'}</Tag></td><td><div className="row-actions"><button className="small-btn" onClick={()=>{E(u);F({name:u.name,phone:u.phone,email:u.email||'',password:''})}}>Edit</button>{u.id!==current.id&&u.active&&<button className="small-btn muted" onClick={()=>deactivate(u)}>Deactivate</button>}</div></td></tr>)}</tbody></table></div></div></section>
}
function RecentAssignments({rows,onRoute}){return <div className="recent-assignments">{rows.map(t=><div className="recent-assignment" key={t.id}><div className="recent-assignment-main"><b>{t.title}</b><small>{t.driver_name||'Unassigned'} · <MapPin size={12}/>{t.address||'Destination not set'}</small></div><Tag tone={t.status==='completed'?'green':t.status==='in_progress'?'blue':'orange'}>{capital(t.status)}</Tag><button type="button" className="recent-route" onClick={()=>onRoute(t)} aria-label={'Open route map for '+t.title} title="View road route"><Route size={16}/><span>Route</span></button></div>)}{!rows.length&&<Empty text="No assignments yet"/>}</div>}
function TaskTable({rows,onRoute}){return <div className="table-wrap"><table><thead><tr><th>Delivery</th><th>Driver</th><th>Destination</th><th>Deadline</th><th>Status</th><th>Road route</th><th>Proof / Customer OTP</th></tr></thead><tbody>{rows.map(t=><tr key={t.id}><td><b>{t.title}</b><small>{t.customer||t.id.slice(0,8)}</small></td><td>{t.driver_name||'—'}</td><td className="dest"><MapPin size={14}/>{t.address}</td><td>{dt(t.due_at)}</td><td><Tag tone={t.status==='completed'?'green':t.status==='in_progress'?'blue':'orange'}>{capital(t.status)}</Tag></td><td><button className="small-btn" onClick={()=>onRoute(t)}><Route size={15}/> View road map</button><small>{t.route_distance_km?`${t.route_distance_km} km · ${t.route_duration_min} min`:'Requires driver GPS'}</small></td><td>{t.otp_verified?<Tag tone="green"><CheckCircle2 size={13}/> Recipient OTP verified</Tag>:t.status==='completed'?'—':<Tag tone="blue">Driver sends OTP to customer</Tag>}{t.proof_url&&<small>Delivery photo stored</small>}{t.late_reason&&<small className="late-note">Driver delay reason: {t.late_reason}</small>}</td></tr>)}</tbody></table>{!rows.length&&<Empty text="No assigned deliveries yet"/>}</div>}
function Modal({kind,drivers,onClose,onSubmit,onSuggest,token}){const[form,F]=useState(kind==='driver'?{name:'',phone:'',pin:'1234',license_no:'',vehicle:'',vehicle_plate:'',language:'en',shift_expected:'09:00'}:{title:'',driver_id:drivers[0]?.id||'',address:'',lat:12.9716,lng:77.5946,due_at:new Date(Date.now()+3*3600000).toISOString().slice(0,16),priority:'normal',customer:'',customer_phone:'',instructions:''}),[busy,B]=useState(false),[suggestions,S]=useState([]);const field=(name,label,type='text',required=false)=><label key={name}>{label}<input type={type} required={required} value={form[name]} onChange={e=>F({...form,[name]:e.target.value})}/></label>;return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose()}}><form className="modal" onSubmit={async e=>{e.preventDefault();B(true);const val=kind==='task'?{...form,lat:Number(form.lat),lng:Number(form.lng),due_at:new Date(form.due_at).toISOString()}:form;await onSubmit(val);B(false)}}><div className="modal-heading"><div><div className="eyebrow">KRIYA360 OPERATIONS</div><h2>{kind==='driver'?'Register Driver':'Create Delivery Assignment'}</h2></div><button type="button" className="icon-btn" onClick={onClose}><X/></button></div>{kind==='driver'?<div className="form-grid">{field('name','Full name','text',true)}<label>Phone number<input type="tel" required pattern="[6-9][0-9]{9}" title="10-digit Indian mobile number" value={form.phone} onChange={e=>F({...form,phone:e.target.value})}/></label>{field('pin','Driver PIN','text',true)}<label>Driving licence number<input value={form.license_no} required placeholder="KA0120230001234" pattern="[A-Za-z]{2}[0-9]{2}(19|20)[0-9]{2}[0-9]{7}" title="Format: KA0120230001234" onChange={e=>F({...form,license_no:e.target.value.toUpperCase()})}/></label><label>Vehicle type (optional)<select value={form.vehicle} onChange={e=>F({...form,vehicle:e.target.value})}><option value="">Not assigned</option><option value="Lorry">Lorry</option><option value="Truck">Truck</option><option value="Heavy Truck">Heavy Truck</option><option value="Container Truck">Container Truck</option></select></label>{field('vehicle_plate','Vehicle registration (optional)')}{field('shift_expected','Scheduled punch-in (HH:MM)')}<label>Language<select value={form.language} onChange={e=>F({...form,language:e.target.value})}><option value="en">English</option><option value="hi">Hindi</option><option value="kn">Kannada</option><option value="ta">Tamil</option><option value="te">Telugu</option></select></label></div>:<><div className="form-grid">{field('title','Delivery title','text',true)}<label>Assigned Driver<select value={form.driver_id} required onChange={e=>F({...form,driver_id:e.target.value})}>{drivers.filter(d=>d.active!==false&&d.approved&&d.license_verified).map(d=><option value={d.id} key={d.id}>{d.name}</option>)}</select></label>{field('address','Delivery address / landmark','text',true)}{field('due_at','Expected delivery deadline','datetime-local',true)}{field('lat','Destination latitude','number',true)}{field('lng','Destination longitude','number',true)}{field('customer','Customer name')}<label>Recipient mobile number (required for SMS OTP)<input required type="tel" pattern="(?:[6-9][0-9]{9}|91[6-9][0-9]{9}|\+91[6-9][0-9]{9})" placeholder="9876543210" value={form.customer_phone} onChange={e=>F({...form,customer_phone:e.target.value})}/></label><label>Priority<select value={form.priority} onChange={e=>F({...form,priority:e.target.value})}><option value="normal">Normal</option><option value="high">High</option><option value="critical">Critical</option></select></label>{field('instructions','Delivery notes')}</div><DestinationSearch token={token} onChoose={place=>F(current=>({...current,address:place.label,lat:place.lat,lng:place.lng}))}/><DestinationPicker lat={form.lat} lng={form.lng} onPick={(lat,lng)=>F(current=>({...current,lat:Number(lat.toFixed(6)),lng:Number(lng.toFixed(6))}))}/><button type="button" className="small-btn" onClick={async()=>{try{S(await onSuggest(Number(form.lat),Number(form.lng)))}catch(e){alert(e.message)}}}><Navigation size={14}/> Suggest nearest available driver</button>{suggestions.length>0&&<div className="suggestion-list">{suggestions.slice(0,4).map(d=><button type="button" key={d.driver_id} onClick={()=>F({...form,driver_id:d.driver_id})}>{d.name} · {d.distance_km??'GPS unavailable'} km · {d.active_tasks} active tasks</button>)}</div>}</>}<div className="modal-footer"><button type="button" className="btn secondary" onClick={onClose}>Cancel</button><button className="btn primary" disabled={busy}>{busy?'Saving…':kind==='driver'?'Create pending driver':'Assign Delivery'} <ArrowRight size={16}/></button></div></form></div>}
createRoot(document.getElementById('root')).render(<App/>);
