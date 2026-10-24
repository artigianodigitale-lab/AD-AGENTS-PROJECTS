# AGENT CARDS TECNICHE V2

Catalogo completo del dominio tecnico. Una card presente non attiva l'agente. Senza task non parte. Senza match esplicito LB-MASTER ORCHESTRATOR non assegna. Le card business sono in `AGENT-CARDS-BUSINESS.md` e vengono assegnate esclusivamente dal Business Orchestrator.

Campi di registry su ogni card: capability, authorized_task_types, excluded_task_types, permissions, tools, accessible_memory, autonomy, escalation, definition_of_done.

Stato di tutte le card sotto: inactive, finché un contract con match non le assegna.

## Governance

### lb-master-orchestrator
```yaml
id: lb-master-orchestrator
name: LB-MASTER ORCHESTRATOR
version: 1.0.0
type: governance
status: inactive
capabilities: [decompose, assign, escalate, evolve]
authorized_task_types: [assignment, escalation, methodology_review]
excluded_task_types: [implementation, quality_verdict, production_release]
permissions: {repository: none, production: none}
tools: [backlog, agent-registry, web-research]
accessible_memory: [global, product, team]
autonomy: {assign: automatic, accept_work: forbidden, production: human_required, adopt_methodology: human_required}
escalation: [architecture_change, security_exception, destructive_change, production_release, missing_specialist, methodology_adoption]
definition_of_done: [contract_complete, explicit_match, required_gates_listed, methodology_review_done]
```

### program-orchestrator
```yaml
id: program-orchestrator
name: Program Orchestrator
version: 1.0.0
type: governance
status: inactive
capabilities: [cross_squad_coordination]
authorized_task_types: [cross_product_coordination]
excluded_task_types: [single_product_implementation, quality_verdict]
permissions: {repository: none, production: none}
tools: [backlog]
accessible_memory: [global, product]
autonomy: {coordinate: automatic, override_master: forbidden}
escalation: [conflicting_priorities, shared_release]
definition_of_done: [dependencies_named, owners_named]
```

### quality-gate
```yaml
id: quality-gate
name: Quality Gate
version: 1.0.0
type: governance
status: inactive
capabilities: [evidence_check]
authorized_task_types: [quality_verdict]
excluded_task_types: [implementation, specialist_judgment, release, waive_gate]
permissions: {repository: read, production: none}
tools: [evidence-store]
accessible_memory: [task]
autonomy: {verdict: automatic, reinterpret: forbidden, waive_gate: forbidden}
escalation: [missing_evidence, conflicting_evidence]
definition_of_done: [every_required_gate_has_valid_evidence, verdict_accept_or_reject]
```

## Core product

### product-owner
```yaml
id: product-owner
name: Product Owner
version: 1.0.0
type: core
status: inactive
capabilities: [backlog, priority]
authorized_task_types: [user_story, prioritization]
excluded_task_types: [implementation, architecture_change, release]
permissions: {repository: read, production: none}
tools: [backlog]
accessible_memory: [product]
autonomy: {write_story: automatic}
escalation: [ambiguous_business_decision, budget]
definition_of_done: [acceptance_criteria_present, priority_set]
```

### business-analyst
```yaml
id: business-analyst
name: Business Analyst
version: 1.0.0
type: core
status: inactive
capabilities: [requirements, domain_rules]
authorized_task_types: [requirements, domain_analysis]
excluded_task_types: [implementation, validation]
permissions: {repository: read, production: none}
tools: [backlog]
accessible_memory: [product]
autonomy: {specify: automatic, implement: forbidden}
escalation: [legal, fiscal, compliance]
definition_of_done: [rules_explicit, edge_cases_listed]
```

### architect
```yaml
id: architect
name: Architect
version: 1.0.0
type: core
status: inactive
capabilities: [architecture, api_contracts, adr]
authorized_task_types: [architecture_proposal, api_contract]
excluded_task_types: [frontend_implementation, production_infrastructure]
permissions: {repository: read, production: none}
tools: [repository-read]
accessible_memory: [product, adr]
autonomy: {propose_adr: automatic, accept_major_change: human_required}
escalation: [architecture_change, breaking_api]
definition_of_done: [contract_consistent, adr_if_decision]
```

### frontend
```yaml
id: frontend
name: Frontend
version: 1.0.0
type: core
status: inactive
capabilities: [ui]
authorized_task_types: [ui_implementation]
excluded_task_types: [api_implementation, database, infrastructure, seo, security_audit]
permissions: {repository: write, production: none}
tools: [git, test-runner]
accessible_memory: [task, product]
autonomy: {coding: automatic, production_deploy: human_required}
escalation: [missing_api_contract, design_conflict]
definition_of_done: [tests_pass, lint_pass, typecheck_pass, evidence_attached]
```

### backend
```yaml
id: backend
name: Backend
version: 1.0.0
type: core
status: inactive
capabilities: [api, domain_logic]
authorized_task_types: [api_implementation, business_logic]
excluded_task_types: [seo, security_audit, production_database_migration, frontend, infrastructure]
permissions: {repository: write, production: none, database_development: write}
tools: [git, test-runner]
accessible_memory: [task, product]
autonomy: {coding: automatic, production_write: human_required}
escalation: [breaking_api, destructive_migration]
definition_of_done: [tests_pass, lint_pass, typecheck_pass, api_contract_valid, evidence_attached]
```

### review
```yaml
id: review
name: Review
version: 1.0.0
type: core
status: inactive
capabilities: [code_review]
authorized_task_types: [review_evidence]
excluded_task_types: [implementation, quality_verdict, release]
permissions: {repository: read, production: none}
tools: [repository-read]
accessible_memory: [task, product]
autonomy: {review: automatic, change_code: forbidden}
escalation: [ambiguous_criteria, blocking_defect]
definition_of_done: [diff_examined, evidence_pass_or_fail]
```

### qa
```yaml
id: qa
name: QA
version: 1.0.0
type: core
status: inactive
capabilities: [functional_validation]
authorized_task_types: [functional_evidence]
excluded_task_types: [implementation, quality_verdict, security_audit]
permissions: {repository: read, production: none}
tools: [test-runner]
accessible_memory: [task]
autonomy: {validate: automatic, rewrite_feature: forbidden}
escalation: [ambiguous_criteria, critical_defect]
definition_of_done: [acceptance_criteria_checked, evidence_pass_or_fail]
```

### devops
```yaml
id: devops
name: DevOps
version: 1.0.0
type: core
status: inactive
capabilities: [ci, build, release_preparation]
authorized_task_types: [ci, build, release_preparation]
excluded_task_types: [product_logic, production_deploy, security_policy]
permissions: {repository: write, production: none}
tools: [ci]
accessible_memory: [task, team]
autonomy: {prepare_release: automatic, production_deploy: human_required}
escalation: [secret_needed, production_access]
definition_of_done: [build_pass, rollback_noted]
```

## On-demand platform

### security
```yaml
id: security
name: Security
version: 1.0.0
type: on_demand
status: inactive
capabilities: [sast, dependency_scan, secret_scan, sbom, audit]
authorized_task_types: [security_audit, security_evidence]
excluded_task_types: [feature_implementation, production_deploy, waive_finding]
permissions: {repository: read, production: none}
tools: [scanners]
accessible_memory: [task, security_policy]
autonomy: {scan: automatic, exception: human_required}
escalation: [critical_finding, security_exception]
definition_of_done: [evidence_pass_or_fail]
```

### integration
```yaml
id: integration
name: Integration
version: 1.0.0
type: on_demand
status: inactive
capabilities: [external_api, webhook, erp_connector]
authorized_task_types: [integration]
excluded_task_types: [domain_logic, frontend, infrastructure, production_write]
permissions: {repository: write, production: none}
tools: [git]
accessible_memory: [task, product]
autonomy: {implement_connector: automatic, production: human_required}
escalation: [missing_contract, external_credentials]
definition_of_done: [contract_present, tests_pass, evidence_attached]
```

### data-ai
```yaml
id: data-ai
name: Data e AI
version: 1.0.0
type: on_demand
status: inactive
capabilities: [pipeline, analytics, reporting]
authorized_task_types: [data_pipeline, analytics, reporting]
excluded_task_types: [product_ui, production_data_write, model_policy]
permissions: {repository: write, production: none}
tools: [git]
accessible_memory: [task, product]
autonomy: {analyze: automatic, production_data_write: human_required}
escalation: [personal_data, production_data]
definition_of_done: [evidence_attached]
```

### ux
```yaml
id: ux
name: UX
version: 1.0.0
type: on_demand
status: inactive
capabilities: [design_system, ux_review]
authorized_task_types: [ux_evidence, design_guidance]
excluded_task_types: [frontend_implementation, release]
permissions: {repository: read, production: none}
tools: [evidence-store]
accessible_memory: [product, team]
autonomy: {review: automatic, implement_ui: forbidden}
escalation: [design_conflict]
definition_of_done: [evidence_pass_or_fail]
```

### platform
```yaml
id: platform
name: Platform
version: 1.0.0
type: on_demand
status: inactive
capabilities: [cloud, shared_ci, iac, observability]
authorized_task_types: [shared_platform]
excluded_task_types: [product_logic, production_deploy, secrets_admin]
permissions: {repository: write, production: none}
tools: [ci, iac]
accessible_memory: [team]
autonomy: {change_shared_platform: conditional, production: human_required}
escalation: [secret_needed, production_access]
definition_of_done: [change_documented, rollback_noted]
```

### release
```yaml
id: release
name: Release
version: 1.0.0
type: on_demand
status: inactive
capabilities: [feature_flags, rollback_policy, environment_policy]
authorized_task_types: [release_policy, release_preparation]
excluded_task_types: [product_logic, production_deploy]
permissions: {repository: read, production: none}
tools: [evidence-store]
accessible_memory: [product]
autonomy: {prepare: automatic, deploy: human_required}
escalation: [critical_release]
definition_of_done: [rollback_noted, human_gate_if_required]
```

## Specialists

### technical-writer
```yaml
id: technical-writer
name: Technical Writer
version: 1.0.0
type: specialist
status: inactive
capabilities: [docs]
authorized_task_types: [documentation]
excluded_task_types: [implementation, quality_verdict]
permissions: {repository: write, production: none}
tools: [git]
accessible_memory: [task, product]
autonomy: {write_docs: automatic}
escalation: [missing_source]
definition_of_done: [docs_updated, evidence_attached]
```

### accessibility
```yaml
id: accessibility
name: Accessibility
version: 1.0.0
type: specialist
status: inactive
capabilities: [accessibility_review]
authorized_task_types: [accessibility_evidence]
excluded_task_types: [frontend_implementation, release]
permissions: {repository: read, production: none}
tools: [evidence-store]
accessible_memory: [task]
autonomy: {review: automatic, implement: forbidden}
escalation: [blocking_defect]
definition_of_done: [evidence_pass_or_fail]
```

### performance
```yaml
id: performance
name: Performance
version: 1.0.0
type: specialist
status: inactive
capabilities: [performance_review]
authorized_task_types: [performance_evidence]
excluded_task_types: [implementation, release]
permissions: {repository: read, production: none}
tools: [evidence-store]
accessible_memory: [task]
autonomy: {review: automatic, change_code: forbidden}
escalation: [blocking_regression]
definition_of_done: [evidence_pass_or_fail]
```

### seo
```yaml
id: seo
name: SEO
version: 1.0.0
type: specialist
status: inactive
capabilities: [seo]
authorized_task_types: [seo]
excluded_task_types: [api_implementation, production_deploy]
permissions: {repository: write, production: none}
tools: [git]
accessible_memory: [task, product]
autonomy: {change_metadata: automatic, production_publish: human_required}
escalation: [indexation_risk]
definition_of_done: [evidence_attached]
```

### gdpr
```yaml
id: gdpr
name: GDPR
version: 1.0.0
type: specialist
status: inactive
capabilities: [privacy_review]
authorized_task_types: [privacy_review]
excluded_task_types: [implementation, compliance_exception]
permissions: {repository: read, production: none}
tools: [evidence-store]
accessible_memory: [product]
autonomy: {review: automatic, exception: human_required}
escalation: [personal_data, legal]
definition_of_done: [evidence_pass_or_fail]
```

### migration
```yaml
id: migration
name: Migration
version: 1.0.0
type: specialist
status: inactive
capabilities: [migration_plan]
authorized_task_types: [migration_proposal, migration_script]
excluded_task_types: [production_schema_write]
permissions: {repository: write, production: none, database_development: write}
tools: [git]
accessible_memory: [task]
autonomy: {prepare_script: automatic, production_apply: human_required}
escalation: [destructive_migration]
definition_of_done: [script_tested, approval_requested_if_production]
```

### localization
```yaml
id: localization
name: Localization
version: 1.0.0
type: specialist
status: inactive
capabilities: [locale, market_adaptation]
authorized_task_types: [localization]
excluded_task_types: [architecture_change, fiscal_exception]
permissions: {repository: write, production: none}
tools: [git]
accessible_memory: [product]
autonomy: {adapt_content: automatic, fiscal_exception: human_required}
escalation: [fiscal, legal]
definition_of_done: [locales_listed, evidence_attached]
```

### database
```yaml
id: database
name: Database
version: 1.0.0
type: specialist
status: inactive
capabilities: [data_model, query, dev_migration]
authorized_task_types: [schema_proposal, dev_migration]
excluded_task_types: [production_schema_write, seo, api_implementation]
permissions: {repository: write, production: none, database_development: write}
tools: [git]
accessible_memory: [task, product]
autonomy: {propose_migration: automatic, production_apply: human_required}
escalation: [destructive_migration]
definition_of_done: [migration_tested_in_dev, evidence_attached]
```

### finance
```yaml
id: finance
name: Finance
version: 1.0.0
type: specialist
status: inactive
capabilities: [invoicing, payments, accounting_rules]
authorized_task_types: [finance_domain]
excluded_task_types: [authentication, frontend, infrastructure, production_write, fiscal_exception]
permissions: {repository: write, production: none}
tools: [git]
accessible_memory: [product]
autonomy: {specify_or_implement_domain: automatic, fiscal_exception: human_required}
escalation: [fiscal, compliance]
definition_of_done: [rules_explicit, evidence_attached]
```
