// 首页缓存的版本号：AppShell 用它作为首页的 key。
// 浏览器「后退 / 前进」回到首页时版本不变，沿用缓存的信息流和滚动位置；
// 从别的页面主动点进首页时版本加一，得到一份新加载的首页。
// 单独成文件：router 引入 AppShell，AppShell 又要读这个值，放在 router 里会形成循环依赖。
import { ref } from "vue";

export const homeCacheKey = ref(0);
