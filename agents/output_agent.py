from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from utils.insurance_rules import format_inr
from utils.simple_chart import write_cost_flow_chart
from utils.tts import write_tts_audio
from utils.validation import ValidationResult


class OutputAgent:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.letters_dir = output_dir / "preauth_letters"
        self.charts_dir = output_dir / "charts"

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        self.letters_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)

        cob = state["cob"]
        clinical = state["clinical"]
        report = {
            "intake": state["intake"],
            "clinical": clinical,
            "cob": cob,
            "run_log": state["run_log"],
            "router_decisions": state.get("router_decisions", []),
            "reflection": state["reflection"],
        }

        summary_path = self.output_dir / "summary.txt"
        json_path = self.output_dir / "final_report.json"
        audio_path = self.output_dir / "audio_briefing.txt"
        audio_file_path = self.output_dir / "audio_briefing.wav"
        chart_paths = write_cost_flow_chart(cob["claims"], self.charts_dir)
        letter_paths = self._write_letters(cob["claims"])
        audio_briefing = self._audio_briefing(cob)

        summary_path.write_text(self._summary(cob), encoding="utf-8")
        json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        audio_path.write_text(audio_briefing, encoding="utf-8")
        generated_audio = write_tts_audio(audio_briefing, audio_file_path)

        outputs = {
            "summary": str(summary_path),
            "final_report": str(json_path),
            "audio_briefing": str(audio_path),
            "audio_file": str(generated_audio) if generated_audio else None,
            "letters": letter_paths,
            "charts": chart_paths,
        }
        return {"outputs": outputs, "validation": self._validate(outputs)}

    def _summary(self, cob: dict[str, Any]) -> str:
        lines = [
            "DuCO-Agent Claim Summary",
            "=" * 28,
            cob["patient_message"],
            "",
        ]
        for claim in cob["claims"]:
            lines.extend(
                [
                    f"{claim['claim_id']} - {claim['member_name']}",
                    f"Service: {claim['description']}",
                    f"Primary: {claim['primary_plan_label']} paid {format_inr(claim['primary_paid_inr'])}",
                    f"Secondary: {claim['secondary_plan_label']} paid {format_inr(claim['secondary_paid_inr'])}",
                    f"Patient estimate: {format_inr(claim['patient_paid_inr'])}",
                    f"Preauthorization required: {'Yes' if claim['preauth_required'] else 'No'}",
                    "",
                ]
            )
        return "\n".join(lines)

    def _write_letters(self, claims: list[dict[str, Any]]) -> list[str]:
        paths = []
        for claim in claims:
            if claim["claim_id"].startswith("AARAV"):
                paths.append(
                    self._write_letter(
                        "aarav_plan_b_primary_preauth.txt",
                        claim,
                        insurer="Insurer2 / Plan B",
                        role="primary payer",
                    )
                )
                paths.append(
                    self._write_letter(
                        "aarav_plan_a_secondary_preauth.txt",
                        claim,
                        insurer="Insurer1 / Plan A",
                        role="secondary payer",
                    )
                )
            if claim["claim_id"].startswith("PRIYA"):
                paths.append(self._write_pt_cover_letter(claim))
        return paths

    def _write_letter(self, filename: str, claim: dict[str, Any], insurer: str, role: str) -> str:
        cpts = ", ".join(f"{item['cpt']} ({item['description']})" for item in claim["cpt_codes"])
        diagnoses = ", ".join(claim["diagnosis"])
        text = f"""To: Medical Management Department, {insurer}
Subject: Pre-Authorization Request for Aarav Sen - ACL Reconstruction

Dear Utilization Review Team,

This letter requests pre-authorization for Aarav Sen's medically necessary knee surgery. MRI findings confirm {diagnoses}. The requested procedures are {cpts}, with an estimated allowed charge of {format_inr(claim['charge_inr'])}.

DuCO-Agent has identified {insurer} as the {role} under the Sen family's Coordination of Benefits arrangement. The surgery is planned to address functional instability and meniscal pathology documented in the radiology report.

Please review the attached clinical report, surgeon estimate, and COB details. Kindly confirm authorization status, approved service dates, and any additional documentation requirements before surgery to avoid claim rejection.

Sincerely,
DuCO-Agent Clinical Coordination System
"""
        path = self.letters_dir / filename
        path.write_text(text, encoding="utf-8")
        return str(path)

    def _write_pt_cover_letter(self, claim: dict[str, Any]) -> str:
        codes = ", ".join(item["cpt"] for item in claim["cpt_codes"])
        text = f"""To: Claims Department, Insurer1 / Plan A and Insurer2 / Plan B
Subject: Coordination of Benefits Claim Submission for Priya Sen Physical Therapy

Dear Claims Team,

Please process Priya Sen's unpaid physical therapy claim for {format_inr(claim['charge_inr'])}. The services map to CPT {codes} and diagnosis {', '.join(claim['diagnosis'])}. Plan A is primary for Priya, and Plan B is secondary.

No pre-authorization is indicated under the mock PT rules. Please coordinate benefits so any eligible residual member liability is considered by the secondary plan.

Sincerely,
DuCO-Agent Clinical Coordination System
"""
        path = self.letters_dir / "priya_pt_claim_cover_letter.txt"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def _audio_briefing(self, cob: dict[str, Any]) -> str:
        return (
            "Hi Aarav and Priya. DuCO-Agent reviewed both policies. "
            f"Your total submitted charges are {format_inr(cob['total_charges_inr'])}. "
            f"After primary and secondary coordination, your estimated household out-of-pocket is "
            f"{format_inr(cob['household_out_of_pocket_inr'])}. "
            "Aarav's surgery needs pre-authorization from the primary and secondary insurers before the procedure."
        )

    def _validate(self, outputs: dict[str, Any]) -> ValidationResult:
        issues = []
        for key, value in outputs.items():
            if value is None:
                continue
            paths = value if isinstance(value, list) else [value]
            for path in paths:
                if not Path(path).exists():
                    issues.append(f"Missing output file for {key}: {path}")
        return ValidationResult(ok=not issues, issues=issues)
