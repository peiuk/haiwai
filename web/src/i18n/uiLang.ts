// 全站界面简繁：DOM 级自动转换，对齐原型 UKCN.applyLang。
// 覆盖：中文文本节点 + aria-label/placeholder/title + document.title；
// 跳过：data-ugc（用户发布内容保持原文）、data-no-hant、输入控件与 script/style/svg。
// 与 Vue 的关系：不接管渲染，只观察 DOM；每个节点缓存 {hans,hant} 原文，
// 语言切换时按原文重新转换，Vue 后续 patch 写回简体也能被正确重新转换。
import { watch } from "vue";
import { useThemeStore } from "../stores/theme";
import { toHant } from "./toHant";

type TextRecord = { hans: string; hant: string };

const textRecords = new WeakMap<Text, TextRecord>();
const attrRecords = new WeakMap<Element, Record<string, TextRecord>>();
const LANG_ATTRS = ["aria-label", "placeholder", "title"] as const;
const SKIP_TAGS = new Set([
  "SCRIPT",
  "STYLE",
  "TEXTAREA",
  "INPUT",
  "IFRAME",
  "NOSCRIPT",
  "CODE",
  "PRE",
  "SVG",
  "OPTION",
  "SELECT",
]);
const HAS_HAN = /[\u4e00-\u9fff]/;

let originalTitle: string | null = null;

function isSkipped(node: Node): boolean {
  let el: Element | null = node.nodeType === Node.ELEMENT_NODE ? (node as Element) : node.parentElement;
  while (el) {
    if (SKIP_TAGS.has(el.tagName.toUpperCase())) return true;
    if (
      el.hasAttribute("data-ugc") ||
      el.hasAttribute("data-no-hant") ||
      el.getAttribute("translate") === "no"
    ) {
      return true;
    }
    el = el.parentElement;
  }
  return false;
}

function convertText(node: Text, hant: boolean): void {
  const current = node.nodeValue ?? "";
  if (!HAS_HAN.test(current)) return;
  let record = textRecords.get(node);
  if (!record || (current !== record.hans && current !== record.hant)) {
    record = { hans: current, hant: toHant(current) };
    textRecords.set(node, record);
  }
  const target = hant ? record.hant : record.hans;
  // 已是目标值时不写回，MutationObserver 因此不会自激循环。
  if (node.nodeValue !== target) node.nodeValue = target;
}

function convertAttrs(el: Element, hant: boolean): void {
  if (isSkipped(el)) return;
  const records = attrRecords.get(el) ?? {};
  for (const attr of LANG_ATTRS) {
    if (!el.hasAttribute(attr)) continue;
    const value = el.getAttribute(attr) ?? "";
    let record = records[attr];
    if (!record || (value !== record.hans && value !== record.hant)) {
      record = { hans: value, hant: toHant(value) };
      records[attr] = record;
    }
    const target = hant ? record.hant : record.hans;
    if (value !== target) el.setAttribute(attr, target);
  }
  attrRecords.set(el, records);
}

function convertTitle(hant: boolean): void {
  const title = document.title;
  if (!title) return;
  if (hant) {
    if (originalTitle === null || toHant(originalTitle) !== title) originalTitle = title;
    const next = toHant(originalTitle);
    if (title !== next) document.title = next;
  } else if (originalTitle && title === toHant(originalTitle)) {
    document.title = originalTitle;
  }
}

/**
 * 设置网页标题（路由切换时用）：同时记下简体原文，简繁切换时才能正确还原；
 * 当前是繁体界面就直接显示繁体。
 */
export function setDocumentTitle(title: string): void {
  originalTitle = title;
  document.title = useThemeStore().lang === "zh-Hant" ? toHant(title) : title;
}

function walk(root: Node, hant: boolean): void {
  if (root.nodeType === Node.TEXT_NODE) {
    if (!isSkipped(root)) convertText(root as Text, hant);
    return;
  }
  if (root.nodeType !== Node.ELEMENT_NODE || isSkipped(root)) return;
  convertAttrs(root as Element, hant);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (node) => {
      if (isSkipped(node)) return NodeFilter.FILTER_REJECT;
      if (node.nodeType === Node.TEXT_NODE) {
        return HAS_HAN.test(node.nodeValue ?? "") ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes: Node[] = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (node.nodeType === Node.TEXT_NODE) convertText(node as Text, hant);
    else convertAttrs(node as Element, hant);
  }
}

/**
 * 挂载后启动：监听主题 store 的 lang，并对 body 子树做文本/属性观察。
 * theme（light/dark）由 store 单独写 data-theme，这里完全不触碰，保证 §7.6 双维度独立。
 */
export function startUiLang(): () => void {
  if (typeof document === "undefined" || typeof MutationObserver === "undefined") {
    return () => undefined;
  }
  const theme = useThemeStore();
  const root = document.body;
  const isHant = () => theme.lang === "zh-Hant";

  const applyAll = (): void => {
    const hant = isHant();
    convertTitle(hant);
    walk(root, hant);
  };

  applyAll();
  const observer = new MutationObserver((mutations) => {
    const hant = isHant();
    for (const mutation of mutations) {
      if (mutation.type === "characterData") {
        if (!isSkipped(mutation.target)) convertText(mutation.target as Text, hant);
        continue;
      }
      if (mutation.type === "attributes") {
        convertAttrs(mutation.target as Element, hant);
        continue;
      }
      for (const added of Array.from(mutation.addedNodes)) {
        walk(added, hant);
      }
    }
  });
  observer.observe(root, {
    childList: true,
    characterData: true,
    attributes: true,
    attributeFilter: [...LANG_ATTRS],
    subtree: true,
  });
  const stopWatch = watch(() => theme.lang, applyAll, { flush: "post" });

  return () => {
    observer.disconnect();
    stopWatch();
  };
}
