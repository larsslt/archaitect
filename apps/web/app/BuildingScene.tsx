'use client';
import {useMemo} from 'react';

type Point={x:number;y:number};
export type SceneDesign={center_x:number;center_y:number;width_m:number;depth_m:number;rotation_deg:number;eave_height_m:number;ridge_height_m:number;roof_type:'flat'|'gable'};
export type Sun={elevation_deg:number;azimuth_deg:number;shadow_east_m:number|null;shadow_north_m:number|null;sun_above_horizon:boolean;shadow_length_m:number|null};
type P3={x:number;y:number;z:number};

// Dark palette, aligned with styles.css tokens (Meta developer dark theme).
// Amber marks the unverified demo parcel; blue marks the parametric building.
const C={
 bg:'#111112',grid:'rgba(242,244,246,.06)',
 parcelFill:'rgba(242,184,75,.07)',parcelLine:'rgba(242,184,75,.7)',
 shadow:'rgba(0,0,0,.55)',shadowSide:'rgba(0,0,0,.3)',
 wallS:'#4b5563',wallW:'#3d4551',wallN:'#343b46',wallE:'#2a3039',wallLine:'rgba(242,244,246,.22)',
 roofL:'#0a4fb4',roofR:'#0064e0',roofFlat:'#0a58c9',gable:'#2a5f9a',roofLine:'#47a5fa',
 centre:'#47a5fa',title:'#f2f4f6',text:'#9fa4ab',note:'#6f747c',north:'#9fa4ab'
};

// Metric coordinate system: x=local east, y=local north, z=height.
// Oblique projection keeps the prototype independent of an unverified cadastral CRS.
function project(p:P3):Point{return {x:380+(p.x-p.y)*8.6,y:218+(p.x+p.y)*4.3-p.z*9.4};}
function pts(items:P3[]){return items.map(p=>{const q=project(p);return `${q.x.toFixed(2)},${q.y.toFixed(2)}`;}).join(' ');}
function poly(id:string,items:P3[],fill:string,stroke:string,dash?:string){return <polygon key={id} points={pts(items)} fill={fill} stroke={stroke} strokeWidth={1.3} strokeLinejoin="round" strokeDasharray={dash}/>;}
function rectangle(cx:number,cy:number,w:number,d:number,rotation:number,z:number):P3[]{
 const a=rotation*Math.PI/180, c=Math.cos(a),s=Math.sin(a);
 return [[-w/2,-d/2],[w/2,-d/2],[w/2,d/2],[-w/2,d/2]].map(([x,y])=>({x:cx+x*c-y*s,y:cy+x*s+y*c,z}));
}
export default function BuildingScene({design,parcel,sun}:{design:SceneDesign;parcel:Point[];sun:Sun|null}){
 const shapes=useMemo(()=>{
  const ground=rectangle(design.center_x,design.center_y,design.width_m,design.depth_m,design.rotation_deg,0);
  const eaves=ground.map(p=>({...p,z:design.eave_height_m}));
  const ridgeHeight=design.roof_type==='flat'?design.eave_height_m:design.ridge_height_m;
  const midway=(a:P3,b:P3):P3=>({x:(a.x+b.x)/2,y:(a.y+b.y)/2,z:ridgeHeight});
  const ridgeA=midway(eaves[0],eaves[1]),ridgeB=midway(eaves[3],eaves[2]);
  const shifting=(p:P3)=>({...p,x:p.x+(sun?.shadow_east_m??0),y:p.y+(sun?.shadow_north_m??0),z:0});
  const shadow=ground.map(shifting);
  return {ground,eaves,ridgeA,ridgeB,shadow};
 },[design,sun]);
 const groundParcel=parcel.map(p=>({x:p.x,y:p.y,z:0}));
 const center=project({x:design.center_x,y:design.center_y,z:0});
 return <svg className="building-3d-svg" viewBox="0 0 760 440" role="img" aria-label="Parametrische dreidimensionale Gebäudeprojektion mit schematischem Sonnenschatten">
  <defs><pattern id="scene-grid" patternUnits="userSpaceOnUse" width="24" height="24"><path d="M24 0H0V24" fill="none" stroke={C.grid} strokeWidth=".8"/></pattern></defs>
  <rect width="760" height="440" fill={C.bg} rx="16"/><rect width="760" height="440" fill="url(#scene-grid)" rx="16"/>
  {poly('parcel',groundParcel,C.parcelFill,C.parcelLine,'5 4')}
  {sun?.sun_above_horizon && <>{poly('shadow',shapes.shadow,C.shadow,'none')}
   {shapes.ground.map((p,i)=>poly(`shadow-link-${i}`,[p,shapes.shadow[i],shapes.shadow[(i+1)%4],shapes.ground[(i+1)%4]],C.shadowSide,'none'))}</>}
  {poly('wall-n',[shapes.ground[3],shapes.ground[2],shapes.eaves[2],shapes.eaves[3]],C.wallN,C.wallLine)}
  {poly('wall-e',[shapes.ground[1],shapes.ground[2],shapes.eaves[2],shapes.eaves[1]],C.wallE,C.wallLine)}
  {poly('wall-s',[shapes.ground[0],shapes.ground[1],shapes.eaves[1],shapes.eaves[0]],C.wallS,C.wallLine)}
  {poly('wall-w',[shapes.ground[3],shapes.ground[0],shapes.eaves[0],shapes.eaves[3]],C.wallW,C.wallLine)}
  {design.roof_type==='gable' ? <>
    {poly('roof-left',[shapes.eaves[0],shapes.ridgeA,shapes.ridgeB,shapes.eaves[3]],C.roofL,C.roofLine)}
    {poly('roof-right',[shapes.ridgeA,shapes.eaves[1],shapes.eaves[2],shapes.ridgeB],C.roofR,C.roofLine)}
    {poly('gable',[shapes.eaves[0],shapes.eaves[1],shapes.ridgeA],C.gable,C.wallLine)}
  </> : poly('flat-roof',shapes.eaves,C.roofFlat,C.roofLine)}
  <circle cx={center.x} cy={center.y} r="3" fill={C.centre}/>
  <text x="25" y="33" fill={C.title} fontSize="13" fontWeight="500">3D MASSING · LOCAL DEMO</text>
  <text x="25" y="52" fill={C.text} fontSize="10">Nicht georeferenziert · stark vereinfachte Dach- und Schattengeometrie</text>
  <path d="M722 53 V26 m0 0 -5 9 m5 -9 5 9" stroke={C.north} strokeWidth="2" fill="none"/>
  <text x="722" y="19" textAnchor="middle" fontSize="11" fill={C.north}>N</text>
  <text x="25" y="412" fill={C.text} fontSize="11">Gebäude {design.width_m.toFixed(1)} × {design.depth_m.toFixed(1)} m</text>
  <text x="25" y="428" fill={C.note} fontSize="10">Sonnen-/Schattenmodell nur illustrativ, kein Verschattungsgutachten</text>
 </svg>;
}
