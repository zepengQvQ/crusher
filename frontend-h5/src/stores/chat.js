import { defineStore, acceptHMRUpdate } from 'pinia'
import {
  createAnalysis,
  createFollowUp,
  extractDocuments,
  getAnalysis,
  pickErrorMessage,
  resolveIntent,
} from '../api/client'

const CHAT_KEY = 'crusher_chat'
const POLL_MS = 800
const POLL_MAX = 60

export const SKILL_ITEMS = [
  { key: 'paste', label: '粘贴条款', icon: 'edit' },
  { key: 'upload', label: '上传文件', icon: 'photograph' },
  { key: 'analyze', label: '开始分析', icon: 'fire-o' },
  { key: 'clear', label: '清空材料', icon: 'delete-o' },
]

const GUIDE_WELCOME =
  '你好，我是金融话术粉碎机助手。\n\n点左下角「+」可粘贴条款或上传文件，材料会留在本会话；备齐后点「开始分析」。也可直接说想做什么。'

function intentReply(decision) {
  if (!decision) return '暂时无法识别你的目标，请换一种说法或点快捷选项。'
  if (decision.status === 'resolved') {
    const reasons = (decision.rationale || []).join('；')
    return reasons ? `已识别：${reasons}\n正在为你打开对应功能…` : '已识别目标，正在为你打开对应功能…'
  }
  if (decision.intent === 'unsupported' || decision.status === 'rejected') {
    return (decision.rationale || []).join('；') || '该需求超出当前 Demo 范围，不能提供购买建议。'
  }
  const reasons = (decision.rationale || []).join('；')
  return reasons || '目标还不明确，请从下面选一件事继续。'
}

function joinMaterials(materials) {
  return (materials || [])
    .map((m) => String(m?.text || '').trim())
    .filter(Boolean)
    .join('\n\n')
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** 寒暄 / 无实质问题：有材料时也不走证据追问。 */
function isChitchat(text) {
  const t = String(text || '')
    .trim()
    .replace(/[！!。.?？~\s]/g, '')
  if (!t) return true
  return /^(你好|您好|嗨|哈喽|在吗|在不在|谢谢|多谢|早上好|中午好|下午好|晚上好|hi|hello|hey|ok|好的|嗯|哦)$/i.test(
    t,
  )
}

/** 聊天完成气泡只用口语摘要；程序账本 / 英文键名一律不进会话。 */
function isChatFriendlyPlain(text) {
  const t = String(text || '').trim()
  if (!t || t.length < 8) return false
  if (
    /invents numbers|explanation invents|MODEL_|OUTPUT_VERIFICATION|draft empty|【部分结果】|【事实】|【参数】|【风险】|【程序说明】|已阻止当作正常解释|product_risk_grade|principal_protection|\bterm\s*:/i.test(
      t,
    )
  ) {
    return false
  }
  // 像「期限：183天」这种短中文说明可以展示；含大量英文 snake_case 则不要
  const snake = (t.match(/[a-z]+_[a-z0-9_]+/gi) || []).length
  if (snake >= 1) return false
  return true
}

/**
 * 分析完成气泡统一 SOP：
 * 1) 看完了 + 风险条数
 * 2) 可选：最多 3 条风险标题
 * 3) 可选：真正的人话通俗解释（非账本）
 * 4) 发布态一句话 + 引导打开报告
 * 禁止：task_id、publish、英文诊断、【事实】账本
 */
function formatAnalyzeDone({ findingCount, outcome, plainText, findingTitles }) {
  const count = Number(findingCount) || 0
  const riskLine =
    count <= 0
      ? '按当前材料，没有抓到需要特别标出的风险点。'
      : `按当前材料，标出了 ${count} 条需要留意的点。`

  const titles = (findingTitles || []).map((t) => String(t || '').trim()).filter(Boolean)
  const titleBlock =
    titles.length > 0
      ? `\n\n主要留意：\n${titles
          .slice(0, 3)
          .map((t) => `· ${t}`)
          .join('\n')}`
      : ''

  let statusLine = ''
  if (outcome === 'publish_partial') {
    statusLine = '有一部分结论已确认；详细内容请打开报告对照原文。'
  } else if (outcome === 'clarify') {
    statusLine = '还有几处信息不够清楚，报告里写了待确认问题。'
  } else if (outcome === 'refuse') {
    statusLine = '这次没法给出完整结论，原因写在报告里。'
  }

  const plain = isChatFriendlyPlain(plainText)
    ? String(plainText).trim().replace(/\s+/g, ' ')
    : ''
  const plainLine = plain
    ? `\n\n先说一句人话：${plain.length > 100 ? `${plain.slice(0, 100)}…` : plain}`
    : ''

  const tail = statusLine
    ? `\n${statusLine}\n\n想继续问就直接说，或点「查看报告」。`
    : '\n\n想继续问就直接说，或点「查看报告」。'

  return `看完了。${riskLine}${titleBlock}${plainLine}${tail}`
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    materials: [],
    contextText: '',
    contextFindings: [],
    pendingQuestions: [],
    lastTaskId: '',
  }),
  getters: {
    hasMaterials: (s) => (s.materials || []).some((m) => String(m?.text || '').trim()),
    hasContext: (s) => !!(s.contextText || '').trim() || (s.materials || []).some((m) => String(m?.text || '').trim()),
    materialSourceText: (s) => {
      const fromMats = joinMaterials(s.materials)
      return fromMats || (s.contextText || '').trim()
    },
  },
  actions: {
    restore() {
      try {
        const raw = sessionStorage.getItem(CHAT_KEY)
        if (raw) {
          const d = JSON.parse(raw)
          this.messages = Array.isArray(d?.messages) ? d.messages : []
          this.materials = Array.isArray(d?.materials) ? d.materials : []
          this.contextText = d?.contextText || ''
          this.contextFindings = Array.isArray(d?.contextFindings) ? d.contextFindings : []
          this.pendingQuestions = Array.isArray(d?.pendingQuestions) ? d.pendingQuestions : []
          this.lastTaskId = d?.lastTaskId || ''
          this._syncContextFromMaterials()
        }
      } catch {
        this.messages = []
        this.materials = []
      }
    },
    _persist() {
      try {
        sessionStorage.setItem(
          CHAT_KEY,
          JSON.stringify({
            messages: this.messages,
            materials: this.materials,
            contextText: this.contextText,
            contextFindings: this.contextFindings,
            pendingQuestions: this.pendingQuestions,
            lastTaskId: this.lastTaskId,
          }),
        )
      } catch {
        /* ignore */
      }
    },
    _syncContextFromMaterials() {
      const joined = joinMaterials(this.materials)
      if (joined) {
        this.contextText = joined
      }
    },
    _pushAi(content, meta = {}) {
      const msg = {
        id: 'a_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
        role: 'ai',
        content,
        time: Date.now(),
        meta,
      }
      this.messages.push(msg)
      this._persist()
      return msg
    },
    _pushUser(content, meta = {}) {
      const msg = {
        id: 'u_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
        role: 'user',
        content,
        time: Date.now(),
        meta,
      }
      this.messages.push(msg)
      this._persist()
      return msg
    },
    ensureGuideWelcome() {
      if (this.messages.length) return
      this.messages.push({
        id: 'welcome_' + Date.now(),
        role: 'ai',
        content: GUIDE_WELCOME,
        time: Date.now(),
        meta: { kind: 'guide_welcome' },
      })
      this._persist()
    },
    setContext(text, findings = [], pendingQuestions = []) {
      this.contextText = text || ''
      this.contextFindings = findings || []
      this.pendingQuestions = pendingQuestions || []
      if (!this.messages.length) {
        this.messages.push({
          id: 'welcome_' + Date.now(),
          role: 'ai',
          content:
            '已关联刚才的分析材料。请围绕原文提问；回答将由服务端按证据接口返回，不会编造结论。',
          time: Date.now(),
        })
      }
      this._persist()
    },
    /**
     * @param {{ kind: 'paste'|'upload', name?: string, text: string }} payload
     */
    addMaterial(payload) {
      const text = String(payload?.text || '').trim()
      if (!text) {
        const err = new Error('EMPTY_MATERIAL')
        err.code = 'EMPTY_MATERIAL'
        throw err
      }
      const kind = payload.kind === 'upload' ? 'upload' : 'paste'
      const name =
        String(payload.name || '').trim() ||
        (kind === 'upload' ? '上传材料' : '粘贴条款')
      const item = {
        id: 'mat_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
        kind,
        name,
        text,
      }
      this.materials.push(item)
      this._syncContextFromMaterials()
      this._pushUser(`[材料] ${name}\n${text.slice(0, 180)}${text.length > 180 ? '…' : ''}`, {
        kind: 'material',
        materialId: item.id,
      })
      this._pushAi(`已收到「${name}」，共 ${text.length} 字。可继续添加材料，或点「开始分析」。`, {
        kind: 'material_ack',
      })
      this._persist()
      return item
    },
    clearMaterials() {
      this.materials = []
      this.contextFindings = []
      this.pendingQuestions = []
      this.contextText = ''
      this.lastTaskId = ''
      this._pushAi('已清空会话材料。可用「+」重新粘贴或上传。', { kind: 'materials_cleared' })
      this._persist()
    },
    /**
     * @param {File[]} files
     */
    async addUploadFiles(files) {
      const list = Array.from(files || []).filter(Boolean)
      if (!list.length) {
        const err = new Error('NO_FILES')
        err.code = 'NO_FILES'
        throw err
      }
      try {
        const doc = await extractDocuments(list)
        const text = String(doc?.combined_text || '').trim()
        if (!text || doc?.overall_status === 'failed') {
          this._pushAi(doc?.message || '提取失败：未得到可用正文，请换文件重试。', {
            kind: 'upload_error',
          })
          const err = new Error('EXTRACT_FAILED')
          err.code = 'EXTRACT_FAILED'
          throw err
        }
        const name = list.map((f) => f.name).join('、') || '上传材料'
        return this.addMaterial({ kind: 'upload', name, text })
      } catch (e) {
        if (e?.code === 'EXTRACT_FAILED' || e?.code === 'EMPTY_MATERIAL') throw e
        const msg = pickErrorMessage(e)
        this._pushAi(`上传解析失败：${msg}`, { kind: 'upload_error' })
        throw e
      }
    },
    async analyzeMaterials(productHint = 'auto') {
      const source = this.materialSourceText
      if (!source) {
        this._pushAi('还没有材料。请先用「+」粘贴条款或上传文件。', { kind: 'analyze_need_material' })
        const err = new Error('NO_MATERIAL')
        err.code = 'NO_MATERIAL'
        throw err
      }
      this._pushUser('开始分析', { kind: 'analyze_request' })
      this._pushAi('正在看这份材料，稍等一下…', { kind: 'analyze_progress' })
      try {
        const created = await createAnalysis(source, { productHint: productHint || 'auto' })
        const taskId = created.task_id
        this.lastTaskId = taskId
        let data = null
        for (let i = 0; i < POLL_MAX; i += 1) {
          data = await getAnalysis(taskId)
          if (data.task_status === 'completed' || data.task_status === 'failed' || data.is_failure) {
            break
          }
          await sleep(POLL_MS)
        }
        if (!data || (data.task_status !== 'completed' && data.task_status !== 'failed' && !data.is_failure)) {
          this._pushAi('还在处理中。可以稍后再打开报告，或再试一次。', {
            kind: 'analyze_timeout',
            taskId,
          })
          return { taskId, data }
        }
        if (data.task_status === 'failed' || data.is_failure) {
          const reason = data.error?.message || data.failure_reason || '这次没分析成功'
          this._pushAi(`没分析成功：${reason}`, { kind: 'analyze_failed', taskId })
          return { taskId, data }
        }
        const findings = Array.isArray(data.report?.findings) ? data.report.findings : []
        const pending = Array.isArray(data.report?.pending_questions)
          ? data.report.pending_questions
          : []
        this.contextText = data.source_text || source
        this.contextFindings = findings
        this.pendingQuestions = pending
        const outcome = data.publication?.outcome || data.report?.publication?.outcome || ''
        const plainText = data.report?.plain_language?.text || ''
        this._pushAi(
          formatAnalyzeDone({
            findingCount: findings.length,
            outcome,
            plainText,
            findingTitles: findings.map((f) => f.title || f.explanation || '').filter(Boolean),
          }),
          { kind: 'analyze_done', taskId, findingCount: findings.length },
        )
        this._persist()
        return { taskId, data }
      } catch (e) {
        if (e?.code === 'NO_MATERIAL') throw e
        const msg = pickErrorMessage(e)
        this._pushAi(`没分析成功：${msg}`, { kind: 'analyze_failed' })
        throw e
      }
    },
    /**
     * @param {string} question
     * @returns {Promise<object|null>}
     */
    async send(question) {
      const text = String(question || '').trim()
      if (!text) return null

      this._pushUser(text)

      const source = this.materialSourceText
      if (!source) {
        return this._sendGuide(text)
      }

      if (isChitchat(text)) {
        return this._pushAi(
          '你好。可以问材料里的具体问题（比如收益率、提前赎回、是否保本），或点下方快捷问题；材料不够时用左下角「+」补充。',
          { kind: 'chitchat' },
        )
      }

      try {
        const data = await createFollowUp(text, source, this.pendingQuestions)
        if (!data || typeof data.answer !== 'string' || !data.answer.trim()) {
          throw new Error('追问接口未返回有效答案')
        }
        let reply = data.answer
        if (data.status === 'insufficient_evidence') {
          const items = Array.isArray(data.missing_info)
            ? data.missing_info.map((s) => String(s || '').trim()).filter(Boolean).slice(0, 4)
            : []
          const list = items.length
            ? `建议补充这些材料：\n${items.map((s) => `· ${s}`).join('\n')}`
            : '建议补充：能直接回答你这个问题的正式条款原文。'
          reply = [
            data.answer || '按现有材料还没法确定回答。',
            list,
            '怎么补：点左下角「+」→「粘贴条款」或「上传文件」，加进本会话后再问一次。',
          ].join('\n\n')
        } else if (data.status === 'out_of_scope') {
          reply = data.answer || '这个问题超出了当前材料能回答的范围。'
        }
        return this._pushAi(reply, {
          kind: 'follow_up',
          status: data.status,
          needSupplement: data.status === 'insufficient_evidence',
          evidence: Array.isArray(data.evidence) ? data.evidence : [],
          publication: data.publication || null,
        })
      } catch (e) {
        const msg = pickErrorMessage(e)
        this._pushAi(`追问失败：${msg}\n\n请确认后端已启动，且已关联有效分析材料。`, {
          kind: 'follow_up_error',
        })
        throw e
      }
    },
    async _sendGuide(userQuery) {
      try {
        const decision = await resolveIntent({
          user_query: userQuery,
          page_route: null,
          source_envelopes: [],
          allow_model_candidate: false,
        })
        const options = Array.isArray(decision?.clarifying_options)
          ? decision.clarifying_options
          : []
        return this._pushAi(intentReply(decision), {
          kind: 'intent',
          decision,
          options,
        })
      } catch (e) {
        const msg = pickErrorMessage(e)
        this._pushAi(`意图识别失败：${msg}\n\n请确认后端已启动，或使用「+」技能栏。`, {
          kind: 'intent_error',
        })
        throw e
      }
    },
    clear() {
      this.messages = []
      this.materials = []
      this.contextText = ''
      this.contextFindings = []
      this.pendingQuestions = []
      this.lastTaskId = ''
      this._persist()
    },
  },
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useChatStore, import.meta.hot))
}