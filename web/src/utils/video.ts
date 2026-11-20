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

// 任何视频开始放（包括详情页、大图里用户自己点的），页面上其他视频都停，避免两个一起响。play 不冒泡，用捕获。
document.addEventListener(
  "play",
  (e) => {
    document.querySelectorAll("video").forEach((v) => v !== e.target && v.pause());
    if (current && current !== e.target) current.pause(); // 缓存起来的首页已不在页面里，querySelectorAll 找不到它
  },
  true,
);

/** 打开详情等盖在信息流上面的页面时调用：下面的视频还算「看得见」，不手动停会一直放。 */
export function pauseAllVideos(): void {
  document.querySelectorAll("video").forEach((v) => v.pause());
  current?.pause();
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
