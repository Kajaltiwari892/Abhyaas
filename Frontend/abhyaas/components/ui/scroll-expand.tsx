"use client";

import { useCallback, useEffect, useLayoutEffect, useRef } from "react";
import type { CSSProperties, ReactNode } from "react";

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);
const smoothstep = (edge0: number, edge1: number, value: number) => {
  const t = clamp((value - edge0) / (edge1 - edge0 || 1e-6), 0, 1);
  return t * t * (3 - 2 * t);
};

export interface ScrollExpandProps {
  src: string;
  mediaType?: "image" | "video";
  poster?: string;
  alt?: string;
  title?: ReactNode;
  scrollHint?: string;
  startWidth?: number;
  startHeight?: number;
  startRadius?: number;
  endRadius?: number;
  mediaZoom?: number;
  scrollDistance?: number;
  holdDistance?: number;
  smoothing?: number;
  overlayScrim?: number;
  useWindowScroll?: boolean;
  enabled?: boolean;
  children?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export default function ScrollExpand({
  src,
  mediaType = "image",
  poster = "",
  alt = "",
  title,
  scrollHint = "",
  startWidth = 48,
  startHeight = 58,
  startRadius = 24,
  endRadius = 0,
  mediaZoom = 1.22,
  scrollDistance = 1.05,
  holdDistance = 0.25,
  smoothing = 0.1,
  overlayScrim = 0.58,
  useWindowScroll = false,
  enabled = true,
  children,
  className = "",
  style,
}: ScrollExpandProps) {
  const initialTrackHeight = useWindowScroll
    ? `${(1 + Math.max(0, scrollDistance) + Math.max(0, holdDistance)) * 100}vh`
    : "100%";
  const initialStageHeight = useWindowScroll ? "100vh" : "100%";
  const rootRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const mediaRef = useRef<HTMLImageElement | HTMLVideoElement>(null);
  const titleRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLDivElement>(null);
  const scrimRef = useRef<HTMLDivElement>(null);
  const hintRef = useRef<HTMLDivElement>(null);
  const configRef = useRef({ startWidth, startHeight, startRadius, endRadius, mediaZoom, scrollDistance, holdDistance, smoothing, overlayScrim, useWindowScroll, enabled });

  useEffect(() => {
    configRef.current = { startWidth, startHeight, startRadius, endRadius, mediaZoom, scrollDistance, holdDistance, smoothing, overlayScrim, useWindowScroll, enabled };
  }, [startWidth, startHeight, startRadius, endRadius, mediaZoom, scrollDistance, holdDistance, smoothing, overlayScrim, useWindowScroll, enabled]);

  const applyProgress = useCallback((progress: number) => {
    const frame = frameRef.current;
    const media = mediaRef.current;
    if (!frame || !media) return;
    const config = configRef.current;
    const eased = smoothstep(0, 1, progress);
    const mobile = (rootRef.current?.clientWidth ?? 0) < 640;
    const initialWidth = mobile ? Math.max(config.startWidth, 78) : config.startWidth;
    const initialHeight = mobile ? Math.max(config.startHeight, 50) : config.startHeight;
    const width = initialWidth + (100 - initialWidth) * eased;
    const height = initialHeight + (100 - initialHeight) * eased;
    const insetX = Math.max(0, (100 - width) / 2);
    const insetY = Math.max(0, (100 - height) / 2);
    const radius = config.startRadius + (config.endRadius - config.startRadius) * eased;
    frame.style.clipPath = `inset(${insetY}% ${insetX}% ${insetY}% ${insetX}% round ${radius}px)`;
    media.style.transform = `scale(${config.mediaZoom + (1 - config.mediaZoom) * eased})`;
    if (scrimRef.current) {
      const dim = smoothstep(0, 0.48, progress);
      scrimRef.current.style.opacity = `${config.overlayScrim * dim}`;
    }
    if (titleRef.current) {
      const exit = smoothstep(0.38, 0.82, progress);
      titleRef.current.style.opacity = `${1 - exit}`;
      titleRef.current.style.transform = `translate3d(0, ${-24 * exit}px, 0) scale(${1 + 0.045 * exit})`;
    }
    if (hintRef.current) {
      const exit = smoothstep(0, 0.13, progress);
      hintRef.current.style.opacity = `${1 - exit}`;
      hintRef.current.style.transform = `translate3d(0, ${8 * exit}px, 0)`;
    }
    if (overlayRef.current) {
      const enter = smoothstep(0.66, 1, progress);
      overlayRef.current.style.opacity = `${enter}`;
      overlayRef.current.style.transform = `translate3d(0, ${20 * (1 - enter)}px, 0)`;
    }
  }, []);

  useLayoutEffect(() => {
    const root = rootRef.current;
    const track = trackRef.current;
    const stage = stageRef.current;
    if (!root || !track || !stage) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let frameId = 0;
    let current = 0;
    let target = 0;
    let stageHeight = 0;
    let running = false;

    const measure = () => {
      const config = configRef.current;
      stageHeight = config.useWindowScroll ? window.innerHeight : root.clientHeight;
      if (stageHeight <= 0) return;
      stage.style.height = `${stageHeight}px`;
      track.style.height = `${stageHeight * (1 + Math.max(0, config.scrollDistance) + Math.max(0, config.holdDistance))}px`;
      const width = root.clientWidth || stageHeight;
      stage.style.setProperty("--se-title-size", `${clamp(width * 0.066, 30, 78)}px`);
    };
    const readProgress = () => {
      const config = configRef.current;
      if (!config.enabled) return 1;
      const span = stageHeight * Math.max(0.01, config.scrollDistance);
      if (config.useWindowScroll) return clamp(-track.getBoundingClientRect().top / span, 0, 1);
      return clamp(root.scrollTop / span, 0, 1);
    };
    const tick = () => {
      const config = configRef.current;
      const amount = config.smoothing <= 0 ? 1 : 1 - Math.exp(-1 / (60 * config.smoothing));
      current += (target - current) * amount;
      if (Math.abs(target - current) < 0.0004) { current = target; running = false; }
      applyProgress(current);
      frameId = running ? requestAnimationFrame(tick) : 0;
    };
    const onScroll = () => {
      target = readProgress();
      if (configRef.current.smoothing <= 0 || reduceMotion) { current = target; applyProgress(current); return; }
      if (!running) { running = true; frameId = requestAnimationFrame(tick); }
    };
    const onResize = () => { measure(); target = readProgress(); current = target; applyProgress(current); };

    measure(); target = readProgress(); current = target; applyProgress(current);
    const scroller: Window | HTMLDivElement = useWindowScroll ? window : root;
    scroller.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onResize);
    const resizeObserver = new ResizeObserver(onResize);
    resizeObserver.observe(root);
    return () => {
      if (frameId) cancelAnimationFrame(frameId);
      scroller.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onResize);
      resizeObserver.disconnect();
    };
  }, [applyProgress, useWindowScroll]);

  return (
    <div ref={rootRef} className={`scroll-expand-root relative w-full ${useWindowScroll ? "" : "h-full overflow-y-auto overflow-x-hidden overscroll-contain"} ${className}`} style={style}>
      <div ref={trackRef} className="relative w-full" style={{ height: initialTrackHeight }}>
        <div ref={stageRef} className="scroll-expand-stage sticky top-0 w-full overflow-hidden [--se-title-size:4rem]" style={{ height: initialStageHeight }}>
          <div ref={frameRef} className="absolute inset-0 [will-change:clip-path]">
            {mediaType === "video" ? (
              <video ref={mediaRef as React.RefObject<HTMLVideoElement>} className="absolute inset-0 h-full w-full origin-center select-none object-cover [will-change:transform]" src={src} poster={poster} autoPlay muted loop playsInline />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img ref={mediaRef as React.RefObject<HTMLImageElement>} className="absolute inset-0 h-full w-full origin-center select-none object-cover [will-change:transform]" src={src} alt={alt} draggable={false} />
            )}
            <div ref={scrimRef} className="scroll-expand-scrim pointer-events-none absolute inset-0 opacity-0" />
            {title ? <div ref={titleRef} className="scroll-expand-title pointer-events-auto absolute inset-0 z-10 flex items-center justify-center px-[8%] text-center [font-size:var(--se-title-size)] [will-change:opacity,transform]">{title}</div> : null}
            {children ? <div ref={overlayRef} className="absolute inset-0 z-10 flex flex-col items-center justify-center p-[6%] text-center opacity-0 [will-change:opacity,transform]">{children}</div> : null}
          </div>
          {scrollHint ? <div ref={hintRef} className="scroll-expand-hint pointer-events-none absolute inset-x-0 top-[78%] z-10 px-4 text-center [will-change:opacity,transform]"><span>{scrollHint}</span><i aria-hidden="true" /></div> : null}
        </div>
      </div>
    </div>
  );
}
