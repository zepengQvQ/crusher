/**
 * P2-RC-05：智能跳转上下文（不存密钥；仅跨页预填材料与目标）。
 * sessionStorage 键名集中管理，避免各页散落魔法字符串。
 */
export const INTENT_CONTEXT_KEY = 'crusher_intent_context'
export const COMPARE_A_KEY = 'crusher_compare_a'
export const DUAL_SALES_PREFILL_KEY = 'crusher_dual_sales_prefill'

/**
 * @param {{ text?: string, userGoal?: string, productHint?: string, targetIntent?: string }} ctx
 */
export function saveIntentContext(ctx) {
  try {
    const text = (ctx.text || '').trim()
    const payload = {
      text,
      userGoal: (ctx.userGoal || '').trim(),
      productHint: ctx.productHint || 'auto',
      targetIntent: ctx.targetIntent || '',
    }
    sessionStorage.setItem(INTENT_CONTEXT_KEY, JSON.stringify(payload))
    if (text) {
      // 产品对照页已有预填约定
      sessionStorage.setItem(COMPARE_A_KEY, text)
      // 双材料页预填销售话术侧
      sessionStorage.setItem(DUAL_SALES_PREFILL_KEY, text)
    }
  } catch {
    /* ignore quota */
  }
}

/** @returns {{ text: string, userGoal: string, productHint: string, targetIntent: string } | null} */
export function loadIntentContext() {
  try {
    const raw = sessionStorage.getItem(INTENT_CONTEXT_KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    return {
      text: data?.text || '',
      userGoal: data?.userGoal || '',
      productHint: data?.productHint || 'auto',
      targetIntent: data?.targetIntent || '',
    }
  } catch {
    return null
  }
}

export function clearIntentContext() {
  try {
    sessionStorage.removeItem(INTENT_CONTEXT_KEY)
  } catch {
    /* ignore */
  }
}
