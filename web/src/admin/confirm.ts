// 后台的二次确认：页面调用 confirmAction()，由 AdminLayout 里唯一的 AdminConfirm 弹窗显示。
import { reactive } from "vue";

export type ConfirmOptions = {
  title: string;
  message?: string;
  confirmLabel: string;
  danger?: boolean;
  /** 是否让管理员填理由（记入操作日志） */
  reason?: boolean;
  /** 不可恢复的操作：要求原样输入这段文字（如频道名）后才能点确认 */
  mustType?: string;
  /** 让管理员选封禁多久（结果在 confirmExtras.days，空串是永久） */
  days?: boolean;
  /** 附带一个勾选项（结果在 confirmExtras.checked），这里是它的文字 */
  checkbox?: string;
};

/** 确认框里除理由以外的选择；确认后由调用方读取。 */
export const confirmExtras = reactive({ days: "", checked: false });

export const confirmState = reactive<{
  open: boolean;
  options: ConfirmOptions;
  resolve: ((value: string | null) => void) | null;
}>({ open: false, options: { title: "", confirmLabel: "确定" }, resolve: null });

/** 弹出确认框；确认返回填写的理由（可能是空串），取消返回 null。 */
export function confirmAction(options: ConfirmOptions): Promise<string | null> {
  confirmState.resolve?.(null); // 上一个还没答就又弹了：按取消处理
  return new Promise((resolve) => {
    confirmState.options = options;
    confirmState.resolve = resolve;
    confirmState.open = true;
  });
}

export function settleConfirm(value: string | null): void {
  confirmState.open = false;
  confirmState.resolve?.(value);
  confirmState.resolve = null;
}
