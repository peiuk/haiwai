// 短文字帖的彩色背景（Facebook 式）。名字要和后端 contents.BG_STYLES 一致。
// 颜色固定写死、不跟主题变：浅色 / 深色模式下都是同一块彩色，字色按底色深浅选白或黑。
export const BG_MAX_LEN = 130;

export type BgPreset = { key: string; label: string; background: string; ink: string };

export const BG_PRESETS: BgPreset[] = [
  { key: "red", label: "红色", background: "#c8102e", ink: "#fff" },
  { key: "purple", label: "紫色", background: "linear-gradient(135deg, #5b1fd1, #a12fd8)", ink: "#fff" },
  { key: "blue", label: "蓝色", background: "linear-gradient(135deg, #0a4fd8, #1f7fe8)", ink: "#fff" },
  { key: "sunset", label: "晚霞", background: "linear-gradient(135deg, #e0305a, #e2580b)", ink: "#fff" },
  { key: "pink", label: "粉色", background: "linear-gradient(135deg, #c21a8a, #e8445a)", ink: "#fff" },
  { key: "green", label: "绿色", background: "linear-gradient(135deg, #0b7a3e, #0f8f86)", ink: "#fff" },
  { key: "dark", label: "黑色", background: "#1c1e21", ink: "#fff" },
  { key: "yellow", label: "黄色", background: "linear-gradient(135deg, #ffe259, #ffa751)", ink: "#1c1e21" },
];

const BY_KEY = new Map(BG_PRESETS.map((preset) => [preset.key, preset]));

/** 背景块的内联样式；不认识的名字（老数据 / 以后删掉的颜色）返回 null，按普通帖显示。 */
export function bgStyleOf(key: string | null | undefined): { background: string; color: string } | null {
  const preset = key ? BY_KEY.get(key) : undefined;
  return preset ? { background: preset.background, color: preset.ink } : null;
}

/** 这段文字还能不能放在背景上：有字、不超长、不带图和视频。 */
export function bgFits(text: string, hasMedia: boolean): boolean {
  const length = text.trim().length;
  return length > 0 && length <= BG_MAX_LEN && !hasMedia;
}
