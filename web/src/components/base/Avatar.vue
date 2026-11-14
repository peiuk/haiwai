<script setup lang="ts">
// Avatar：首字色块头像，对齐 MASTER §5.1 与原型 6 色调色板（uks-av-a~f）。
// - 人（kind="person"）用圆形 + 6 色调色板；频道（kind="channel"）用 12px 圆角 + 中性底。
// - tone 支持 "a"~"f"；缺省时由 name 确定性哈希派生，保证同一用户/频道颜色稳定。
import { computed } from "vue";

const TONES = ["a", "b", "c", "d", "e", "f"] as const;

const props = withDefaults(
  defineProps<{
    name: string;
    size?: 38 | 40 | 42 | 44 | 56;
    kind?: "person" | "channel";
    tone?: string;
  }>(),
  {
    size: 42,
    kind: "person",
    tone: "",
  },
);

function hashTone(value: string): string {
  let h = 0;
  for (let i = 0; i < value.length; i += 1) {
    h = (h * 31 + value.charCodeAt(i)) >>> 0;
  }
  return TONES[h % TONES.length];
}

const resolvedTone = computed(() => {
  if (TONES.includes(props.tone as (typeof TONES)[number])) return props.tone;
  return hashTone(props.name);
});

// 字号随尺寸缩放：38→14，40→15，42→15，44→16，56→22（对齐原型 me-card 头像 22px）
const fontSize = computed(() => {
  const map: Record<number, number> = { 38: 14, 40: 15, 42: 15, 44: 16, 56: 22 };
  return map[props.size] ?? 15;
});
</script>

<template>
  <span
    class="avatar"
    :class="[`uks-av-${resolvedTone}`, kind === 'channel' ? 'avatar--channel' : '']"
    :style="{ width: `${size}px`, height: `${size}px`, fontSize: `${fontSize}px` }"
    aria-hidden="true"
  >
    {{ name.trim().charAt(0) || "·" }}
  </span>
</template>

<style scoped>
.avatar {
  display: grid;
  place-items: center;
  border-radius: 50%;
  font-weight: var(--fw-bold);
  flex-shrink: 0;
}
/* 频道头像：12px 圆角；颜色仍走 6 色调（确定性派生），与原型频道彩色头像一致 */
.avatar--channel {
  border-radius: 12px;
}

/* 6 色调色板（对齐原型 uks-av-a~f） */
.uks-av-a { background: var(--accent-strong); color: var(--on-accent); }
.uks-av-b { background: var(--good-solid); color: var(--on-good); }
.uks-av-c { background: var(--warn); color: var(--bg); }
.uks-av-d { background: var(--danger); color: var(--bg); }
.uks-av-e { background: var(--media-ph-b); color: var(--on-media); }
.uks-av-f { background: var(--media-ph-c); color: var(--on-media); }
</style>
