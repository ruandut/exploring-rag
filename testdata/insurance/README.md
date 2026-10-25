# Kestrel Ridge insurance test set (fictional)

Nine PDFs from a **fictional** South African insurer, Kestrel Ridge, for testing RAG Lab.
They have about 250 pages and 83,000 words, plus an answer key you can import as a benchmark suite.
Kestrel Ridge doesn't exist. Every page says so, and the documents are not legal or insurance advice.

| File | What it is | Sections |
|---|---|---|
| `KR-PL-001-household-policy-wording.pdf` | Household policy wording | Definitions; Buildings; Contents; All risks; Liability; Excesses; Premiums; Cancellation; Claims; Exclusions; Conditions; Complaints; POPIA; Regulatory; premium guide, worked examples, FAQ, endorsements, specimen schedules |
| `KR-PL-002-private-motor-policy-wording.pdf` | Private motor policy wording | Cover types; who may drive; security; excesses; extra benefits; exclusions; claims; rate tables, vehicle rating groups, examples, schedules |
| `KR-CL-001-business-insurance-policy-wording.pdf` | SME business policy | Fire; business interruption; office contents; theft; money; goods in transit; public liability; fidelity; electronic equipment; occupation classes, examples, schedules |
| `KR-LF-001-funeral-and-life-policy-terms.pdf` | Funeral, term life, disability (long-term) | Waiting periods; benefits; claims documents; premiums and lapse; premium tables by age, examples, schedules |
| `KR-OPS-001-claims-management-manual.pdf` | Internal claims manual | Lifecycle; service levels; assessors; authority limits; rejections; fraud indicators; recoveries; QA; letters; claims statistics; case studies |
| `KR-UW-001-underwriting-guidelines.pdf` | Internal underwriting guidelines | Acceptance; construction; location; motor; rating factors; referral authority; area risk zones |
| `KR-GOV-002-complaints-and-tcf-policy.pdf` | Complaints and Treating Customers Fairly | Six TCF outcomes; measures; complaints process; categories; records |
| `KR-GOV-004-privacy-and-information-protection-policy.pdf` | POPIA policy | Eight conditions; special information; retention; data subject requests; breaches; operators |
| `KR-GOV-003-financial-crime-and-fraud-policy.pdf` | FICA, AML and fraud | Risk-based approach; due diligence; STR/CTR reporting; fraud prevention; red flags |

The documents refer to real South African laws and bodies, such as the Insurance Act, the Policyholder
Protection Rules, FAIS, POPIA, FICA, SASRIA, the FSCA and the National Financial Ombud Scheme.
The figures in them (excesses, limits, waiting periods, service levels) are invented and kept consistent across the set.

## Build

```bash
make testdata
```

That runs `uv run --no-project --with reportlab --with pypdf python testdata/insurance/generate.py`.
The output is deterministic because the random seed is fixed. The PDFs are written to `pdfs/` and aren't committed.

## Use it

1. Upload `pdfs/*.pdf` into a Library folder, for example "Insurance".
2. Create an embedding that covers that folder (Embeddings page).
3. Benchmarks: create a suite and import `cases.jsonl`. It has 79 questions, each with a reference
   answer, the relevant document and an evidence snippet, plus 5 refusal questions.
4. Run the suite against an agent and an embedding, or compare two embeddings side by side.

The generator checks every evidence snippet against the text pypdf extracts from the PDF.
pypdf is the parser the app uses, so a suite built from `cases.jsonl` always matches the documents.
