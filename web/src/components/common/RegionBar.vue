<script setup lang="ts">
// 首页「当前国家」区域栏：接通 GET/POST /api/v1/me/regions。
// 自动定位：用浏览器语言 + 时区推断国家；命中已开通国家则用之，否则回落 GLOBAL（国际频道）。
// 已开通国家列表由后端下发（open_regions），前端不硬编码。
import { computed, onMounted, ref, watch } from "vue";
import { detectCountryCode, GUEST_REGION_KEY } from "../../utils/region";
import { jsonBody, request, type OpenRegion, type RegionPref } from "../../api";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import BaseIcon from "../base/BaseIcon.vue";

const auth = useAuthStore();
const toast = useToastStore();
const emit = defineEmits<{ (e: "changed", code: string): void }>();

// 游客自动定位记忆 key
const LOCAL_KEY = GUEST_REGION_KEY;

// 兜底已开通国家列表（游客/未拿到后端时用；登录后以后端 open_regions 为准）
const DEFAULT_OPEN_REGIONS: OpenRegion[] = [
  { code: "UK", name: "英国", city: "伦敦" },
  { code: "GLOBAL", name: "国际", city: "" },
];

const pref = ref<RegionPref | null>(null);
const busy = ref(false);
const openPicker = ref(false);

// 后端下发的已开通国家列表（fallback：内置 UK+GLOBAL）
const openRegions = computed<OpenRegion[]>(() => {
  const list = pref.value?.open_regions;
  if (list && list.length) return list;
  return DEFAULT_OPEN_REGIONS;
});

const regionLabel = computed(() => {
  const code = pref.value?.region_code ?? "GLOBAL";
  return openRegions.value.find((r) => r.code === code)?.name ?? code ?? "未定位";
});
const isGlobal = computed(() => (pref.value?.region_code ?? "GLOBAL") === "GLOBAL");
const isRoaming = computed(() => pref.value?.roaming === true);


// 定位结果映射到已开通国家；没开通（或判断不出来）默认英国，英国也没开才看国际。和后端 effective_region 同一规则。
function resolveRegion(detected: string | null): string {
  if (detected && openRegions.value.some((r) => r.code === detected)) return detected;
  return openRegions.value.some((r) => r.code === "UK") ? "UK" : "GLOBAL";
}

// 第一次自动定位时告诉用户定位到哪了（之后记住了，不再提示）
function announce(detected: string | null, code: string): void {
  const name = openRegions.value.find((r) => r.code === code)?.name ?? code;
  toast.show(
    detected && detected !== code
      ? `你所在的国家还没开通，先为你显示${name}。可点右边「切换」修改`
      : `已根据你的位置定位到${name}。不对的话可点右边「切换」修改`,
  );
}

async function load(): Promise<void> {
  if (!auth.isLoggedIn) {
    // 游客：优先 localStorage 记忆，否则自动定位
    // 首页等这个事件才渲染信息流，存储被禁用时也必须发出去
    let saved: string | null = null;
    try { saved = localStorage.getItem(LOCAL_KEY); } catch { /* 存储不可用 */ }
    if (saved && openRegions.value.some((r) => r.code === saved)) {
      pref.value = { region_code: saved, source: "local", locked: false, roaming: false };
      emit("changed", saved);
      return;
    }
    const detected = detectCountryCode();
    const code = resolveRegion(detected);
    pref.value = { region_code: code, source: "auto", locked: false, roaming: false };
    try { localStorage.setItem(LOCAL_KEY, code); } catch { /* 存储不可用 */ }
    emit("changed", code);
    announce(detected, code);
    return;
  }
  try {
    pref.value = await request<RegionPref>("/api/v1/me/regions");
    // 登录用户若尚未设置（region_code 默认 GLOBAL 且 source=default），做一次自动定位兜底
    if (pref.value.region_code === "GLOBAL" && pref.value.source === "default") {
      const detected = detectCountryCode();
      const code = resolveRegion(detected);
      if (code !== "GLOBAL") {
        // 写进账号，下次不再定位
        pref.value = await request<RegionPref>(
          "/api/v1/me/regions",
          jsonBody({ region_code: code, source: "auto" }),
        );
        announce(detected, code);
      }
    }
    emit("changed", pref.value.region_code);
  } catch {
    const code = resolveRegion(detectCountryCode());
    pref.value = { region_code: code, source: "auto", locked: false, roaming: false };
    emit("changed", code);
  }
}

async function setRegion(code: string): Promise<void> {
  if (!auth.isLoggedIn) {
    // 游客：切换即写入 localStorage
    pref.value = { region_code: code, source: "local", locked: false, roaming: false };
    localStorage.setItem(LOCAL_KEY, code);
    openPicker.value = false;
    emit("changed", code);
    toast.show(`已切换到${openRegions.value.find((r) => r.code === code)?.name ?? code}`);
    return;
  }
  busy.value = true;
  try {
    pref.value = await request<RegionPref>(
      "/api/v1/me/regions",
      jsonBody({ region_code: code, source: "manual" }),
    );
    openPicker.value = false;
    emit("changed", pref.value.region_code);
    toast.show(`已切换到${openRegions.value.find((r) => r.code === code)?.name ?? code}`);
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "地区切换失败");
  } finally {
    busy.value = false;
  }
}

onMounted(load);
watch(() => auth.isLoggedIn, () => void load());
</script>

<template>
  <div class="region-bar" role="group" aria-label="当前国家">
    <span class="lb">当前国家</span>

    <template v-if="pref">
      <span class="rchip" :class="{ global: isGlobal }">
        {{ regionLabel }}
        <span v-if="isRoaming" class="roaming" title="漫游中：正在浏览其它地区">漫游</span>
      </span>
    </template>
    <span v-else class="rchip">未定位</span>

    <div class="region-picker">
      <button
        type="button"
        class="reg-switch"
        :aria-expanded="openPicker"
        :aria-label="`切换国家（当前 ${regionLabel}）`"
        @click="openPicker = !openPicker"
      >
        <BaseIcon name="i-globe" :size="18" />
        <span>切换</span>
      </button>

      <div v-if="openPicker" class="region-menu" role="listbox" aria-label="选择国家">
        <button
          v-for="region in openRegions"
          :key="region.code"
          type="button"
          class="region-option"
          :class="{ active: (pref?.region_code ?? 'GLOBAL') === region.code }"
          role="option"
          :aria-selected="(pref?.region_code ?? 'GLOBAL') === region.code"
          :disabled="busy"
          @click="setRegion(region.code)"
        >
          <span>{{ region.name }}</span>
          <span v-if="(pref?.region_code ?? 'GLOBAL') === region.code" class="active-mark"><BaseIcon name="i-check" :size="14" /></span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.region-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  padding: 4px 14px;
  min-height: 44px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.lb {
  font-size: var(--fs-12);
  color: var(--muted);
  white-space: nowrap;
}
.rchip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 30px;
  padding: 0 10px;
  border-radius: var(--r-pill);
  border: 1px solid var(--line);
  background: var(--bg);
  color: var(--text);
  font-size: var(--fs-12);
  white-space: nowrap;
}
.rchip.global {
  background: var(--surface2);
  color: var(--muted);
}
.roaming {
  font-size: var(--fs-11);
  color: var(--accent-ink);
  background: var(--accent-soft);
  border-radius: var(--r-pill);
  padding: 0 6px;
}
.region-picker {
  position: relative;
  margin-left: auto;
  flex-shrink: 0;
}
.reg-switch {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: var(--tap);
  padding: 0 var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-12);
}
.region-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 4px);
  z-index: var(--z-toast);
  min-width: 140px;
  padding: var(--sp-1);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.region-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-height: var(--tap);
  padding: 0 var(--sp-2);
  border-radius: var(--r-sm);
  text-align: left;
  color: var(--text);
}
.region-option:hover:not(:disabled) {
  background: var(--hover);
}
.region-option.active {
  font-weight: var(--fw-bold);
}
.region-option:disabled {
  opacity: 0.6;
}
.active-mark {
  color: var(--accent-ink);
}
</style>
