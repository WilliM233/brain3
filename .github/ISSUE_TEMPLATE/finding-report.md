---
name: Finding Report
about: QA, Security, or Documentation finding during hardening
labels: ''
assignees: ''
---

## Finding

**Type:**
<!-- Choose one: Bug | Deviation | Gap | Cosmetic | Vulnerability | Misconfiguration | Risk | Hardening | Contract Mismatch | Documentation Gap | Recommendation -->

**Severity:**
<!-- Choose one: Blocker | Major | Minor | Cosmetic -->

**Filed by:**
<!-- Agent name and designation (e.g., Quincy Assurance · QA-01) -->

**Area:**
<!-- Where in the system this finding applies.
QA examples: Router | Schema | Filter | Cascade | Test Coverage | Edge Case
Security examples: Input Validation | Secrets | Docker | CORS | Auth Readiness | Dependencies | Backup | Logging | Scripts
API Doc examples: Router | Schema | OpenAPI | Filter | Report | Tool Definition | Client | Configuration -->

**Ticket context:**
<!-- Which ticket introduced or should have covered this (e.g., TICKET-05) -->

---

## Description
<!-- Clear, specific description of the finding. One finding per issue. -->

## Location
<!-- File path and line number(s) where the issue exists. -->

## Steps to Reproduce
<!-- For bugs and deviations. Remove this section if not applicable. -->

1. 
2. 
3. 

## Expected Behavior
<!-- What should happen according to the spec, design document, or convention. -->

## Actual Behavior
<!-- What actually happens. Include response body, error message, or output if relevant. -->

## Suggested Fix
<!-- Optional. Your analysis and recommendation. Do not implement — file only. -->

## Layer Coverage
<!-- Required for Type: Contract Mismatch. Optional for other types; remove the section if not applicable.
List every layer that could carry state for this finding, what you checked, and what you found.
Status column values: Checked + consistent | Checked + inconsistent | Not applicable | Not checked (blind spot).
Any "Not checked" row must name its mitigation — a proxy test, manual probe, or follow-up issue.
For enum / schema / typed-column findings, the standing layer list lives in BRAIN artifact
18e6da34-03e1-4e3d-bc87-3c788f88d688 (Enum / Schema Change Checklist). -->

| Layer | Status | Evidence / Notes |
|-------|--------|------------------|
|       |        |                  |

---

### Severity Reference

| Severity | Meaning |
|----------|---------|
| **Blocker** | Release cannot proceed. Core functionality broken, data integrity at risk, or documentation cannot be written. |
| **Major** | Significant gap but workaround exists. Should be addressed before release if possible. |
| **Minor** | Small functional issue, low user impact. Log for next cycle. |
| **Cosmetic** | No functional impact. Style, convention, or aesthetic issue. |
