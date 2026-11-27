import React, {useCallback, useEffect, useState} from 'react';
import {API, apiFetch} from './apiConfig.js';
import {RefreshCcw, Store, Package, AlertTriangle, X, ArrowLeft} from 'lucide-react';

const statusText = value => String(value || '').replaceAll('_',' ');
async function request(token,path,method='GET',body) {
  const r=await apiFetch(API+'/marketplace'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});
  const data=await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(typeof data.detail==='string'?data.detail:'Request failed ('+r.status+')');
  return data;
}
export default function MerchantWorkspace({token}) {
  const [merchants,setMerchants]=useState([]),[bookings,setBookings]=useState([]),[loading,setLoading]=useState(false),[error,setError]=useState(''),[enabled,setEnabled]=useState(null),[review,setReview]=useState(null),[note,setNote]=useState(''),[saving,setSaving]=useState(false),[filter,setFilter]=useState('all'),[reviewError,setReviewError]=useState(''),[notice,setNotice]=useState('');
  const savingRef=React.useRef(false);
  const close=useCallback(()=>{if(!savingRef.current){setReview(null);setNote('');setReviewError('')}},[]);
  useEffect(()=>{if(!review)return;const key=e=>{if(e.key==='Escape'){e.preventDefault();close()}};window.addEventListener('keydown',key);return()=>window.removeEventListener('keydown',key)},[review,close]);
  const load=useCallback(async()=>{
    setLoading(true);setError('');
    try{
      const h=await request(token,'/health');setEnabled(h.enabled&&h.configured);
      if(!h.enabled||!h.configured)return;
      const [m,b]=await Promise.all([request(token,'/admin/merchants'),request(token,'/admin/bookings')]);setMerchants(m);setBookings(b);
    }catch(e){setError(e.message)}finally{setLoading(false)}
  },[token]);
  useEffect(()=>{load()},[load]);
  const change=async e=>{
    e.preventDefault();if(savingRef.current||note.trim().length<3)return;
    savingRef.current=true;setSaving(true);setReviewError('');setNotice('');
    try{
      if(review.kind==='merchant')await request(token,'/admin/merchants/'+encodeURIComponent(review.id),'PATCH',{state:review.state,note:note.trim()});
      else await request(token,'/admin/bookings/'+encodeURIComponent(review.id)+'/cancel-pickup','POST',{reason:note.trim()});
      setReview(null);setNote('');setNotice('Review saved successfully.');await load();
    }catch(e){setReviewError(e.message)}finally{savingRef.current=false;setSaving(false)}
  };
  const open=(kind,id,state,label)=>{setReview({kind,id,state,label});setNote('');setReviewError('');setNotice('');};
  return <div className="merchant-workspace">
    <section className="card"><div className="card-heading"><div><h3>Merchant marketplace</h3><p>Review independent businesses and monitor driver pickups.</p></div><button className="small-btn" disabled={loading} onClick={load}><RefreshCcw size={15}/> {loading?'Refreshing…':'Refresh'}</button></div>
      {notice&&<p role="status" className="merchant-notice">{notice}</p>}{error&&<p role="alert" style={{color:'#b91c1c',padding:12}}><AlertTriangle size={16}/> {error}</p>}
      {enabled===false&&<p style={{padding:12}}>The merchant pilot is disabled or its backend security configuration is incomplete. Existing operations are unaffected.</p>}
      {enabled&&<div className="stats-grid" style={{padding:12}}>{[["Registered merchants",merchants.length],["Awaiting review",merchants.filter(m=>m.state==='pending').length],["Active pickups",bookings.filter(b=>['requested','accepted','arrived','collected','in_transit'].includes(b.state)).length]].map(([label,n])=><div className="stat" key={label}><div><p>{label}</p><strong>{n}</strong></div></div>)}</div>}
    </section>
    {enabled&&<><section className="card"><div className="card-heading"><div><h3><Store size={18}/> Merchant approvals</h3><p>Verify the applicant’s contact and business information independently before approving. Registration does not prove identity or store ownership.</p></div><select aria-label="Filter merchants" value={filter} onChange={e=>setFilter(e.target.value)}>{['all','pending','approved','rejected','suspended'].map(x=><option key={x} value={x}>{statusText(x)}</option>)}</select></div>
    <div className="table-wrap"><table><thead><tr><th>Business</th><th>Applicant / contact</th><th>Pickup address</th><th>Status</th><th>Review</th></tr></thead><tbody>{merchants.filter(m=>filter==='all'||filter===m.state).map(m=><tr key={m.id}><td><b>{m.business_name}</b><small>{m.business_type}</small></td><td>{m.name}<small>{m.email}</small><small>{m.phone}</small></td><td>{m.pickup_address}</td><td>{statusText(m.state)}<small>{m.review_note}</small></td><td><div className="row-actions">{m.state!=='approved'&&<button className="small-btn" onClick={()=>open('merchant',m.id,'approved','Approve '+m.business_name)}>Approve</button>}{m.state==='pending'&&<button className="small-btn" onClick={()=>open('merchant',m.id,'rejected','Reject '+m.business_name)}>Reject</button>}{m.state==='approved'&&<button className="small-btn" onClick={()=>open('merchant',m.id,'suspended','Suspend '+m.business_name)}>Suspend</button>}</div></td></tr>)}</tbody></table>{!merchants.length&&<p style={{padding:16}}>No merchants registered.</p>}</div></section>
    <section className="card"><div className="card-heading"><div><h3><Package size={18}/> Pickup requests</h3><p>Accepted pickups reserve the driver until verified collection or cancellation. Delivery completion uses the existing task workflow.</p></div></div><div className="table-wrap"><table><thead><tr><th>Package</th><th>Merchant / driver</th><th>Pickup and destination</th><th>Status</th><th>Actions</th></tr></thead><tbody>{bookings.map(b=><tr key={b.id}><td><b>{b.title}</b><small>{b.id.slice(0,8)}</small></td><td>{b.merchant_name}<small>{b.driver_name}</small></td><td>{b.pickup_address}<small>{b.delivery_address}</small></td><td>{statusText(b.state)}{b.problem&&<small role="status">Issue: {b.problem}</small>}</td><td>{['requested','accepted','arrived'].includes(b.state)&&<button className="small-btn" onClick={()=>open('booking',b.id,'cancelled','Cancel pickup '+b.title)}>Cancel pickup</button>}{b.task_id&&<small>Existing task: {b.task_id.slice(0,8)}</small>}</td></tr>)}</tbody></table>{!bookings.length&&<p style={{padding:16}}>No pickup requests.</p>}</div></section></>}
    {review&&<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)close()}}><form className="modal merchant-review-modal" role="dialog" aria-modal="true" aria-labelledby="merchant-review-title" onSubmit={change}>
      <div className="modal-heading"><div><div className="eyebrow">KRIYA360 / MERCHANT REVIEW</div><h2 id="merchant-review-title">{review.label}</h2></div><button type="button" className="icon-btn" aria-label="Close review" disabled={saving} onClick={close}><X size={20}/></button></div>
      <p>Record the reason for this decision. This action is audited.</p>
      <label htmlFor="merchant-review-note">{review.kind==='booking'?'Cancellation reason':'Review reason'}</label><textarea id="merchant-review-note" autoFocus required minLength={3} maxLength={500} rows={4} value={note} disabled={saving} onChange={e=>setNote(e.target.value)} placeholder="Enter at least 3 characters" aria-describedby="merchant-review-help"/>
      <div id="merchant-review-help" className="merchant-review-help">At least 3 characters <span>{note.length}/500</span></div>
      {reviewError&&<p role="alert" className="merchant-review-error">{reviewError}</p>}
      <div className="modal-footer"><button type="button" className="btn secondary" disabled={saving} onClick={close}><ArrowLeft size={16}/> Back</button><button type="submit" className="btn primary" disabled={saving||note.trim().length<3}>{saving?'Saving…':({approved:'Approve merchant',rejected:'Reject merchant',suspended:'Suspend merchant',cancelled:'Cancel pickup'}[review.state]||'Confirm')}</button></div>
    </form></div>}
  </div>;
}
