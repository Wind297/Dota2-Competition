import { ref } from "vue";

// ≤ 640px 视为手机；与 Naive UI 的 sm 断点一致。
const MOBILE_MAX = 640;

function init() {
  if (typeof window === "undefined") {
    return ref(false);
  }
  const mql = window.matchMedia(`(max-width: ${MOBILE_MAX}px)`);
  const r = ref(mql.matches);
  mql.addEventListener("change", (e: MediaQueryListEvent) => {
    r.value = e.matches;
  });
  return r;
}

const isMobile = init();

/** 共享的移动端判断 ref；任何组件 setup 里直接 `const isMobile = useIsMobile();` 即可。 */
export function useIsMobile() {
  return isMobile;
}

export { isMobile };
