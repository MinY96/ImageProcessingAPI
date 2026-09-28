import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';

export type PixelRoi = { x: number; y: number; width: number; height: number };
export type ImagePixel = { x: number; y: number; channels: number[] };

type ImageCanvasProps = {
  src: string;
  alt?: string;
  roi?: PixelRoi | null;
  onRoiChange?: (roi: PixelRoi, size: { width: number; height: number }) => void;
  onImageSize?: (size: { width: number; height: number }) => void;
  className?: string;
  maxHeight?: number;
};

export function ImageCanvas({ src, alt = 'Image canvas', roi, onRoiChange, onImageSize, className = '', maxHeight }: ImageCanvasProps) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const samplerRef = useRef<HTMLCanvasElement | null>(null);
  const stageRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);
  const [pixel, setPixel] = useState<ImagePixel | null>(null);
  const [drag, setDrag] = useState<{ x: number; y: number; currentX: number; currentY: number } | null>(null);
  const [dragRoi, setDragRoi] = useState<PixelRoi | null>(null);

  useEffect(() => { setSize(null); setPixel(null); setDrag(null); setDragRoi(null); }, [src]);

  const pointAt = (event: ReactPointerEvent<HTMLDivElement>, clamp: boolean) => {
    const image = imageRef.current;
    if (!image || !size) return null;
    const rect = image.getBoundingClientRect();
    if (!clamp && (event.clientX < rect.left || event.clientY < rect.top || event.clientX > rect.right || event.clientY > rect.bottom)) return null;
    const nx = Math.min(0.999999, Math.max(0, (event.clientX - rect.left) / rect.width));
    const ny = Math.min(0.999999, Math.max(0, (event.clientY - rect.top) / rect.height));
    return { nx, ny, x: Math.floor(nx * size.width), y: Math.floor(ny * size.height), rect, stage: stageRef.current?.getBoundingClientRect() };
  };

  const samplePixel = (x: number, y: number) => {
    const image = imageRef.current;
    const canvas = samplerRef.current;
    const context = canvas?.getContext('2d', { willReadFrequently: true });
    if (!image || !context) return;
    try {
      context.drawImage(image, x, y, 1, 1, 0, 0, 1, 1);
      const data = context.getImageData(0, 0, 1, 1).data;
      setPixel({ x, y, channels: Array.from(data) });
    } catch { setPixel({ x, y, channels: [] }); }
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!onRoiChange || !size) return;
    const point = pointAt(event, false);
    if (!point) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({ x: point.nx, y: point.ny, currentX: point.nx, currentY: point.ny });
    setDragRoi(null);
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const point = pointAt(event, Boolean(drag));
    if (!point) { if (!drag) setPixel(null); return; }
    samplePixel(point.x, point.y);
    if (drag) {
      setDrag({ ...drag, currentX: point.nx, currentY: point.ny });
      const left = Math.min(drag.x, point.nx); const top = Math.min(drag.y, point.ny);
      setDragRoi({ x: Math.floor(left * size!.width), y: Math.floor(top * size!.height), width: Math.max(1, Math.round(Math.abs(point.nx - drag.x) * size!.width)), height: Math.max(1, Math.round(Math.abs(point.ny - drag.y) * size!.height)) });
    }
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag || !size || !onRoiChange) return;
    const point = pointAt(event, true);
    if (!point) { setDrag(null); return; }
    const x = Math.min(drag.x, point.nx); const y = Math.min(drag.y, point.ny);
    const width = Math.abs(point.nx - drag.x); const height = Math.abs(point.ny - drag.y);
    if (width > 0.002 && height > 0.002) onRoiChange({ x: Math.floor(x * size.width), y: Math.floor(y * size.height), width: Math.max(1, Math.round(width * size.width)), height: Math.max(1, Math.round(height * size.height)) }, size);
    setDrag(null); setDragRoi(null);
  };

  const displayRoi = dragRoi ?? roi;
  const imageRect = imageRef.current?.getBoundingClientRect();
  const stageRect = stageRef.current?.getBoundingClientRect();
  const overlay = displayRoi && size && imageRect && stageRect ? {
    left: imageRect.left - stageRect.left + displayRoi.x / size.width * imageRect.width,
    top: imageRect.top - stageRect.top + displayRoi.y / size.height * imageRect.height,
    width: displayRoi.width / size.width * imageRect.width,
    height: displayRoi.height / size.height * imageRect.height,
  } : null;

  return <div ref={stageRef} className={`image-canvas-stage ${onRoiChange ? 'selecting' : ''} ${className}`} style={maxHeight ? { maxHeight } : undefined} onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={() => { setDrag(null); setDragRoi(null); }} onPointerLeave={() => { if (!drag) setPixel(null); }}>
    <img ref={imageRef} className="image-canvas-image" src={src} alt={alt} draggable={false} onLoad={(event) => { const natural = { width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight }; setSize(natural); onImageSize?.(natural); }}/>
    {overlay && <div className={`image-canvas-roi ${drag ? 'dragging' : ''}`} style={overlay}/>}
    {pixel && <div className="image-canvas-readout" aria-live="polite">x {pixel.x} · y {pixel.y} · {pixel.channels.length ? `RGBA(${pixel.channels.join(', ')})` : 'pixel unavailable'}</div>}
    {onRoiChange && <div className="image-canvas-hint">드래그하여 ROI 지정 · 좌표와 픽셀값은 커서 위치에 표시됩니다</div>}
    <canvas ref={samplerRef} width={1} height={1} className="image-canvas-sampler" aria-hidden="true"/>
  </div>;
}
