// 登录提示：游客做需要登录的操作（点赞、收藏、转发、加入频道）时弹出登录 / 注册，
// 登录成功后自动完成刚才的操作（MASTER §22.14：「游客点喜欢 / 收藏先轻注册，完成后自动执行」）。
import { defineStore } from "pinia";
import { ref, watch } from "vue";
import { useAuthStore } from "./auth";

type PendingAction = () => void | Promise<void>;

export const useLoginPromptStore = defineStore("loginPrompt", () => {
  const auth = useAuthStore();
  const open = ref(false);
  const reason = ref("");
  let pending: PendingAction | null = null;
  let running: Promise<void> | null = null;

  /** 弹出登录提示；action 会在登录成功后自动执行。 */
  function require(reasonText: string, action?: PendingAction): void {
    reason.value = reasonText;
    pending = action ?? null;
    open.value = true;
  }

  function close(): void {
    open.value = false;
    pending = null;
  }

  /** 登录后自动执行的操作完成前，信息流先不要重新加载，否则会拿到操作前的状态。 */
  function whenIdle(): Promise<void> {
    return running ?? Promise.resolve();
  }

  // 同步监听：赶在各信息流「登录状态变了就重新加载」之前，把待执行的操作先发出去。
  watch(
    () => auth.isLoggedIn,
    (loggedIn) => {
      if (!loggedIn || !open.value) return;
      const action = pending;
      pending = null;
      open.value = false;
      if (!action) return;
      const task = Promise.resolve()
        .then(action)
        .catch(() => undefined)
        .finally(() => {
          if (running === task) running = null;
        });
      running = task;
    },
    { flush: "sync" },
  );

  return { open, reason, require, close, whenIdle };
});
