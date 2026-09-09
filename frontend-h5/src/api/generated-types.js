/**
 * 由 scripts/export_openapi.py 自动生成，勿手改。
 * 与 contracts/openapi.json / 后端 Pydantic 保持一致。
 * 更新命令：make export-openapi
 */

export const SCHEMA_NAMES = ["AnalysisReport", "AnalysisScope", "CreateAnalysisRequest", "CreateAnalysisResponse", "DemoErrorKind", "ErrorCode", "Evidence", "EvidenceSource", "FactStatus", "Finding", "FindingSeverity", "GeneralReference", "HTTPValidationError", "KeyParameter", "MissingDisclosure", "ParameterKey", "PlainLanguage", "ProductCandidate", "ProductHint", "ProductRiskGrade", "ProductTypeId", "StageInfo", "StageStatus", "TaskResponse", "TaskStatus", "ValidationError"]

export const DISCLAIMER = '本 Demo 不进行用户适当性评估，不构成投资建议。'

export const AnalysisScope = Object.freeze({
  supported: "supported",
  out_of_scope: "out_of_scope",
  needs_confirmation: "needs_confirmation",
})

export const DemoErrorKind = Object.freeze({
  model_timeout: "model_timeout",
  invalid_json: "invalid_json",
  rate_limited: "rate_limited",
})

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

export const EvidenceSource = Object.freeze({
  input_text: "input_text",
  knowledge: "knowledge",
})

export const FactStatus = Object.freeze({
  document_fact: "document_fact",
  calculated_fact: "calculated_fact",
  general_reference: "general_reference",
  not_disclosed: "not_disclosed",
  unknown: "unknown",
})

export const FindingSeverity = Object.freeze({
  high: "high",
  mid: "mid",
  low: "low",
})

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

export const ProductHint = Object.freeze({
  auto: "auto",
  structured_deposit: "structured_deposit",
  loan: "loan",
})

export const ProductTypeId = Object.freeze({
  structured_deposit: "structured_deposit",
  loan: "loan",
  snowball: "snowball",
  insurance: "insurance",
  fund: "fund",
  unknown: "unknown",
})

export const StageStatus = Object.freeze({
  success: "success",
  partial: "partial",
  failed: "failed",
  not_applicable: "not_applicable",
})

export const TaskStatus = Object.freeze({
  queued: "queued",
  running: "running",
  completed: "completed",
  failed: "failed",
})

/**
 * @typedef CreateAnalysisRequest
 * @property {string} text
 * @property {ProductHint} [optional] product_hint
 * @property {string} [optional] locale
 * @property {DemoErrorKind} [optional] demo_error
 */

/**
 * @typedef CreateAnalysisResponse
 * @property {string} task_id
 * @property {TaskStatus} task_status
 */

/**
 * @typedef TaskResponse
 * @property {string} task_id
 * @property {TaskStatus} task_status
 * @property {string} created_at
 * @property {string} updated_at
 * @property {Array<StageInfo>} stages
 * @property {ErrorCode} [optional] error_code
 * @property {string} [optional] error_message
 * @property {AnalysisReport} [optional] report
 * @property {boolean} [optional] is_failure
 * @property {string} [optional] source_text
 * @property {ProductHint} [optional] product_hint
 * @property {ProductTypeId} [optional] resolved_product_type
 * @property {AnalysisScope} [optional] analysis_scope
 */

/**
 * @typedef AnalysisReport
 * @property {Array<ProductCandidate>} [optional] product_candidates
 * @property {ProductTypeId} [optional] resolved_product_type
 * @property {AnalysisScope} [optional] analysis_scope
 * @property {string} [optional] scope_reason
 * @property {ProductRiskGrade} product_risk_grade
 * @property {PlainLanguage} plain_language
 * @property {Array<KeyParameter>} [optional] key_parameters
 * @property {Array<Finding>} [optional] findings
 * @property {Array<MissingDisclosure>} [optional] missing_disclosures
 * @property {Array<GeneralReference>} [optional] general_references
 * @property {Array<string>} [optional] pending_questions
 * @property {string} [optional] disclaimer
 */

/**
 * @typedef Finding
 * @property {string} id
 * @property {string} title
 * @property {FindingSeverity} finding_severity
 * @property {string} explanation
 * @property {Array<Evidence>} evidence
 * @property {string} rule_or_knowledge_id
 * @property {number} confidence
 * @property {boolean} [optional] needs_review
 */

/**
 * @typedef Evidence
 * @property {string} quote
 * @property {number} start
 * @property {number} end
 * @property {EvidenceSource} [optional] source
 */

/**
 * @typedef KeyParameter
 * @property {ParameterKey} key
 * @property {string} label
 * @property {string} [optional] value
 * @property {FactStatus} status
 * @property {string} [optional] amount
 */

/**
 * @typedef ProductCandidate
 * @property {ProductTypeId} product_type_id
 * @property {string} product_type_name
 * @property {number} confidence
 * @property {Array<string>} [optional] evidence_quotes
 */

/**
 * @typedef ProductRiskGrade
 * @property {string} [optional] value
 * @property {FactStatus} status
 * @property {string} [optional] note
 */

/**
 * @typedef PlainLanguage
 * @property {string} text
 * @property {StageStatus} [optional] status
 */

/**
 * @typedef MissingDisclosure
 * @property {ParameterKey} key
 * @property {string} question
 */

/**
 * @typedef GeneralReference
 * @property {FactStatus} [optional] status
 * @property {string} text
 * @property {string} source
 */

/**
 * @typedef StageInfo
 * @property {string} name
 * @property {StageStatus} status
 * @property {string} [optional] message
 */

/**
 * @typedef HTTPValidationError
 * @property {Array<ValidationError>} [optional] detail
 */

/**
 * @typedef ValidationError
 * @property {Array<string|number>} loc
 * @property {string} msg
 * @property {string} type
 * @property {any} [optional] input
 * @property {Object} [optional] ctx
 */

