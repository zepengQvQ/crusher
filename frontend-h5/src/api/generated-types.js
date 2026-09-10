/**
 * 由 scripts/export_openapi.py 自动生成，勿手改。
 * 与 contracts/openapi.json / 后端 Pydantic 保持一致。
 * 更新命令：make export-openapi
 */

export const SCHEMA_NAMES = ["AnalysisCoverage", "AnalysisReport", "AnalysisRevision", "AnalysisScope", "AnswerControl", "AnswerStatus", "ApiErrorDetail", "ApiErrorResponse", "Body_extract_document_api_v1_documents_extract_post", "CalculateScenarioRequest", "CalculationKind", "CalculationResult", "Claim", "ClaimComparison", "ClaimStatus", "ClaimSubject", "ClarificationAnswer", "ClarifyingOption", "ClarifyingQuestion", "CompletenessCheckRequest", "CompletenessResult", "CorrectionItem", "CorrectionKind", "CorrectionRecord", "CorrectionRequest", "CreateAnalysisRequest", "CreateAnalysisResponse", "DayCountBasis", "DecisionSource", "DecisionStatus", "DemoErrorKind", "DiffStatus", "DimensionComparison", "DualAnalysisReport", "DualAnalysisRequest", "ErrorCode", "Evidence", "EvidenceAnswer", "EvidenceRef", "EvidenceSource", "ExtractedDocument", "ExtractorSource", "FactEvidenceRef", "FactPolarity", "FactSideValue", "FactStatus", "FieldStatus", "FinancialFact", "FinancialFactStatus", "Finding", "FindingSeverity", "FollowUpRequest", "GapKind", "GeneralReference", "IntentDecision", "IntentOption", "IntentResolveRequest", "IntentType", "KeyParameter", "MissingDisclosure", "PageExtractResult", "PageExtractStatus", "ParameterKey", "PlainLanguage", "ProductCandidate", "ProductCompareRequest", "ProductComparisonReport", "ProductFactDimension", "ProductFacts", "ProductHint", "ProductRiskGrade", "ProductTypeId", "PublicationDecision", "PublicationOutcome", "SourceDocument", "SourceEnvelope", "SourceRole", "SourceType", "StageInfo", "StageStatus", "TaskResponse", "TaskStatus", "ValueKind"]

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
 * @typedef {"buttons"|"enum"|"free_text"} AnswerControlValue
 */

export const AnswerControl = Object.freeze({
  buttons: "buttons",
  enum: "enum",
  free_text: "free_text",
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
 * @typedef {"source_text"|"product_type"|"fact_value"} CorrectionKindValue
 */

export const CorrectionKind = Object.freeze({
  source_text: "source_text",
  product_type: "product_type",
  fact_value: "fact_value",
})

/**
 * @typedef {"360"|"365"} DayCountBasisValue
 */

export const DayCountBasis = Object.freeze({
  _360: "360",
  _365: "365",
})

/**
 * @typedef {"explicit_ui"|"api_route"|"rule"|"model_candidate"} DecisionSourceValue
 */

export const DecisionSource = Object.freeze({
  explicit_ui: "explicit_ui",
  api_route: "api_route",
  rule: "rule",
  model_candidate: "model_candidate",
})

/**
 * @typedef {"resolved"|"needs_clarification"|"rejected"} DecisionStatusValue
 */

export const DecisionStatus = Object.freeze({
  resolved: "resolved",
  needs_clarification: "needs_clarification",
  rejected: "rejected",
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
 * @typedef {"same"|"different"|"missing_a"|"missing_b"|"both_missing"|"incomparable"} DiffStatusValue
 */

export const DiffStatus = Object.freeze({
  same: "same",
  different: "different",
  missing_a: "missing_a",
  missing_b: "missing_b",
  both_missing: "both_missing",
  incomparable: "incomparable",
})

/**
 * @typedef {"INPUT_TOO_LONG"|"MODEL_TIMEOUT"|"RATE_LIMITED"|"INVALID_MODEL_JSON"|"MODEL_OUTPUT_INVALID"|"OUTPUT_VERIFICATION_FAILED"|"RULE_FAILED"|"KNOWLEDGE_UNAVAILABLE"|"TASK_NOT_FOUND"|"FORBIDDEN_CLIENT_CONFIG"|"OCR_UNAVAILABLE"|"DOCUMENT_PARSE_FAILED"|"CALCULATION_INVALID"|"INTENT_AMBIGUOUS"|"INPUT_INCOMPLETE"|"PRODUCT_CONFLICT"|"INSUFFICIENT_EVIDENCE"|"UNSUPPORTED_REQUEST"|"INTERNAL_ERROR"} ErrorCodeValue
 */

export const ErrorCode = Object.freeze({
  INPUT_TOO_LONG: "INPUT_TOO_LONG",
  MODEL_TIMEOUT: "MODEL_TIMEOUT",
  RATE_LIMITED: "RATE_LIMITED",
  INVALID_MODEL_JSON: "INVALID_MODEL_JSON",
  MODEL_OUTPUT_INVALID: "MODEL_OUTPUT_INVALID",
  OUTPUT_VERIFICATION_FAILED: "OUTPUT_VERIFICATION_FAILED",
  RULE_FAILED: "RULE_FAILED",
  KNOWLEDGE_UNAVAILABLE: "KNOWLEDGE_UNAVAILABLE",
  TASK_NOT_FOUND: "TASK_NOT_FOUND",
  FORBIDDEN_CLIENT_CONFIG: "FORBIDDEN_CLIENT_CONFIG",
  OCR_UNAVAILABLE: "OCR_UNAVAILABLE",
  DOCUMENT_PARSE_FAILED: "DOCUMENT_PARSE_FAILED",
  CALCULATION_INVALID: "CALCULATION_INVALID",
  INTENT_AMBIGUOUS: "INTENT_AMBIGUOUS",
  INPUT_INCOMPLETE: "INPUT_INCOMPLETE",
  PRODUCT_CONFLICT: "PRODUCT_CONFLICT",
  INSUFFICIENT_EVIDENCE: "INSUFFICIENT_EVIDENCE",
  UNSUPPORTED_REQUEST: "UNSUPPORTED_REQUEST",
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
 * @typedef {"RULE"|"MODEL_CANDIDATE"|"USER_CORRECTION"} ExtractorSourceValue
 */

export const ExtractorSource = Object.freeze({
  RULE: "RULE",
  MODEL_CANDIDATE: "MODEL_CANDIDATE",
  USER_CORRECTION: "USER_CORRECTION",
})

/**
 * @typedef {"affirmative"|"negative"|"contrastive"} FactPolarityValue
 */

export const FactPolarity = Object.freeze({
  affirmative: "affirmative",
  negative: "negative",
  contrastive: "contrastive",
})

/**
 * @typedef {"document_fact"|"calculated_fact"|"general_reference"|"not_disclosed"|"user_asserted"|"unknown"} FactStatusValue
 */

export const FactStatus = Object.freeze({
  document_fact: "document_fact",
  calculated_fact: "calculated_fact",
  general_reference: "general_reference",
  not_disclosed: "not_disclosed",
  user_asserted: "user_asserted",
  unknown: "unknown",
})

/**
 * @typedef {"confirmed"|"missing"|"conflicting"|"uncertain"} FieldStatusValue
 */

export const FieldStatus = Object.freeze({
  confirmed: "confirmed",
  missing: "missing",
  conflicting: "conflicting",
  uncertain: "uncertain",
})

/**
 * @typedef {"CONFIRMED"|"UNCERTAIN"|"NOT_DISCLOSED"} FinancialFactStatusValue
 */

export const FinancialFactStatus = Object.freeze({
  CONFIRMED: "CONFIRMED",
  UNCERTAIN: "UNCERTAIN",
  NOT_DISCLOSED: "NOT_DISCLOSED",
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
 * @typedef {"field_missing"|"not_disclosed"|"ocr_unrecognized"|"value_conflict"|"user_unconfirmed"} GapKindValue
 */

export const GapKind = Object.freeze({
  field_missing: "field_missing",
  not_disclosed: "not_disclosed",
  ocr_unrecognized: "ocr_unrecognized",
  value_conflict: "value_conflict",
  user_unconfirmed: "user_unconfirmed",
})

/**
 * @typedef {"single_analysis"|"dual_source_compare"|"product_compare"|"calculation"|"evidence_follow_up"|"document_extract"|"unsupported"|"ambiguous"} IntentTypeValue
 */

export const IntentType = Object.freeze({
  single_analysis: "single_analysis",
  dual_source_compare: "dual_source_compare",
  product_compare: "product_compare",
  calculation: "calculation",
  evidence_follow_up: "evidence_follow_up",
  document_extract: "document_extract",
  unsupported: "unsupported",
  ambiguous: "ambiguous",
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
 * @typedef {"product_type"|"term"|"amount"|"return_or_rate"|"early_exit"|"fees"|"principal_protection"|"main_risks"|"undisclosed"} ProductFactDimensionValue
 */

export const ProductFactDimension = Object.freeze({
  product_type: "product_type",
  term: "term",
  amount: "amount",
  return_or_rate: "return_or_rate",
  early_exit: "early_exit",
  fees: "fees",
  principal_protection: "principal_protection",
  main_risks: "main_risks",
  undisclosed: "undisclosed",
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
 * @typedef {"publish"|"publish_partial"|"clarify"|"refuse"} PublicationOutcomeValue
 */

export const PublicationOutcome = Object.freeze({
  publish: "publish",
  publish_partial: "publish_partial",
  clarify: "clarify",
  refuse: "refuse",
})

/**
 * @typedef {"sales_pitch"|"official_document"|"user_supplement"|"unknown"} SourceRoleValue
 */

export const SourceRole = Object.freeze({
  sales_pitch: "sales_pitch",
  official_document: "official_document",
  user_supplement: "user_supplement",
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
 * @typedef {"amount"|"percent"|"term"|"text"|"fee"} ValueKindValue
 */

export const ValueKind = Object.freeze({
  amount: "amount",
  percent: "percent",
  term: "term",
  text: "text",
  fee: "fee",
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
 * @property {PublicationDecision} [publication]
 * @property {string} [parent_task_id]
 * @property {AnalysisRevision} [revision]
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
 * @property {PublicationDecision} [publication]
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
 * @property {Array<FinancialFact>} [sales_financial_facts]
 * @property {Array<FinancialFact>} [official_financial_facts]
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
 * @typedef {Object} ProductCompareRequest
 * @property {string} text_a
 * @property {string} text_b
 * @property {ProductHintValue} [product_hint_a]
 * @property {ProductHintValue} [product_hint_b]
 * @property {string} [label_a]
 * @property {string} [label_b]
 * @property {string} [locale]
 */

/**
 * @typedef {Object} ProductComparisonReport
 * @property {ProductFacts} product_a
 * @property {ProductFacts} product_b
 * @property {Array<DimensionComparison>} [dimensions]
 * @property {string} [disclaimer]
 */

/**
 * @typedef {Object} DimensionComparison
 * @property {ProductFactDimensionValue} dimension
 * @property {string} label
 * @property {DiffStatusValue} status
 * @property {FactSideValue} side_a
 * @property {FactSideValue} side_b
 * @property {string} [note]
 */

/**
 * @typedef {Object} ProductFacts
 * @property {string} product_id
 * @property {string} label
 * @property {ProductTypeIdValue} [product_type]
 * @property {string} source_text
 */

/**
 * @typedef {Object} FactSideValue
 * @property {string} [display]
 * @property {string} [normalized]
 * @property {FieldStatusValue} [status]
 * @property {Array<EvidenceRef>} [evidence]
 * @property {string} [nature]
 */

/**
 * @typedef {Object} IntentResolveRequest
 * @property {string} [user_query]
 * @property {IntentTypeValue} [explicit_intent]
 * @property {string} [page_route]
 * @property {Array<SourceEnvelope>} [source_envelopes]
 * @property {boolean} [allow_model_candidate]
 */

/**
 * @typedef {Object} IntentDecision
 * @property {IntentTypeValue} intent
 * @property {DecisionStatusValue} status
 * @property {DecisionSourceValue} source
 * @property {Array<string>} [rationale]
 * @property {Array<string>} [missing]
 * @property {Array<IntentOption>} [clarifying_options]
 * @property {string} [use_case_key]
 */

/**
 * @typedef {Object} IntentOption
 * @property {IntentTypeValue} intent
 * @property {string} label
 * @property {string} [reason]
 */

/**
 * @typedef {Object} SourceEnvelope
 * @property {string} source_id
 * @property {SourceRoleValue} [role]
 * @property {string} text
 * @property {boolean} [user_corrected]
 * @property {string} [content_hash]
 */

/**
 * @typedef {Object} CompletenessCheckRequest
 * @property {IntentTypeValue} intent
 * @property {Array<SourceEnvelope>} [source_envelopes]
 * @property {ProductHintValue} [product_hint]
 * @property {CalculationKindValue} [calculation_kind]
 * @property {string} [principal]
 * @property {string} [annual_rate_percent]
 * @property {string} [days]
 * @property {DayCountBasisValue} [day_count_basis]
 * @property {string} [fee_base]
 * @property {string} [fee_rate_percent]
 * @property {string} [return_amount]
 * @property {string} [fee_amount]
 * @property {boolean} [user_confirmed_calculation]
 * @property {string} [follow_up_question]
 * @property {string} [bound_source_id]
 * @property {Array<string>} [document_file_names]
 * @property {number} [document_bytes_total]
 * @property {number} [document_page_count]
 * @property {Array<ClarificationAnswer>} [clarification_answers]
 */

/**
 * @typedef {Object} CompletenessResult
 * @property {IntentTypeValue} intent
 * @property {boolean} can_continue
 * @property {Array<ClarifyingQuestion>} [questions]
 * @property {string} [summary]
 * @property {Array<ClarificationAnswer>} [answered]
 */

/**
 * @typedef {Object} ClarifyingQuestion
 * @property {string} question_id
 * @property {string} prompt
 * @property {GapKindValue} gap_kind
 * @property {AnswerControlValue} [control]
 * @property {Array<ClarifyingOption>} [options]
 * @property {number} [blocking_priority]
 */

/**
 * @typedef {Object} AnalysisCoverage
 * @property {Array<string>} [checked]
 * @property {Array<string>} [not_checked]
 */

/**
 * @typedef {Object} AnalysisRevision
 * @property {number} revision_no
 * @property {string} parent_task_id
 * @property {Array<CorrectionRecord>} corrections
 * @property {string} [created_at]
 * @property {string} [note]
 */

/**
 * @typedef {Object} Body_extract_document_api_v1_documents_extract_post
 * @property {Array<string>} files
 */

/**
 * @typedef {Object} ClarificationAnswer
 * @property {string} question_id
 * @property {string} value
 */

/**
 * @typedef {Object} ClarifyingOption
 * @property {string} value
 * @property {string} label
 */

/**
 * @typedef {Object} CorrectionItem
 * @property {CorrectionKindValue} kind
 * @property {string} [corrected_text]
 * @property {ProductHintValue} [product_type]
 * @property {ParameterKeyValue} [parameter_key]
 * @property {string} [corrected_value]
 * @property {string} [previous_value]
 */

/**
 * @typedef {Object} CorrectionRecord
 * @property {string} [correction_id]
 * @property {CorrectionKindValue} kind
 * @property {string} [previous_value]
 * @property {string} new_value
 * @property {ParameterKeyValue} [parameter_key]
 * @property {string} [created_at]
 */

/**
 * @typedef {Object} CorrectionRequest
 * @property {Array<CorrectionItem>} corrections
 * @property {string} [note]
 */

/**
 * @typedef {Object} FactEvidenceRef
 * @property {string} quote
 * @property {number} start
 * @property {number} end
 */

/**
 * @typedef {Object} FinancialFact
 * @property {string} fact_id
 * @property {string} [product_id]
 * @property {string} field_key
 * @property {string} raw_value
 * @property {string} [normalized_value]
 * @property {string} [unit]
 * @property {ValueKindValue} value_kind
 * @property {FactPolarityValue} [polarity]
 * @property {Array<string>} [qualifiers]
 * @property {string} [condition_text]
 * @property {FinancialFactStatusValue} status
 * @property {Array<FactEvidenceRef>} [evidence_refs]
 * @property {ExtractorSourceValue} [extractor_source]
 * @property {string} [negated_raw_value]
 */

/**
 * @typedef {Object} PublicationDecision
 * @property {PublicationOutcomeValue} outcome
 * @property {ErrorCodeValue} [reason_code]
 * @property {string} user_reason
 * @property {Array<string>} [next_steps]
 * @property {AnalysisCoverage} [coverage]
 */

