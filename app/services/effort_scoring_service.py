from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.services.gemini_service import GeminiService
from app.services.github_service import GitHubCommitDetails, GitHubChangedFile


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)
_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


@dataclass
class EffortScoringResult:
    effort_score: float
    confidence: float
    score_source: str
    difficulty: str
    reason_short: str
    summary: str


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


class EffortScoringService:
    """
    Hybrid effort scoring:
    - Deterministic baseline from code-change metadata.
    - LLM rubric over compact diff context.
    - Graceful deterministic fallback when AI is unavailable/rate-limited.
    """

    def __init__(self, gemini: GeminiService | None, ai_error_reason: str | None = None):
        self.gemini = gemini
        self.ai_error_reason = ai_error_reason
        self.v2_enabled = settings.EFFORT_V2_ENABLED
        self.llm_enabled = settings.EFFORT_V2_LLM_ENABLED

    def score_commit(self, commit_message: str, details: GitHubCommitDetails) -> EffortScoringResult:
        if not self.v2_enabled:
            return self.score_commit_deterministic(commit_message, details, llm_error="EFFORT_V2 disabled")

        deterministic = self._deterministic_score(commit_message, details)

        if not self.llm_enabled:
            return deterministic

        if not self.gemini:
            reason = self.ai_error_reason or "AI provider not configured"
            return self.score_commit_deterministic(commit_message, details, llm_error=reason)

        prompt = self._build_llm_prompt(
            commit_message=commit_message,
            details=details,
            deterministic_score=deterministic.effort_score,
            deterministic_reason=deterministic.reason_short,
        )

        try:
            raw_output = self.gemini.generate(prompt)
            payload = self._parse_json_payload(raw_output)
            return self._combine_scores(payload, deterministic, commit_message, details)
        except Exception as exc:
            return self.score_commit_deterministic(
                commit_message,
                details,
                llm_error=str(exc),
            )

    def score_commit_deterministic(
        self,
        commit_message: str,
        details: GitHubCommitDetails,
        llm_error: str | None = None,
    ) -> EffortScoringResult:
        base = self._deterministic_score(commit_message, details)
        if llm_error:
            suffix = f" LLM fallback: {llm_error[:120]}"
            reason = (base.reason_short + suffix)[:240]
            return EffortScoringResult(
                effort_score=base.effort_score,
                confidence=base.confidence,
                score_source="effort_v2_deterministic_fallback",
                difficulty=base.difficulty,
                reason_short=reason,
                summary=base.summary,
            )
        return base

    def _combine_scores(
        self,
        payload: dict[str, Any],
        deterministic: EffortScoringResult,
        commit_message: str,
        details: GitHubCommitDetails,
    ) -> EffortScoringResult:
        metrics = {
            "feature_impact": self._score_field(payload, "feature_impact"),
            "code_quality": self._score_field(payload, "code_quality"),
            "code_organization": self._score_field(payload, "code_organization"),
            "test_coverage_impact": self._score_field(payload, "test_coverage_impact"),
            "risk_management": self._score_field(payload, "risk_management"),
            "maintainability": self._score_field(payload, "maintainability"),
        }

        llm_score = (
            0.25 * metrics["feature_impact"]
            + 0.20 * metrics["code_quality"]
            + 0.15 * metrics["code_organization"]
            + 0.15 * metrics["test_coverage_impact"]
            + 0.10 * metrics["risk_management"]
            + 0.15 * metrics["maintainability"]
        )

        llm_confidence = self._confidence_field(payload, "confidence")
        final_score = round((0.65 * llm_score) + (0.35 * deterministic.effort_score), 2)
        final_confidence = round(_clamp((0.70 * llm_confidence) + (0.30 * deterministic.confidence), 0.0, 1.0), 2)

        summary = self._sanitize_summary(payload.get("summary")) or deterministic.summary
        justification = self._sanitize_reason(payload.get("justification"))
        if not justification:
            justification = (
                f"Feature {metrics['feature_impact']:.0f}, quality {metrics['code_quality']:.0f}, "
                f"maintainability {metrics['maintainability']:.0f}."
            )
        reason_short = justification[:240]

        return EffortScoringResult(
            effort_score=final_score,
            confidence=final_confidence,
            score_source="effort_v2_hybrid_llm",
            difficulty=self._difficulty_from_score(final_score),
            reason_short=reason_short,
            summary=summary,
        )

    def _deterministic_score(
        self,
        commit_message: str,
        details: GitHubCommitDetails,
    ) -> EffortScoringResult:
        additions = max(0, int(details.additions or 0))
        deletions = max(0, int(details.deletions or 0))
        files = details.files or []
        file_count = len(files)
        loc_total = additions + deletions
        weighted_loc = additions + (0.8 * deletions)

        directories = {
            "/".join(file.filename.split("/")[:-1])
            for file in files
            if file.filename and "/" in file.filename
        }
        rename_count = sum(1 for file in files if file.status == "renamed")
        test_count = sum(1 for file in files if self._is_test_file(file.filename))
        docs_count = sum(1 for file in files if self._is_docs_file(file.filename))
        config_count = sum(1 for file in files if self._is_config_file(file.filename))
        patch_count = sum(1 for file in files if (file.patch or "").strip())

        loc_component = min(45.0, math.sqrt(max(0.0, weighted_loc)) * 2.4)
        breadth_component = min(
            22.0,
            (file_count * 2.6) + (max(0, len(directories) - 1) * 1.3) + (rename_count * 1.8),
        )
        quality_component = min(18.0, (test_count * 5.0) + (docs_count * 2.0))

        config_penalty = min(10.0, config_count * 1.6)
        if test_count > 0:
            config_penalty = min(4.0, config_count * 0.7)

        large_change_penalty = 0.0
        if loc_total > 1200 and test_count == 0:
            large_change_penalty = min(12.0, (loc_total - 1200) / 180.0)

        score = 12.0 + loc_component + breadth_component + quality_component - config_penalty - large_change_penalty
        score = round(_clamp(score, 0.0, 100.0), 2)

        coverage_ratio = (patch_count / file_count) if file_count else 0.0
        confidence = 0.46 + min(0.22, file_count * 0.025) + (0.18 * coverage_ratio)
        confidence = round(_clamp(confidence, 0.35, 0.82), 2)

        reason = (
            f"Deterministic baseline from {loc_total} changed lines across {file_count} files "
            f"({test_count} test, {docs_count} docs)."
        )[:240]

        return EffortScoringResult(
            effort_score=score,
            confidence=confidence,
            score_source="effort_v2_deterministic",
            difficulty=self._difficulty_from_score(score),
            reason_short=reason,
            summary=self._fallback_summary(commit_message, details),
        )

    def _build_llm_prompt(
        self,
        *,
        commit_message: str,
        details: GitHubCommitDetails,
        deterministic_score: float,
        deterministic_reason: str,
    ) -> str:
        diff_context = self._compact_diff_for_prompt(details.files)

        return (
            "You are an expert senior software engineer evaluating commit effort.\n"
            "Evaluate commit effort using software-engineering signals, not raw LOC only.\n"
            "Return STRICT JSON only (no markdown).\n\n"
            "Scoring rubric (0-100 each):\n"
            "- feature_impact: how meaningful the functional change is.\n"
            "- code_quality: readability, correctness signals, robustness.\n"
            "- code_organization: architecture/structure/cohesion improvements.\n"
            "- test_coverage_impact: tests added/updated and validation quality.\n"
            "- risk_management: safe handling of edge cases, backwards compatibility.\n"
            "- maintainability: long-term maintainability and clarity.\n"
            "Also return confidence (0-1), concise justification, and concise summary.\n\n"
            "Output JSON schema:\n"
            "{\n"
            '  "feature_impact": number,\n'
            '  "code_quality": number,\n'
            '  "code_organization": number,\n'
            '  "test_coverage_impact": number,\n'
            '  "risk_management": number,\n'
            '  "maintainability": number,\n'
            '  "confidence": number,\n'
            '  "justification": "string (max 220 chars)",\n'
            '  "summary": "string (1-2 short sentences)"\n'
            "}\n\n"
            f"Commit message:\n{commit_message.strip()[:500]}\n\n"
            f"Diff stats: additions={details.additions}, deletions={details.deletions}, files={len(details.files)}\n"
            f"Deterministic baseline score={deterministic_score}. Note: {deterministic_reason}\n\n"
            "Changed file context:\n"
            f"{diff_context}"
        )

    def _compact_diff_for_prompt(self, files: list[GitHubChangedFile]) -> str:
        max_files = max(1, int(settings.EFFORT_V2_MAX_FILES_FOR_LLM))
        max_chars = max(1000, int(settings.EFFORT_V2_MAX_PATCH_CHARS))

        selected_files = files[:max_files]
        if not selected_files:
            return "<No file-level diff available>"

        chunks: list[str] = []
        remaining = max_chars

        for index, file in enumerate(selected_files, start=1):
            header = (
                f"[{index}] {file.status.upper()} {file.filename} "
                f"(+{file.additions}/-{file.deletions})"
            )
            if file.previous_filename:
                header += f" from {file.previous_filename}"

            chunk = header
            patch = (file.patch or "").strip()
            if patch:
                per_file_patch_limit = max(250, max_chars // max(1, max_files))
                trimmed = patch[:per_file_patch_limit]
                if len(patch) > len(trimmed):
                    trimmed = trimmed.rstrip() + "\n... [file patch truncated]"
                chunk += "\n" + trimmed
            else:
                chunk += "\n<No textual patch available>"

            if len(chunk) > remaining:
                chunk = chunk[:remaining].rstrip() + "\n... [overall diff truncated]"
                chunks.append(chunk)
                break

            chunks.append(chunk)
            remaining -= len(chunk)
            if remaining <= 0:
                break

        return "\n\n".join(chunks)

    def _parse_json_payload(self, raw_text: str) -> dict[str, Any]:
        text = (raw_text or "").strip()
        if not text:
            raise ValueError("Empty LLM response")

        cleaned = _JSON_FENCE_RE.sub("", text).strip()
        candidates = [cleaned]

        block_match = _JSON_BLOCK_RE.search(cleaned)
        if block_match:
            candidates.append(block_match.group(0))

        for candidate in candidates:
            try:
                payload = json.loads(candidate)
                if isinstance(payload, dict):
                    return payload
            except Exception:
                continue

        raise ValueError(f"Unable to parse scoring JSON: {text[:220]}")

    def _score_field(self, payload: dict[str, Any], key: str) -> float:
        value = payload.get(key)
        try:
            numeric = float(value)
        except Exception:
            raise ValueError(f"Missing or invalid '{key}' in scoring response")
        return round(_clamp(numeric, 0.0, 100.0), 2)

    def _confidence_field(self, payload: dict[str, Any], key: str) -> float:
        value = payload.get(key)
        try:
            numeric = float(value)
        except Exception:
            numeric = 0.55

        if numeric > 1.0:
            numeric = numeric / 100.0

        return round(_clamp(numeric, 0.0, 1.0), 2)

    def _sanitize_summary(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()[:320]

    def _sanitize_reason(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(value.strip().split())[:240]

    def _difficulty_from_score(self, score: float) -> str:
        if score < 25:
            return "low"
        if score < 50:
            return "medium"
        if score < 75:
            return "high"
        return "very_high"

    def _fallback_summary(self, commit_message: str, details: GitHubCommitDetails) -> str:
        first_line = (commit_message or "").strip().splitlines()[0] if commit_message else "Code changes"
        first_line = first_line[:140]
        file_count = len(details.files or [])
        return (
            f"{first_line}. Updated {file_count} file(s) "
            f"(+{details.additions}/-{details.deletions})."
        )[:320]

    def _is_test_file(self, path: str) -> bool:
        normalized = (path or "").lower()
        return any(
            marker in normalized
            for marker in (
                "/test/",
                "/tests/",
                "_test.",
                ".test.",
                ".spec.",
                "test_",
            )
        )

    def _is_docs_file(self, path: str) -> bool:
        normalized = (path or "").lower()
        return (
            normalized.endswith(".md")
            or normalized.endswith(".rst")
            or normalized.startswith("docs/")
            or "/docs/" in normalized
        )

    def _is_config_file(self, path: str) -> bool:
        normalized = (path or "").lower()
        return any(
            normalized.endswith(suffix)
            for suffix in (
                ".yml",
                ".yaml",
                ".json",
                ".toml",
                ".ini",
                ".cfg",
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "poetry.lock",
            )
        )
