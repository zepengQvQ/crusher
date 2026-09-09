/**
 * 由 scripts/export_openapi.py 自动生成，勿手改。
 * 与 contracts/openapi.json / 后端 Pydantic 保持一致。
 * 更新命令：make export-openapi
 */

export const SCHEMA_NAMES = ["AnalysisReport", "AnalysisScope", "ApiErrorDetail", "ApiErrorResponse", "CreateAnalysisRequest", "CreateAnalysisResponse", "DemoErrorKind", "ErrorCode", "Evidence", "EvidenceSource", "FactStatus", "Finding", "FindingSeverity", "GeneralReference", "KeyParameter", "MissingDisclosure", "ParameterKey", "PlainLanguage", "ProductCandidate", "ProductHint", "ProductRiskGrade", "ProductTypeId", "StageInfo", "StageStatus", "TaskResponse", "TaskStatus"]

export const MAX_INPUT_CHARS = 8000

export const DISCLAIMER = '本 Demo 不进行用户适当性评估，不构成投资建议。'

/**
 * @typedef {"supported"|"out_of_scope"|"needs_confirmation"} AnalysisScopeValue
 */

export const AnalysisScope = Object.freeze({
  supported: "supported",
  out_of_scope: "out_of_scope",
  needs_confirmation: "needs_confirmation",
})

/**
 * @typedef {"model_timeout"|"invalid_json"|"rate_limited"} DemoErrorKindValue
 */

export const DemoErrorKind = Object.freeze({
  model_timeout: "model_timeout",
  invalid_json: "invalid_json",
  rate_limited: "rate_limited",
})

/**
 * @typedef {"INPUT_TOO_LONG"|"MODEL_TIMEOUT"|"RATE_LIMITED"|"INVALID_MODEL_JSON"|"RULE_FAILED"|"KNOWLEDGE_UNAVAILABLE"|"TASK_NOT_FOUND"|"FORBIDDEN_CLIENT_CONFIG"|"INTERNAL_ERROR"} ErrorCodeValue
 */

export const ErrorCode = Object.freeze({
  INPUT_TOO_LONG: "INPUT_TOO_LONG",
  MODEL_TIMEOUT: "MODEL_TIMEOUT",
  RATE_LIMITED: "RATE_LIMITED",
  INVALID_MODEL_JSON: "INVALID_MODEL_JSON",
  RULE_FAILED: "RULE_FAILED",
  KNOWLEDGE_UNAVAILABLE: "KNOWLEDGE_UNAVAILABLE",
  TASK_NOT_FOUND: "TASK_NOT_FOUND",
  FORBIDDEN_CLIENT_CONFIG: "FORBIDDEN_CLIENT_CONFIG",
  INTERNAL_ERROR: "INTERNAL_ERROR",
})

/**
 * @typedef {"input_text"|"knowledge"} EvidenceSourceValue
 */

export const EvidenceSource = Object.freeze({
  input_text: "input_text",
  knowledge: "knowledge",
})

/**
 * @typedef {"document_fact"|"calculated_fact"|"general_reference"|"not_disclosed"|"unknown"} FactStatusValue
 */

export const FactStatus = Object.freeze({
  document_fact: "document_fact",
  calculated_fact: "calculated_fact",
  general_reference: "general_reference",
  not_disclosed: "not_disclosed",
  unknown: "unknown",
})

/**
 * @typedef {"high"|"mid"|"low"} FindingSeverityValue
 */

export const FindingSeverity = Object.freeze({
  high: "high",
  mid: "mid",
  low: "low",
})

/**
 * @typedef {"term"|"expected_return"|"early_redemption"|"fee_structure"|"principal_protection"|"product_risk_grade"|"amount"|"annual_interest_rate"|"repayment_method"|"penalty_interest"|"prepayment_fee"} ParameterKeyValue
 */

export const ParameterKey = Object.freeze({
  term: "term",
  expected_return: "expected_return",
  early_redemption: "early_redemption",
  fee_structure: "fee_structure",
  principal_protection: "principal_protection",
  product_risk_grade: "product_risk_grade",
  amount: "amount",
  annual_interest_rate: "annual_interest_rate",
  repayment_method: "repayment_method",
  penalty_interest: "penalty_interest",
  prepayment_fee: "prepayment_fee",
})

/**
 * @typedef {"auto"|"structured_deposit"|"loan"} ProductHintValue
 */

export const ProductHint = Object.freeze({
  auto: "auto",
  structured_deposit: "structured_deposit",
  loan: "loan",
})

/**
 * @typedef {"structured_deposit"|"loan"|"snowball"|"insurance"|"fund"|"unknown"} ProductTypeIdValue
 */

export const ProductTypeId = Object.freeze({
  structured_deposit: "structured_deposit",
  loan: "loan",
  snowball: "snowball",
  insurance: "insurance",
  fund: "fund",
  unknown: "unknown",
})

/**
 * @typedef {"success"|"partial"|"failed"|"not_applicable"} StageStatusValue
 */

export const StageStatus = Object.freeze({
  success: "success",
  partial: "partial",
  failed: "failed",
  not_applicable: "not_applicable",
})

/**
 * @typedef {"queued"|"running"|"completed"|"failed"} TaskStatusValue
 */

export const TaskStatus = Object.freeze({
  queued: "queued",
  running: "running",
  completed: "completed",
  failed: "failed",
})

/**
 * @typedef {Object} CreateAnalysisRequest
 * @property {string} text
 * @property {ProductHintValue} [product_hint]
 * @property {string} [locale]
 * @property {DemoErrorKindValue} [demo_error]
 */

/**
 * @typedef {Object} CreateAnalysisResponse
 * @property {string} task_id
 * @property {TaskStatusValue} task_status
 */

/**
 * @typedef {Object} TaskResponse
 * @property {string} task_id
 * @property {TaskStatusValue} task_status
 * @property {string} created_at
 * @property {string} updated_at
 * @property {Array<StageInfo>} stages
 * @property {ErrorCodeValue} [error_code]
 * @property {string} [error_message]
 * @property {AnalysisReport} [report]
 * @property {boolean} [is_failure]
 * @property {string} [source_text]
 * @property {ProductHintValue} [product_hint]
 * @property {ProductTypeIdValue} [resolved_product_type]
 * @property {AnalysisScopeValue} [analysis_scope]
 */

/**
 * @typedef {Object} AnalysisReport
 * @property {Array<ProductCandidate>} [product_candidates]
 * @property {ProductTypeIdValue} [resolved_product_type]
 * @property {AnalysisScopeValue} [analysis_scope]
 * @property {string} [scope_reason]
 * @property {ProductRiskGrade} product_risk_grade
 * @property {PlainLanguage} plain_language
 * @property {Array<KeyParameter>} [key_parameters]
 * @property {Array<Finding>} [findings]
 * @property {Array<MissingDisclosure>} [missing_disclosures]
 * @property {Array<GeneralReference>} [general_references]
 * @property {Array<string>} [pending_questions]
 * @property {string} [disclaimer]
 */

/**
 * @typedef {Object} Finding
 * @property {string} id
 * @property {string} title
 * @property {FindingSeverityValue} finding_severity
 * @property {string} explanation
 * @property {Array<Evidence>} evidence
 * @property {string} rule_or_knowledge_id
 * @property {number} confidence
 * @property {boolean} [needs_review]
 */

/**
 * @typedef {Object} Evidence
 * @property {string} quote
 * @property {number} start
 * @property {number} end
 * @property {EvidenceSourceValue} [source]
 */

/**
 * @typedef {Object} KeyParameter
 * @property {ParameterKeyValue} key
 * @property {string} label
 * @property {string} [value]
 * @property {FactStatusValue} status
 * @property {string} [amount]
 */

/**
 * @typedef {Object} ProductCandidate
 * @property {ProductTypeIdValue} product_type_id
 * @property {string} product_type_name
 * @property {number} confidence
 * @property {Array<string>} [evidence_quotes]
 */

/**
 * @typedef {Object} ProductRiskGrade
 * @property {string} [value]
 * @property {FactStatusValue} status
 * @property {string} [note]
 */

/**
 * @typedef {Object} PlainLanguage
 * @property {string} text
 * @property {StageStatusValue} [status]
 */

/**
 * @typedef {Object} MissingDisclosure
 * @property {ParameterKeyValue} key
 * @property {string} question
 */

/**
 * @typedef {Object} GeneralReference
 * @property {FactStatusValue} [status]
 * @property {string} text
 * @property {string} source
 */

/**
 * @typedef {Object} StageInfo
 * @property {string} name
 * @property {StageStatusValue} status
 * @property {string} [message]
 */

/**
 * @typedef {Object} ApiErrorDetail
 * @property {string} error_code
 * @property {string} message
 * @property {Array<string>} [fields]
 * @property {number} [max_input_chars]
 */

/**
 * @typedef {Object} ApiErrorResponse
 * @property {ApiErrorDetail} detail
 */

