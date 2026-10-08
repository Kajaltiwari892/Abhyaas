import * as THREE from "three";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { autonomousAction, companionPose, type CompanionAction } from "./companion-motion";

export type CompanionMood = "hello" | "thinking" | "happy" | "idle" | "retry";

/** A procedural model: no downloaded images, trackers, model files or render service. */
export function createCompanionScene(host: HTMLElement, initialMood: CompanionMood, variant: "robot" | "commando" = "robot") {
  const commando = variant === "commando";
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, .1, 30);
  camera.position.set(0, .30, 6.25);
  camera.lookAt(0, .30, 0);
  scene.add(new THREE.HemisphereLight(0xf7f8df, 0x405039, 2.7));
  const key = new THREE.DirectionalLight(0xfff3da, 3.3);
  key.position.set(-3, 4, 6); scene.add(key);
  const rim = new THREE.DirectionalLight(0xb8d27c, 2);
  rim.position.set(3, 1, -2); scene.add(rim);
  const shell = new THREE.MeshStandardMaterial({ color: commando ? 0x3d4b36 : 0xe6e6d5, roughness: .28, metalness: .18 });
  const olive = new THREE.MeshStandardMaterial({ color: 0x87974d, roughness: .32, metalness: .3 });
  const gold = new THREE.MeshStandardMaterial({ color: 0xc6b46d, roughness: .3, metalness: .5 });
  const glass = new THREE.MeshStandardMaterial({ color: 0x101d17, roughness: .18, metalness: .32 });
  const glow = new THREE.MeshBasicMaterial({ color: 0xd6ee98 });
  const paperMaterial = new THREE.MeshStandardMaterial({ color: 0xfff3cd, roughness: .9 });
  const ink = new THREE.MeshBasicMaterial({ color: 0x657644 });
  const robot = new THREE.Group(); scene.add(robot);
  const mesh = (geometry: THREE.BufferGeometry, material: THREE.Material, parent: THREE.Object3D, x=0, y=0, z=0) => {
    const object = new THREE.Mesh(geometry, material); object.position.set(x, y, z); parent.add(object); return object;
  };
  const rounded = (w:number,h:number,d:number,r:number,material:THREE.Material,parent:THREE.Object3D,x=0,y=0,z=0) =>
    mesh(new RoundedBoxGeometry(w,h,d,3,r), material, parent,x,y,z);
  const head = new THREE.Group(); head.position.y = .62; robot.add(head);
  rounded(1.82,1.30,.98,.30,shell,head);
  rounded(1.52,.91,.15,.22,glass,head,0,-.015,.50);
  const eyes = new THREE.Group(); eyes.position.set(0,.06,.60); head.add(eyes);
  for (const x of [-.35,.35]) {
    const curve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(x-.16,-.015,0),new THREE.Vector3(x,.27,0),new THREE.Vector3(x+.16,-.015,0));
    mesh(new THREE.TubeGeometry(curve,16,.035,6,false),glow,eyes);
    mesh(new THREE.SphereGeometry(.045,10,8),gold,head,x*.9,-.20,.60).scale.set(1.5,.5,.4);
  }
  const smileCurve = new THREE.QuadraticBezierCurve3(new THREE.Vector3(-.17,-.20,.605),new THREE.Vector3(0,-.36,.62),new THREE.Vector3(.17,-.20,.605));
  const smile = mesh(new THREE.TubeGeometry(smileCurve,16,.022,6,false),glow,head);
  for (const x of [-.95,.95]) {
    mesh(new THREE.SphereGeometry(.19,16,12),olive,head,x,0,0).scale.set(.7,1,1);
  }
  mesh(new THREE.CylinderGeometry(.024,.03,.23,8),gold,head,0,.76,0);
  const antenna = mesh(new THREE.SphereGeometry(.095,16,12),glow,head,0,.91,0);
  if (commando) {
    // Original low-poly tactical companion, not a textured copy of a photograph.
    mesh(new THREE.SphereGeometry(.94,24,16,0,Math.PI*2,0,Math.PI/2),olive,head,0,.33,-.04).scale.set(1,.57,.64);
    rounded(.48,.24,.20,.055,glass,head,0,.54,.52);
    rounded(.24,.18,.13,.035,gold,head,0,.54,.64);
    for (const side of [-1,1]) {
      rounded(.25,.48,.48,.10,glass,head,side*.99,-.02,0);
      rounded(.20,.33,.32,.06,olive,head,side*1.04,-.02,.04);
    }
    rounded(.65,.22,.07,.06,olive,head,0,-.42,.50);
    antenna.visible = false;
  }
  const body = mesh(new THREE.SphereGeometry(.62,24,20),shell,robot,0,-.55,0);
  body.scale.set(1,1.04,.74);
  rounded(.90,.45,.65,.19,olive,robot,0,-.33,.04);
  mesh(new THREE.CylinderGeometry(.16,.16,.04,24),gold,robot,0,-.38,.41).rotation.x=Math.PI/2;
  mesh(new THREE.SphereGeometry(.11,16,12),glow,robot,0,-.38,.44).scale.z=.25;
  if (commando) {
    rounded(.92,.57,.24,.09,olive,robot,0,-.62,.33);
    for (const x of [-.27,.27]) rounded(.23,.32,.12,.04,gold,robot,x,-.63,.49);
    rounded(.49,.07,.04,.015,shell,robot,0,-.86,.47);
  }
  const arms: THREE.Group[]=[];
  for (const side of [-1,1]) {
    const arm = new THREE.Group(); arm.position.set(side*.74,-.32,0); robot.add(arm); arms.push(arm);
    mesh(new THREE.SphereGeometry(.20,16,12),olive,arm);
    mesh(new THREE.CapsuleGeometry(.14,.38,4,12),shell,arm,0,-.27,0);
    mesh(new THREE.SphereGeometry(.155,14,10),gold,arm,0,-.52,0);
    rounded(.29,.20,.35,.095,olive,robot,side*.28,-1.16,.03);
  }
  // An actual open book, with two covers, stacked pages and a hinged turning page.
  const book = new THREE.Group(); book.position.set(0,-.42,.78); book.rotation.x=-.24; robot.add(book);
  for (const side of [-1,1]) {
    const half = new THREE.Group(); half.rotation.y=side*.23; book.add(half);
    rounded(.59,.58,.055,.025,olive,half,side*.295,0,-.025);
    rounded(.54,.52,.05,.015,paperMaterial,half,side*.285,.005,.027);
    for (let line=0;line<5;line++) {
      rounded(line===4?.26:.39,.012,.006,.003,ink,half,side*.285,.17-line*.078,.058);
    }
  }
  const turningPage=new THREE.Group(); book.add(turningPage);
  rounded(.54,.50,.012,.008,paperMaterial,turningPage,.27,0,.067);
  const shadow = mesh(new THREE.CircleGeometry(1,32),new THREE.MeshBasicMaterial({color:0x758644,transparent:true,opacity:.11,depthWrite:false}),scene,0,-1.47,-.1);
  shadow.scale.set(.91,.105,1);
  let mood=initialMood, disposed=false, frame=0, lastPaint=0, visible=true;
  let action: CompanionAction = initialMood==="thinking"?"read":initialMood==="happy"?"jump":"wave";
  let activeTime=0, lastTick=0;
  let actionStarted=0, actionUntil=initialMood==="happy"?1800:0;
  const motion=window.matchMedia("(prefers-reduced-motion: reduce)");
  const pointer={x:0,y:0};
  const render=(now:number) => {
    frame=0;
    if(disposed || !visible || document.hidden) return;
    // Use elapsed seconds, not frame counts: a throttled laptop must not turn a
    // six-second pause into a minute. Hidden/offscreen transitions reset lastTick.
    if(lastTick) activeTime+=Math.max(0,now-lastTick);
    lastTick=now;
    if(now-lastPaint>32 || motion.matches) {
      lastPaint=now;
      const t=activeTime/1000, still=motion.matches;
      const automatic=autonomousAction(t,still);
      const override=activeTime<actionUntil || mood==="thinking";
      const active=override?(mood==="thinking"?"read":action):automatic.action;
      const elapsed=override?(activeTime-actionStarted)/1000:automatic.elapsed;
      const pose=companionPose(elapsed,active,still);
      host.dataset.action=active;
      const reading=pose.reading;
      robot.position.y=(still?0:Math.sin(t*1.8)*.035)+pose.lift;
      robot.scale.y=pose.squash;
      robot.rotation.y=still?-.20:-.20+Math.sin(t*.65)*.10+pointer.x*.18;
      robot.rotation.z=still?0:Math.sin(t*1.2)*.025;
      head.rotation.z=reading?-.06:still?0:Math.sin(t*.9)*.035;
      head.rotation.x=reading?.20:pointer.y*.08;
      head.rotation.y=reading&&!still?Math.sin(t*1.5)*.10:0;
      eyes.scale.y=pose.blink*(reading?.78:1);
      smile.scale.y=reading?.65:mood==="happy"?1.25:mood==="retry"?.6:1;
      arms[0].rotation.z=active==="wave"?pose.wave:reading?.9:active==="jump"?-1.4:-.3;
      arms[1].rotation.z=reading?-.9:active==="jump"?1.4:.35+(still?0:Math.sin(t*1.8)*.08);
      arms.forEach(arm=>{arm.rotation.x=reading?-1.05:0;});
      book.visible=reading;
      turningPage.rotation.y=-pose.turnPage;
      antenna.scale.setScalar(reading&&!still?1+Math.sin(t*4)*.15:1);
      shadow.scale.x=.92-pose.lift*.5;
      shadow.material.opacity=.11-pose.lift*.09;
      renderer.render(scene,camera);
    }
    if(!motion.matches) frame=requestAnimationFrame(render);
  };
  const resume=() => { if(!frame && !disposed) frame=requestAnimationFrame(render); };
  const resize=new ResizeObserver(() => {
    const {width,height}=host.getBoundingClientRect(); if(!width||!height)return;
    renderer.setSize(width,height,false); camera.aspect=width/height; camera.updateProjectionMatrix(); resume();
  }); resize.observe(host);
  const observe=new IntersectionObserver(([entry])=>{visible=entry.isIntersecting;if(visible)resume();else{cancelAnimationFrame(frame);frame=0;lastTick=0;}}); observe.observe(host);
  const visibility=()=>{if(document.hidden){cancelAnimationFrame(frame);frame=0;lastTick=0;}else resume();};
  const motionChanged=()=>{lastTick=0;resume();};
  document.addEventListener("visibilitychange",visibility); motion.addEventListener("change",motionChanged);
  resume();
  return {
    setMood(next:CompanionMood){
      if(mood!==next){
        mood=next;actionStarted=activeTime;
        action=next==="thinking"?"read":next==="happy"?"jump":"wave";
        actionUntil=actionStarted+(next==="thinking"?8000:next==="happy"?1800:2400);
      }
      resume();
    },
    act(next:CompanionAction){action=next;actionStarted=activeTime;actionUntil=actionStarted+(next==="read"?8000:next==="jump"?1800:2800);resume();},
    look(x:number,y:number){pointer.x=x;pointer.y=y;resume();},
    dispose(){
      disposed=true;cancelAnimationFrame(frame);resize.disconnect();observe.disconnect();
      document.removeEventListener("visibilitychange",visibility);motion.removeEventListener("change",motionChanged);
      scene.traverse(object=>{if(object instanceof THREE.Mesh){object.geometry.dispose();}});
      [shell,olive,gold,glass,glow,paperMaterial,ink,shadow.material].forEach(material=>material.dispose());
      renderer.dispose();renderer.forceContextLoss();renderer.domElement.remove();
    },
  };
}
