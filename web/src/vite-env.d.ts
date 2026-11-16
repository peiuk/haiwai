/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 对外公示的联系方式（邮箱等），构建时填；留空则只显示「联系平台管理员」 */
  readonly VITE_SUPPORT_CONTACT?: string;
}

declare module "*.vue" {
  import type { DefineComponent } from "vue";
  const component: DefineComponent<object, object, unknown>;
  export default component;
}
