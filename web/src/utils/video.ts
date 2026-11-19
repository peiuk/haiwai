// 信息流视频带声音自动播放，同一时间只放一个（新的开始放，上一个暂停）。
// 浏览器规定：用户还没点过页面时不许有声自动播放。被拦下就先静音播，
// 等用户第一次点页面就把声音打开；点在正在播的视频上只开声音、不暂停。
const waiting = new Set<HTMLVideoElement>();
let current: HTMLVideoElement | null = null;

function unmuteWaiting(e: Event): void {
  for (const v of waiting) {
    v.muted = false;
    if (e.target === v && !v.paused) e.stopPropagation();
  }
  waiting.clear();
}

export function playWithSound(v: HTMLVideoElement): Promise<void> {
  if (current && current !== v) current.pause();
  current = v;
  v.muted = false;
  return v.play().catch((err: unknown) => {
    // 只有「不许有声播放」才退回静音；被 pause() 打断之类的不重试，免得滑走后又播起来
    if (!(err instanceof DOMException && err.name === "NotAllowedError")) throw err;
    v.muted = true;
    waiting.add(v);
    document.addEventListener("click", unmuteWaiting, { capture: true, once: true });
    return v.play();
  });
}
