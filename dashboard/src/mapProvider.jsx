// KRIYA360 map compatibility facade: Google Maps when configured, Leaflet otherwise.
// Preserves the existing map widgets and GPS/route data contracts.
import React,{createContext,useContext,useEffect,useMemo,useRef,useState} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import * as Leaf from 'react-leaflet';

export const GOOGLE_MAPS_ACTIVE=Boolean(import.meta.env.VITE_GOOGLE_MAPS_BROWSER_KEY?.trim());
const Context=createContext(null);
let scriptPromise;
function loadGoogle(){
 if(window.google?.maps)return Promise.resolve(window.google);
 if(scriptPromise)return scriptPromise;
 scriptPromise=new Promise((resolve,reject)=>{
  const script=document.createElement('script');
  script.src=`https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(import.meta.env.VITE_GOOGLE_MAPS_BROWSER_KEY)}&v=weekly&loading=async`;
  script.async=true;
  script.onload=()=>window.google?.maps?resolve(window.google):reject(Error('Google Maps did not initialize'));
  script.onerror=()=>reject(Error('Google Maps script could not be loaded'));
  document.head.appendChild(script);
 });
 return scriptPromise;
}
function coords(value){return {lat:Number(value[0]),lng:Number(value[1])}}
function googleBounds(bounds){
 const b=new window.google.maps.LatLngBounds();
 if(Array.isArray(bounds))bounds.forEach(p=>b.extend(coords(p)));
 else if(bounds?.getSouthWest){b.extend(bounds.getSouthWest());b.extend(bounds.getNorthEast())}
 return b;
}
function createFacade(map){
 return {
  native:map,
  getZoom:()=>map.getZoom()||11,
  flyTo:(position,zoom)=>{map.panTo(coords(position));if(zoom)map.setZoom(zoom)},
  fitBounds:(bounds,options={})=>{map.fitBounds(googleBounds(bounds),options.padding?.[0]||35);if(options.maxZoom){window.google.maps.event.addListenerOnce(map,'idle',()=>{if(map.getZoom()>options.maxZoom)map.setZoom(options.maxZoom)})}},
  invalidateSize:()=>window.google.maps.event.trigger(map,'resize'),
  addLayer:layer=>{
   if(layer?.options?.radius&&layer?._latlng){
    const circle=new window.google.maps.Circle({map,center:{lat:layer._latlng.lat,lng:layer._latlng.lng},radius:layer.options.radius,strokeColor:layer.options.color||'#ea580c',fillColor:layer.options.fillColor||'#fb923c',fillOpacity:layer.options.fillOpacity??.12,strokeWeight:layer.options.weight||2});
    layer.__googleCircle=circle;
   }
  },
  removeLayer:layer=>{layer?.__googleCircle?.setMap(null)}
 };
}
function GoogleContainer({center,zoom=11,children,style={},scrollWheelZoom=true}){
 const target=useRef(null),[map,setMap]=useState(null),[error,setError]=useState('');
 useEffect(()=>{
  let active=true;
  loadGoogle().then(()=>{
   if(!active||!target.current)return;
   const instance=new window.google.maps.Map(target.current,{
    center:coords(center),zoom,scrollwheel:Boolean(scrollWheelZoom),
    mapTypeControl:false,streetViewControl:false,fullscreenControl:false
   });
   setMap(instance);
  }).catch(e=>{if(active)setError(e.message)});
  return()=>{active=false};
 },[]);
 const facade=useMemo(()=>map?createFacade(map):null,[map]);
 return <div style={{position:'relative',width:'100%',height:'100%',minHeight:style.height||250,...style}}>
  <div ref={target} style={{height:'100%',width:'100%'}}/>
  {error&&<p role="alert" style={{position:'absolute',inset:0,background:'white',padding:20}}>Google Maps unavailable: {error}</p>}
  {facade&&<Context.Provider value={facade}>{children}</Context.Provider>}
 </div>;
}
function GoogleMarker({position,children,eventHandlers,icon}){
 const map=useContext(Context);
 const popup=React.Children.toArray(children).find(c=>c?.type===GooglePopup||c?.type===Leaf.Popup);
 const markup=popup?renderToStaticMarkup(<>{popup.props.children}</>):'';
 useEffect(()=>{
  if(!map||!position)return;
  const point=coords(position);
  const image=icon?.options?.iconUrl;
  const html=icon?.options?.html;
  const info=markup?new window.google.maps.InfoWindow({content:markup}):null;
  let marker=null,overlay=null,listener=null;
  if(html){
   // Preserve the existing driver-photo and custom fleet pins.
   const Overlay=class extends window.google.maps.OverlayView{
    constructor(){super();this.element=null}
    onAdd(){
     const el=document.createElement('div');el.style.position='absolute';
     el.innerHTML=html;el.style.cursor='pointer';
     el.addEventListener('click',()=>{eventHandlers?.click?.();info?.setPosition(point);info?.open({map:map.native})});
     this.getPanes().overlayMouseTarget.appendChild(el);this.element=el;
    }
    draw(){
     if(!this.element)return;
     const p=this.getProjection().fromLatLngToDivPixel(point);
     if(!p)return;
     const anchor=icon?.options?.iconAnchor||[20,40];
     this.element.style.left=`${p.x-anchor[0]}px`;
     this.element.style.top=`${p.y-anchor[1]}px`;
    }
    onRemove(){this.element?.remove();this.element=null}
   };
   overlay=new Overlay();overlay.setMap(map.native);
  }else{
   marker=new window.google.maps.Marker({map:map.native,position:point,
    ...(image?{icon:{url:image,scaledSize:new window.google.maps.Size(25,41)}}:{})});
   listener=marker.addListener('click',()=>{eventHandlers?.click?.();info?.open({anchor:marker,map:map.native})});
  }
  return()=>{listener?.remove();info?.close();marker?.setMap(null);overlay?.setMap(null)};
 },[map,position?.[0],position?.[1],markup,eventHandlers?.click,icon]);
 return null;
}
function GooglePolyline({positions=[],pathOptions={}}){
 const map=useContext(Context);
 const path=JSON.stringify(positions);
 useEffect(()=>{
  if(!map||positions.length<2)return;
  const line=new window.google.maps.Polyline({map:map.native,path:positions.map(coords),strokeColor:pathOptions.color||'#f47a20',strokeWeight:pathOptions.weight||4,strokeOpacity:pathOptions.opacity??1});
  return()=>line.setMap(null);
 },[map,path,pathOptions.color,pathOptions.weight,pathOptions.opacity]);
 return null;
}
function GooglePopup(){return null}
function GoogleTiles(){return null}
function googleMapEvents(handlers){
 const map=useContext(Context);
 useEffect(()=>{
  if(!map)return;
  const listeners=Object.entries(handlers).map(([name,fn])=>map.native.addListener(name,e=>fn({latlng:{lat:e.latLng?.lat(),lng:e.latLng?.lng()}})));
  return()=>listeners.forEach(l=>l.remove());
 },[map,handlers?.click]);
}
export const MapContainer=GOOGLE_MAPS_ACTIVE?GoogleContainer:Leaf.MapContainer;
export const Marker=GOOGLE_MAPS_ACTIVE?GoogleMarker:Leaf.Marker;
export const Popup=GOOGLE_MAPS_ACTIVE?GooglePopup:Leaf.Popup;
export const Polyline=GOOGLE_MAPS_ACTIVE?GooglePolyline:Leaf.Polyline;
export const TileLayer=GOOGLE_MAPS_ACTIVE?GoogleTiles:Leaf.TileLayer;
export function useMap(){return GOOGLE_MAPS_ACTIVE?useContext(Context):Leaf.useMap()}
export function useMapEvents(handlers){if(GOOGLE_MAPS_ACTIVE){googleMapEvents(handlers)}else{Leaf.useMapEvents(handlers)}}
