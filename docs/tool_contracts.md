# Tool Contracts

The system treats each agent as a tool with structured inputs and outputs.

## Intake Agent

Input:

- Workflow state.
- Files under `data/`.

Output:

- `intake.raw_documents`
- `intake.people`
- `intake.claims`

Failure behavior:

- Returns validation issues if required claims or clinical evidence are missing.

## Clinical Agent

Input:

- `intake.claims`

Output:

- `clinical.claims`
- `clinical.medical_summary`

Failure behavior:

- Returns validation issues if CPT codes are missing or surgery preauthorization is not detected.

## COB Agent

Input:

- `clinical.claims`

Output:

- `cob.claims`
- `cob.total_charges_inr`
- `cob.total_insurer_paid_inr`
- `cob.household_out_of_pocket_inr`

Failure behavior:

- Returns validation issues if claim payments do not balance to the charge.

## Output Agent

Input:

- `intake`
- `clinical`
- `cob`

Output:

- `outputs.summary`
- `outputs.final_report`
- `outputs.audio_briefing`
- `outputs.letters`
- `outputs.charts`

Failure behavior:

- Returns validation issues if expected files are not created.
