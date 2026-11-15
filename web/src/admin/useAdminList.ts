// 后台表格页共用：分页加载 + 写操作（提交 → 提示 → 刷新）。
import { ref, type Ref } from "vue";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { ADMIN_CHANGED, adminRequest } from "./adminApi";
import { confirmAction, type ConfirmOptions } from "./confirm";
import type { Paged } from "./shared";

/** 写操作：同一时间只提交一个，成功后调用 after 刷新，并通知菜单更新待办数字。 */
export function useAdminAction(after: () => Promise<void>) {
  const toast = useToastStore();
  const busy = ref(""); // 正在提交的那一行，防止重复点击

  async function act(key: string, path: string, body: unknown, done: string): Promise<void> {
    if (busy.value) return;
    busy.value = key;
    try {
      await adminRequest(path, jsonBody(body));
      toast.show(done);
      window.dispatchEvent(new Event(ADMIN_CHANGED));
      await after();
    } catch (err) {
      toast.show(toMessage(err));
    } finally {
      busy.value = "";
    }
  }

  /** 先弹确认框（可填理由），确认后再提交；body 用填写的理由生成。 */
  async function ask(options: ConfirmOptions, key: string, path: string, body: (reason: string) => unknown, done: string): Promise<void> {
    const reason = await confirmAction(options);
    if (reason === null) return;
    await act(key, path, body(reason), done);
  }

  return { busy, act, ask };
}

export function useAdminList<T>(path: string, filters: () => Record<string, string>) {
  const items = ref([]) as Ref<T[]>;
  const total = ref(0);
  const pageSize = ref(20);
  const page = ref(1);
  const loading = ref(false);
  const error = ref("");
  let version = 0;

  async function load(): Promise<void> {
    const mine = ++version;
    loading.value = true;
    error.value = "";
    const params = new URLSearchParams({ page: String(page.value) });
    for (const [key, value] of Object.entries(filters())) if (value.trim()) params.set(key, value.trim());
    try {
      const body = await adminRequest<Paged<T>>(`${path}?${params.toString()}`);
      if (mine !== version) return;
      items.value = body.items;
      total.value = body.total;
      pageSize.value = body.page_size;
    } catch (err) {
      if (mine === version) error.value = toMessage(err);
    } finally {
      if (mine === version) loading.value = false;
    }
  }

  function search(): void {
    page.value = 1;
    void load();
  }

  function go(next: number): void {
    page.value = next;
    void load();
  }

  const { busy, act, ask } = useAdminAction(load);
  void load();
  return { items, total, pageSize, page, loading, error, busy, load, search, go, act, ask };
}
