/** Demo 示例（与 data/examples.json 对齐的脱敏片段）。 */
export const EXAMPLES = [
  {
    id: 'structured_deposit',
    name: '结构性存款',
    text:
      '本产品为结构性存款，期限90天，挂钩美元兑日元汇率。若观察期内汇率始终位于145.00-155.00区间，则到期年化收益率4.80%；若突破区间，则到期年化收益率1.20%。',
  },
  {
    id: 'loan',
    name: '消费贷',
    text:
      '本贷款年化利率（单利）为7.20%，采用等额本息还款方式。若借款人未按期还款，逾期部分按日利率0.05%计收罚息，罚息利率为正常利率的2.5倍。逾期超过30天的，贷款人有权宣布贷款提前到期并要求一次性偿还全部本息。借款人提前还款需支付剩余本金3%的违约金。',
  },
  {
    id: 'safe',
    name: '安全文本（零风险）',
    text: '本说明书仅介绍营业网点地址与客服电话，不含任何收费或违约条款。',
  },
]

export const PRODUCT_OPTIONS = [
  { value: 'auto', text: '自动识别' },
  { value: 'structured_deposit', text: '结构性存款' },
  { value: 'loan', text: '借贷' },
]
