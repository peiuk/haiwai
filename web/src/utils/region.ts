// 游客的国家：首页国家栏选的（存在本地），没选过就按浏览器时区 / 语言猜。
// api.ts 把它放进 X-Region 请求头：游客、以及账号里还没存过国家的新用户，后端按它给内容；存过的以账号为准。
export const GUEST_REGION_KEY = "ukcn.guest-region";

// ---- 自动定位：浏览器语言 + 时区 -> 国家代码 ----
// 常见语言/时区映射到 ISO 国家代码；未命中返回 null（走 GLOBAL 回落）。
export function detectCountryCode(): string | null {
  // 1) 时区优先（最贴近物理位置）
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";
  const tzMap: Record<string, string> = {
    "Europe/London": "UK",
    "Europe/Paris": "FR",
    "Europe/Berlin": "DE",
    "Europe/Madrid": "ES",
    "Europe/Rome": "IT",
    "Europe/Amsterdam": "NL",
    "Europe/Dublin": "IE",
    "Europe/Lisbon": "PT",
    "Europe/Stockholm": "SE",
    "Europe/Oslo": "NO",
    "Europe/Zurich": "CH",
    "Europe/Vienna": "AT",
    "Europe/Brussels": "BE",
    "Europe/Warsaw": "PL",
    "Europe/Prague": "CZ",
    "Europe/Athens": "GR",
    "Europe/Helsinki": "FI",
    "Europe/Copenhagen": "DK",
    "Europe/Budapest": "HU",
    "Europe/Bucharest": "RO",
    "Europe/Sofia": "BG",
    "Europe/Luxembourg": "LU",
    "Europe/Bratislava": "SK",
    "Europe/Zagreb": "HR",
    "Europe/Ljubljana": "SI",
    "Europe/Tallinn": "EE",
    "Europe/Riga": "LV",
    "Europe/Vilnius": "LT",
    "Europe/Nicosia": "CY",
    "Europe/Valletta": "MT",
    "Asia/Tokyo": "JP",
    "Asia/Seoul": "KR",
    "Asia/Shanghai": "CN",
    "Asia/Hong_Kong": "HK",
    "Asia/Taipei": "TW",
    "Asia/Singapore": "SG",
    "Asia/Bangkok": "TH",
    "Asia/Kuala_Lumpur": "MY",
    "Asia/Jakarta": "ID",
    "Asia/Dubai": "AE",
    "Asia/Kolkata": "IN",
    "America/New_York": "US",
    "America/Chicago": "US",
    "America/Los_Angeles": "US",
    "America/Toronto": "CA",
    "America/Vancouver": "CA",
    "Australia/Sydney": "AU",
    "Australia/Melbourne": "AU",
    "Pacific/Auckland": "NZ",
  };
  if (tzMap[tz]) return tzMap[tz];

  // 2) 浏览器语言回退（en-GB -> UK）
  const lang = navigator.language ?? "";
  const langMap: Record<string, string> = {
    "en-gb": "UK",
    "en-ie": "IE",
    "en-au": "AU",
    "en-nz": "NZ",
    "en-ca": "CA",
    "fr": "FR",
    "de": "DE",
    "es": "ES",
    "it": "IT",
    "nl": "NL",
    "pt": "PT",
    "ja": "JP",
    "ko": "KR",
    "zh": "CN",
    "zh-cn": "CN",
    "zh-hk": "HK",
    "zh-tw": "TW",
    "en": "UK",
    "en-us": "US",
  };
  const key = lang.toLowerCase();
  if (langMap[key]) return langMap[key];
  if (key.startsWith("en-")) return "UK";
  return null;
}

export function guestRegion(): string {
  try {
    const saved = localStorage.getItem(GUEST_REGION_KEY);
    if (saved) return saved;
  } catch {
    // 存储不可用时退回自动判断
  }
  return detectCountryCode() ?? "";
}
