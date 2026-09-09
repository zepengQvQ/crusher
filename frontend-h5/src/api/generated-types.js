/**
 * 由 scripts/export_openapi.py 自动生成，勿手改。
 * 与 contracts/openapi.json / 后端 Pydantic 保持一致。
 * 更新命令：make export-openapi
 */

export const SCHEMA_NAMES = ["AnalysisReport", "AnalysisScope", "AnswerStatus", "ApiErrorDetail", "ApiErrorResponse", "Body_extract_document_api_v1_documents_extract_post", "CalculateScenarioRequest", "CalculationKind", "CalculationResult", "Claim", "ClaimComparison", "ClaimStatus", "ClaimSubject", "CreateAnalysisRequest", "CreateAnalysisResponse", "DayCountBasis", "DemoErrorKind", "DualAnalysisReport", "DualAnalysisRequest", "ErrorCode", "Evidence", "EvidenceAnswer", "EvidenceRef", "EvidenceSource", "ExtractedDocument", "FactStatus", "Finding", "FindingSeverity", "FollowUpRequest", "GeneralReference", "KeyParameter", "MissingDisclosure", "PageExtractResult", "PageExtractStatus", "ParameterKey", "PlainLanguage", "ProductCandidate", "ProductHint", "ProductRiskGrade", "ProductTypeId", "SourceDocument", "SourceType", "StageInfo", "StageStatus", "TaskResponse", "TaskStatus"]

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
 * @typedef {"answered"|"insufficient_evidence"|"out_of_scope"} AnswerStatusValue
 */

export const AnswerStatus = Object.freeze({
  answered: "answered",
  insufficient_evidence: "insufficient_evidence",
  out_of_scope: "out_of_scope",
})

/**
 * @typedef {"simple_return"|"fee"|"net_exit"} CalculationKindValue
 */

export const CalculationKind = Object.freeze({
  simple_return: "simple_return",
  fee: "fee",
  net_exit: "net_exit",
})

/**
 * @typedef {"confirmed"|"not_found"|"conflict"|"conditional"|"uncertain"} ClaimStatusValue
 */

export const ClaimStatus = Object.freeze({
  confirmed: "confirmed",
  not_found: "not_found",
  conflict: "conflict",
  conditional: "conditional",
  uncertain: "uncertain",
})

/**
 * @typedef {"expected_return"|"fee"|"early_exit"|"principal_protection"|"term"} ClaimSubjectValue
 */

export const ClaimSubject = Object.freeze({
  expected_return: "expected_return",
  fee: "fee",
  early_exit: "early_exit",
  principal_protection: "principal_protection",
  term: "term",
})

/**
 * @typedef {"360"|"365"} DayCountBasisValue
 */

export const DayCountBasis = Object.freeze({
  _360: "360",
  _365: "365",
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
 * @typedef {"INPUT_TOO_LONG"|"MODEL_TIMEOUT"|"RATE_LIMITED"|"INVALID_MODEL_JSON"|"RULE_FAILED"|"KNOWLEDGE_UNAVAILABLE"|"TASK_NOT_FOUND"|"FORBIDDEN_CLIENT_CONFIG"|"OCR_UNAVAILABLE"|"DOCUMENT_PARSE_FAILED"|"CALCULATION_INVALID"|"INTERNAL_ERROR"} ErrorCodeValue
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
  OCR_UNAVAILABLE: "OCR_UNAVAILABLE",
  DOCUMENT_PARSE_FAILED: "DOCUMENT_PARSE_FAILED",
  CALCULATION_INVALID: "CALCULATION_INVALID",
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
 * @typedef {"success"|"failed"|"blank"} PageExtractStatusValue
 */

export const PageExtractStatus = Object.freeze({
  success: "success",
  failed: "failed",
  blank: "blank",
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
 * @typedef {"sales_pitch"|"official_document"|"user_input"} SourceTypeValue
 */

export const SourceType = Object.freeze({
  sales_pitch: "sales_pitch",
  official_document: "official_document",
  user_input: "user_input",
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

/**
 * @typedef {Object} DualAnalysisRequest
 * @property {string} sales_text
 * @property {string} official_text
 * @property {ProductHintValue} [product_hint]
 * @property {string} [locale]
 */

/**
 * @typedef {Object} DualAnalysisReport
 * @property {SourceDocument} sales_source
 * @property {SourceDocument} official_source
 * @property {Array<ClaimComparison>} [comparisons]
 * @property {Array<string>} [pending_questions]
 * @property {string} [disclaimer]
 */

/**
 * @typedef {Object} ClaimComparison
 * @property {string} comparison_id
 * @property {ClaimSubjectValue} subject
 * @property {ClaimStatusValue} status
 * @property {string} summary
 * @property {Claim} [sales_claim]
 * @property {EvidenceRef} [official_evidence]
 * @property {string} [suggested_follow_up]
 */

/**
 * @typedef {Object} Claim
 * @property {string} claim_id
 * @property {ClaimSubjectValue} subject
 * @property {string} summary
 * @property {boolean} [negated]
 * @property {string} [numeric_value]
 * @property {"percent"|"bp"|"months"|"days"|"yuan"} [numeric_unit]
 * @property {EvidenceRef} evidence
 */

/**
 * @typedef {Object} SourceDocument
 * @property {string} [source_id]
 * @property {SourceTypeValue} source_type
 * @property {string} name
 * @property {string} text
 * @property {number} [pages]
 */

/**
 * @typedef {Object} EvidenceRef
 * @property {string} source_id
 * @property {string} quote
 * @property {number} start
 * @property {number} end
 * @property {number} [page]
 * @property {number} [confidence]
 * @property {boolean} [user_corrected]
 */

/**
 * @typedef {Object} ExtractedDocument
 * @property {string} [document_id]
 * @property {string} filename
 * @property {string} media_type
 * @property {StageStatusValue} overall_status
 * @property {Array<PageExtractResult>} [pages]
 * @property {string} [combined_text]
 * @property {Array<string>} [sensitive_hints]
 * @property {string} [message]
 */

/**
 * @typedef {Object} PageExtractResult
 * @property {number} page
 * @property {PageExtractStatusValue} status
 * @property {string} [text]
 * @property {number} [confidence]
 * @property {string} [error_message]
 * @property {boolean} [used_ocr]
 */

/**
 * @typedef {Object} FollowUpRequest
 * @property {string} question
 * @property {string} source_text
 * @property {Array<string>} [pending_questions]
 */

/**
 * @typedef {Object} EvidenceAnswer
 * @property {string} question
 * @property {AnswerStatusValue} status
 * @property {string} answer
 * @property {Array<EvidenceRef>} [evidence]
 * @property {Array<string>} [missing_info]
 */

/**
 * @typedef {Object} CalculateScenarioRequest
 * @property {CalculationKindValue} kind
 * @property {boolean} [user_confirmed]
 * @property {string} [principal]
 * @property {string} [annual_rate_percent]
 * @property {string} [days]
 * @property {DayCountBasisValue} [day_count_basis]
 * @property {string} [fee_base]
 * @property {string} [fee_rate_percent]
 * @property {string} [return_amount]
 * @property {string} [fee_amount]
 */

/**
 * @typedef {Object} CalculationResult
 * @property {CalculationKindValue} kind
 * @property {string} formula
 * @property {Object} [inputs]
 * @property {Array<string>} [assumptions]
 * @property {string} result
 * @property {string} [rounding]
 * @property {string} [disclaimer]
 */

/**
 * @typedef {Object} Body_extract_document_api_v1_documents_extract_post
 * @property {Array<string>} files
 */

