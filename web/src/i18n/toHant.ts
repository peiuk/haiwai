// 简 → 繁转换：与共享层 UKCN.toHant 同一算法（二字词组优先，其余按单字表逐字映射）。
// 只用于界面文案；用户发布的内容（data-ugc）不参与转换。
import { HANT_C, HANT_P } from "./hantTable";

const charMap = new Map<string, string>();
const phraseMap = new Map<string, string>();

const chars = Array.from(HANT_C);
for (let i = 0; i + 1 < chars.length; i += 2) {
  charMap.set(chars[i], chars[i + 1]);
}
for (const pair of HANT_P.split("|")) {
  if (pair.length === 4) phraseMap.set(pair.slice(0, 2), pair.slice(2));
}

export function toHant(value: unknown): string {
  const text = value == null ? "" : String(value);
  let out = "";
  for (let i = 0; i < text.length; i++) {
    const two = text.slice(i, i + 2);
    const phrase = two.length === 2 ? phraseMap.get(two) : undefined;
    if (phrase) {
      out += phrase;
      i += 1;
      continue;
    }
    out += charMap.get(text[i]) ?? text[i];
  }
  return out;
}
