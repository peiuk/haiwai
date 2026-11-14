#!/usr/bin/env node
/**
 * 前端逻辑测试（零新增依赖）：用项目已有的 Vite 在 Node 里直接加载 TS 源码，
 * 配合 Node 自带的 node:test 运行。只测不依赖浏览器渲染的逻辑：
 *   - usePostReactions：先变色、失败回滚、连点不重复发请求、游客弹登录
 *   - loginPrompt：登录成功后自动执行刚才的操作，且早于信息流重新加载
 *   - api.request：多标签页同时刷新令牌时不互相登出
 *   - time：相对时间格式
 * 用法：npm run test:logic
 */
import assert from "node:assert/strict";
import { beforeEach, after, before, describe, it } from "node:test";
import { setMaxListeners } from "node:events";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";
import { createPinia, setActivePinia } from "pinia";
import { reactive } from "vue";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

// ---- 最小浏览器环境：api.ts 用到 window 事件、localStorage / sessionStorage、fetch ----
function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => void map.set(k, String(v)),
    removeItem: (k) => void map.delete(k),
    clear: () => map.clear(),
  };
}
globalThis.window = new EventTarget();
// 每个用例都会新建一套 store，各自在 window 上挂监听；测试里不必为此告警
setMaxListeners(200, globalThis.window);
globalThis.localStorage = memoryStorage();
globalThis.sessionStorage = memoryStorage();

const json = (status, body) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
const tick = (ms = 0) => new Promise((r) => setTimeout(r, ms));

let vite;
let mods;

before(async () => {
  vite = await createServer({
    root: webRoot,
    appType: "custom",
    server: { middlewareMode: true, hmr: false, ws: false },
    optimizeDeps: { noDiscovery: true },
    logLevel: "silent",
  });
  mods = {
    api: await vite.ssrLoadModule("/src/api.ts"),
    reactions: await vite.ssrLoadModule("/src/composables/usePostReactions.ts"),
    auth: await vite.ssrLoadModule("/src/stores/auth.ts"),
    prompt: await vite.ssrLoadModule("/src/stores/loginPrompt.ts"),
    toast: await vite.ssrLoadModule("/src/stores/toast.ts"),
    time: await vite.ssrLoadModule("/src/utils/time.ts"),
  };
});

after(async () => {
  await vite?.close();
});

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  globalThis.fetch = async () => {
    throw new Error("unexpected fetch");
  };
});

/** 以登录 / 游客状态建一套全新的 store，返回常用句柄。 */
function setup({ loggedIn }) {
  if (loggedIn) localStorage.setItem("ukcn.token", "access-1");
  setActivePinia(createPinia());
  const auth = mods.auth.useAuthStore();
  const prompt = mods.prompt.useLoginPromptStore();
  const toast = mods.toast.useToastStore();
  const reactions = mods.reactions.usePostReactions();
  return { auth, prompt, toast, reactions };
}

describe("usePostReactions", () => {
  it("点赞：先变色，服务器确认后保持", async () => {
    const { reactions, toast } = setup({ loggedIn: true });
    const seen = [];
    globalThis.fetch = async (url) => {
      seen.push(String(url));
      await tick(20);
      return json(200, { liked: true });
    };
    const item = reactive({ content_id: "c1", liked: false });
    const pending = reactions.toggleLike(item);
    assert.equal(item.liked, true, "请求还没返回时界面就应该已经变色");
    await pending;
    assert.equal(item.liked, true);
    assert.deepEqual(seen, ["/api/v1/contents/c1/like"]);
    toast.clear();
  });

  it("点赞失败：回滚并提示后端给的文案", async () => {
    const { reactions, toast } = setup({ loggedIn: true });
    globalThis.fetch = async () => json(500, { code: "X", message: "模拟失败" });
    const item = reactive({ content_id: "c1", liked: false });
    await reactions.toggleLike(item);
    assert.equal(item.liked, false, "失败后必须恢复原状");
    assert.equal(toast.text, "模拟失败");
    toast.clear();
  });

  it("已点赞的帖子再点：先取消，以服务器结果为准", async () => {
    const { reactions, toast } = setup({ loggedIn: true });
    globalThis.fetch = async () => json(200, { liked: false });
    const item = reactive({ content_id: "c1", liked: true });
    await reactions.toggleLike(item);
    assert.equal(item.liked, false);
    toast.clear();
  });

  it("连点：请求返回前不会重复发起", async () => {
    const { reactions, toast } = setup({ loggedIn: true });
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      await tick(30);
      return json(200, { favorited: true });
    };
    const item = reactive({ content_id: "c1", favorited: false });
    await Promise.all([reactions.toggleFavorite(item), reactions.toggleFavorite(item), reactions.toggleFavorite(item)]);
    assert.equal(calls, 1);
    assert.equal(item.favorited, true);
    toast.clear();
  });

  it("转发失败：回滚 reposted", async () => {
    const { reactions, toast } = setup({ loggedIn: true });
    globalThis.fetch = async () => json(500, { code: "X", message: "转发失败啦" });
    const item = reactive({ content_id: "c1", reposted: false });
    await reactions.repost(item, "ch1");
    assert.equal(item.reposted, false);
    assert.equal(toast.text, "转发失败啦");
    toast.clear();
  });

  it("没有频道的内容不能转发，也不发请求", async () => {
    const { reactions, toast } = setup({ loggedIn: true });
    const item = reactive({ content_id: "c1", reposted: false });
    await reactions.repost(item, null);
    assert.equal(item.reposted, false);
    assert.match(toast.text, /没有可转发的频道/);
    toast.clear();
  });

  it("游客：弹登录，不改状态，不发请求", async () => {
    const { reactions, prompt } = setup({ loggedIn: false });
    const item = reactive({ content_id: "c1", liked: false });
    await reactions.toggleLike(item);
    assert.equal(prompt.open, true);
    assert.equal(item.liked, false);
  });
});

describe("loginPrompt", () => {
  it("登录成功后自动完成刚才的点赞，且先于信息流刷新", async () => {
    const { auth, prompt, reactions } = setup({ loggedIn: false });
    const order = [];
    globalThis.fetch = async (url) => {
      order.push(String(url));
      await tick(20);
      return json(200, { liked: true });
    };
    const item = reactive({ content_id: "c1", liked: false });
    await reactions.toggleLike(item); // 游客：只弹窗
    assert.equal(prompt.open, true);
    assert.deepEqual(order, []);

    auth.login("access-new"); // 弹窗里登录成功
    assert.equal(prompt.open, false, "登录后弹窗关闭");
    // 信息流会在登录状态变化时调用 whenIdle().then(reload)：要等自动操作做完才轮到它
    await prompt.whenIdle();
    order.push("reload");
    assert.deepEqual(order, ["/api/v1/contents/c1/like", "reload"]);
    assert.equal(item.liked, true);
  });

  it("关闭弹窗：之后再登录也不会执行被放弃的操作", async () => {
    const { auth, prompt, reactions } = setup({ loggedIn: false });
    let calls = 0;
    globalThis.fetch = async () => {
      calls += 1;
      return json(200, { liked: true });
    };
    const item = reactive({ content_id: "c1", liked: false });
    await reactions.toggleLike(item);
    prompt.close();
    auth.login("access-new");
    await prompt.whenIdle();
    await tick(30);
    assert.equal(calls, 0);
    assert.equal(item.liked, false);
  });

  it("没开弹窗时登录（比如在「我的」页）：不会误执行任何操作", async () => {
    const { auth, prompt } = setup({ loggedIn: false });
    auth.login("access-new");
    await prompt.whenIdle();
    assert.equal(prompt.open, false);
  });
});

describe("api.request 令牌续期", () => {
  const tokenCall = (init) => init?.headers?.Authorization;

  it("两个标签页同时续期：慢的一方被拒，但沿用另一方写入的新令牌，不登出", async () => {
    localStorage.setItem("ukcn.token", "expired");
    localStorage.setItem("ukcn.refresh", "r1");
    let refreshCalls = 0;
    globalThis.fetch = async (url, init) => {
      if (String(url).includes("/auth/refresh")) {
        refreshCalls += 1;
        // 另一个标签页抢先续期并写入了新令牌，轮到我们时旧 refresh 已被后端作废
        localStorage.setItem("ukcn.token", "fresh");
        localStorage.setItem("ukcn.refresh", "r2");
        return json(401, { code: "INVALID_REFRESH", message: "登录已失效" });
      }
      return tokenCall(init) === "Bearer fresh" ? json(200, { ok: true }) : json(401, { code: "X", message: "过期" });
    };
    const result = await mods.api.request("/api/v1/me/badges");
    assert.deepEqual(result, { ok: true });
    assert.equal(refreshCalls, 1);
    assert.equal(localStorage.getItem("ukcn.refresh"), "r2", "新令牌必须保留");
  });

  it("续期真的失败（令牌没人换过）：清掉登录态并报错", async () => {
    localStorage.setItem("ukcn.token", "expired");
    localStorage.setItem("ukcn.refresh", "r1");
    let cleared = 0;
    mods.api.onAuthCleared(() => {
      cleared += 1;
    });
    globalThis.fetch = async (url) =>
      String(url).includes("/auth/refresh")
        ? json(401, { code: "INVALID_REFRESH", message: "登录已失效" })
        : json(401, { code: "X", message: "过期" });
    await assert.rejects(() => mods.api.request("/api/v1/me/badges"), { status: 401 });
    assert.equal(localStorage.getItem("ukcn.token"), null);
    assert.equal(localStorage.getItem("ukcn.refresh"), null);
    assert.ok(cleared >= 1);
  });

  it("旧版本放在 sessionStorage 里的令牌：读取时迁移到 localStorage", () => {
    sessionStorage.setItem("ukcn.token", "legacy");
    assert.equal(mods.api.getToken(), "legacy");
    assert.equal(localStorage.getItem("ukcn.token"), "legacy");
    assert.equal(sessionStorage.getItem("ukcn.token"), null);
  });
});

describe("fmtRelativeTime", () => {
  const ago = (ms) => new Date(Date.now() - ms).toISOString();
  it("各档位", () => {
    const f = mods.time.fmtRelativeTime;
    assert.equal(f(ago(10_000)), "刚刚");
    assert.equal(f(ago(5 * 60_000)), "5 分钟前");
    assert.equal(f(ago(3 * 3_600_000)), "3 小时前");
    assert.equal(f(ago(2 * 86_400_000)), "2 天前");
    assert.equal(f(ago(30 * 86_400_000)), new Date(ago(30 * 86_400_000)).toLocaleDateString("zh-CN"));
  });
  it("空值与无效值返回空串", () => {
    const f = mods.time.fmtRelativeTime;
    assert.equal(f(""), "");
    assert.equal(f(null), "");
    assert.equal(f("不是时间"), "");
  });
});
