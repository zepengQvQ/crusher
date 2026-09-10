import { defineStore } from 'pinia'
import { EXAMPLES } from '../data/examples'

function quickAnalyze(text) {
  const findings = []
  if (/不保证收益|浮动收益|收益不确定/.test(text)) {
    findings.push({
      key: 'return_not_guaranteed',
      title: '收益不保证',
      severity: 'mid',
      desc: '产品收益随挂钩标的波动，宣传的收益水平并非保证。',
    })
  }
  if (/不支持提前赎回|不可赎回|不可提前支取/.test(text)) {
    findings.push({
      key: 'no_early_redemption',
      title: '不可提前赎回',
      severity: 'mid',
      desc: '产品到期前无法取回资金，存在流动性风险。',
    })
  }
  if (/不保证本金|本金亏损|本金损失/.test(text)) {
    findings.push({
      key: 'principal_not_guaranteed',
      title: '本金不保证',
      severity: 'high',
      desc: '产品不保本，可能面临本金亏损。',
    })
  }
  if (/逾期.*罚息|违约金.*%/.test(text)) {
    findings.push({
      key: 'punitive_fee',
      title: '违约金/罚息',
      severity: 'mid',
      desc: '逾期或提前还款会产生惩罚性费用。',
    })
  }
  if (/等待期.*不赔付|犹豫期后退保/.test(text)) {
    findings.push({
      key: 'period_limit',
      title: '时间限制条款',
      severity: 'low',
      desc: '等待期/犹豫期内的权益限制需注意。',
    })
  }
  const params = []
  const rateMatch = text.match(/(\d+\.?\d*)%/)
  if (rateMatch) {
    params.push({ key: 'rate', label: '提及利率/收益率', value: rateMatch[1] + '%' })
  }
  const daysMatch = text.match(/(\d+)天/)
  if (daysMatch) {
    params.push({ key: 'term', label: '产品期限', value: daysMatch[1] + '天' })
  }
  return { findings, params }
}

export const useCompareStore = defineStore('compare', {
  state: () => ({
    textA: '',
    textB: '',
    titleA: '条款 A',
    titleB: '条款 B',
  }),
  getters: {
    canCompare: (s) => s.textA.trim().length > 0 && s.textB.trim().length > 0,
    resultA: (s) => quickAnalyze(s.textA),
    resultB: (s) => quickAnalyze(s.textB),
    summary(state) {
      const a = quickAnalyze(state.textA)
      const b = quickAnalyze(state.textB)
      const aSeverityScore = a.findings.reduce(
        (s, f) => s + (f.severity === 'high' ? 3 : f.severity === 'mid' ? 2 : 1),
        0,
      )
      const bSeverityScore = b.findings.reduce(
        (s, f) => s + (f.severity === 'high' ? 3 : f.severity === 'mid' ? 2 : 1),
        0,
      )
      let winner = 'tie'
      let reason = '两份条款的风险发现数量和严重度相近。'
      if (aSeverityScore < bSeverityScore) {
        winner = 'A'
        reason = `条款 A 的风险评分更低（${aSeverityScore} vs ${bSeverityScore}），从风险角度更优。`
      } else if (bSeverityScore < aSeverityScore) {
        winner = 'B'
        reason = `条款 B 的风险评分更低（${bSeverityScore} vs ${aSeverityScore}），从风险角度更优。`
      }
      const uniqueInA = a.findings.filter((f) => !b.findings.some((x) => x.key === f.key))
      const uniqueInB = b.findings.filter((f) => !a.findings.some((x) => x.key === f.key))
      return {
        winner,
        reason,
        aSeverityScore,
        bSeverityScore,
        aFindingCount: a.findings.length,
        bFindingCount: b.findings.length,
        uniqueInA,
        uniqueInB,
      }
    },
  },
  actions: {
    setText(side, text, title) {
      if (side === 'A') {
        this.textA = text || ''
        if (title) this.titleA = title
      } else {
        this.textB = text || ''
        if (title) this.titleB = title
      }
    },
    fillExample(side, exampleId) {
      const ex = EXAMPLES.find((e) => e.id === exampleId)
      if (ex) {
        this.setText(side, ex.text, ex.name)
      }
    },
    clear(side) {
      if (side === 'A') {
        this.textA = ''
        this.titleA = '条款 A'
      } else {
        this.textB = ''
        this.titleB = '条款 B'
      }
    },
  },
})
