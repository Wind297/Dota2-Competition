import { ref } from "vue";
import { fetchConfig, updateDeductThreshold as apiUpdateThreshold } from "@/api";

/** 扣分阈值默认值（与后端 DEFAULT_DEDUCT_THRESHOLD 保持一致，仅作加载前兜底）。 */
export const DEFAULT_DEDUCT_THRESHOLD = 8;

/** 全局扣分阈值：负方基础积分 > 阈值 时可被勾选扣 1 分。所有页面共享此 ref。 */
export const deductThreshold = ref<number>(DEFAULT_DEDUCT_THRESHOLD);

/** 从后端加载全局配置。失败时保持默认值，不抛错（避免阻塞页面）。 */
export async function loadConfig(): Promise<void> {
  try {
    const cfg = await fetchConfig();
    deductThreshold.value = cfg.deduct_threshold;
  } catch {
    // 加载失败保持默认值
  }
}

/** 更新扣分阈值并同步到共享 ref。失败时抛错给调用方处理。 */
export async function saveDeductThreshold(value: number): Promise<void> {
  const cfg = await apiUpdateThreshold(value);
  deductThreshold.value = cfg.deduct_threshold;
}
