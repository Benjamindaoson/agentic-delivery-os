"""
Strategy enumerator for Data Intelligence Agent.
Enumerates candidate strategies per file with explicit cost/accuracy/latency.
"""

from typing import Dict, List
from dataclasses import dataclass, asdict
from runtime.data_intel.type_classifier import TypeTag


@dataclass
class Strategy:
    id: str
    pipeline_steps: List[str]
    expected_quality_range: str  # e.g., high/medium/low
    expected_cost_range: List[float]  # [min, max]
    expected_latency_class: str  # low / medium / high
    risk_types: List[str]
    resource_profile: Dict[str, str]


def _ocr_strategies() -> List[Strategy]:
    return [
        Strategy(
            id="T3_layout_ocr_mineru",
            pipeline_steps=["ocr:MinerU", "text_normalize"],
            expected_cost_range=[1.0, 1.5],
            expected_quality_range="high",
            expected_latency_class="high",
            risk_types=["higher_cost"],
            resource_profile={"cpu": "medium", "gpu": "optional", "memory": "medium"},
        ),
        Strategy(
            id="T4_progressive_roi",
            pipeline_steps=["roi_detect:light", "ocr:targeted_high_fidelity"],
            expected_cost_range=[0.6, 1.0],
            expected_quality_range="high",
            expected_latency_class="medium",
            risk_types=["roi_miss"],
            resource_profile={"cpu": "medium", "gpu": "optional", "memory": "medium"},
        ),
        Strategy(
            id="T2_high_ocr_deepseek",
            pipeline_steps=["ocr:DeepSeek", "text_normalize"],
            expected_cost_range=[0.6, 1.0],
            expected_quality_range="high",
            expected_latency_class="medium",
            risk_types=["cost_spike_if_large"],
            resource_profile={"cpu": "medium", "gpu": "optional", "memory": "medium"},
        ),
        Strategy(
            id="T1_fast_ocr_paddleocr",
            pipeline_steps=["ocr:PaddleOCR", "text_normalize"],
            expected_cost_range=[0.2, 0.4],
            expected_quality_range="medium",
            expected_latency_class="low",
            risk_types=["lower_accuracy_on_complex_layout"],
            resource_profile={"cpu": "low", "gpu": "none", "memory": "low"},
        ),
    ]


def _table_strategies(need_ocr: bool) -> List[Strategy]:
    strategies = [
        Strategy(
            id="T0_table_native",
            pipeline_steps=["table_parse:native"],
            expected_cost_range=[0.1, 0.2],
            expected_quality_range="high",
            expected_latency_class="low",
            risk_types=["fails_on_scanned_tables"],
            resource_profile={"cpu": "low", "gpu": "none", "memory": "low"},
        ),
        Strategy(
            id="T0_table_recover_struct",
            pipeline_steps=["table_parse:native", "table_recover:structure"],
            expected_cost_range=[0.3, 0.5],
            expected_quality_range="medium",
            expected_latency_class="medium",
            risk_types=["structure_misalignment"],
            resource_profile={"cpu": "medium", "gpu": "none", "memory": "medium"},
        ),
    ]
    if need_ocr:
        strategies.append(
            Strategy(
                id="T1_table_ocr_recover",
                pipeline_steps=["ocr:PaddleOCR", "table_recover:structure"],
                expected_cost_range=[0.5, 0.8],
                expected_quality_range="medium",
                expected_latency_class="medium",
                risk_types=["ocr_noise", "structure_loss"],
                resource_profile={"cpu": "medium", "gpu": "none", "memory": "medium"},
            )
        )
    return strategies


def _text_strategies() -> List[Strategy]:
    return [
        Strategy(
            id="T0_text_native",
            pipeline_steps=["text_extract:native", "clean:light"],
            expected_cost_range=[0.05, 0.15],
            expected_quality_range="high",
            expected_latency_class="low",
            risk_types=[],
            resource_profile={"cpu": "low", "gpu": "none", "memory": "low"},
        ),
        Strategy(
            id="T0_text_heavy_normalize",
            pipeline_steps=["text_extract:native", "clean:heavy", "segment"],
            expected_cost_range=[0.1, 0.25],
            expected_quality_range="high",
            expected_latency_class="medium",
            risk_types=["slower"],
            resource_profile={"cpu": "medium", "gpu": "none", "memory": "low"},
        ),
    ]


def enumerate_strategies(classification: Dict) -> List[Dict]:
    """
    Enumerate candidate strategies based on classification result.
    """
    type_tags = classification.get("type_tags", [])
    need_ocr = bool(classification.get("need_ocr"))
    need_table_recovery = bool(classification.get("need_table_recovery"))

    strategies: List[Strategy] = []

    # Standard strategy family T0-T3 always included
    strategies.append(
        Strategy(
            id="T0_native_parse",
            pipeline_steps=["text_extract:native"],
            expected_cost_range=[0.05, 0.2],
            expected_quality_range="medium",
            expected_latency_class="low",
            risk_types=["fails_if_no_text_layer"],
            resource_profile={"cpu": "low", "gpu": "none", "memory": "low"},
        )
    )
    strategies.append(
        Strategy(
            id="T1_fast_ocr_paddleocr",
            pipeline_steps=["ocr:PaddleOCR", "text_normalize"],
            expected_cost_range=[0.2, 0.4],
            expected_quality_range="medium",
            expected_latency_class="low",
            risk_types=["lower_accuracy_on_complex_layout"],
            resource_profile={"cpu": "low", "gpu": "none", "memory": "low"},
        )
    )
    strategies.append(
        Strategy(
            id="T2_high_ocr_deepseek",
            pipeline_steps=["ocr:DeepSeek", "text_normalize"],
            expected_cost_range=[0.6, 1.0],
            expected_quality_range="high",
            expected_latency_class="medium",
            risk_types=["cost_spike_if_large"],
            resource_profile={"cpu": "medium", "gpu": "optional", "memory": "medium"},
        )
    )
    strategies.append(
        Strategy(
            id="T3_layout_ocr_mineru",
            pipeline_steps=["ocr:MinerU", "text_normalize"],
            expected_cost_range=[1.0, 1.5],
            expected_quality_range="high",
            expected_latency_class="high",
            risk_types=["higher_cost"],
            resource_profile={"cpu": "medium", "gpu": "optional", "memory": "medium"},
        )
    )

    if TypeTag.IMAGE_DOMINANT in type_tags:
        strategies.extend([])  # already covered by T1-T3

    if TypeTag.TABLE_STRUCTURED in type_tags:
        strategies.extend(_table_strategies(need_ocr))

    if TypeTag.TEXT_NATIVE in type_tags or TypeTag.SEMI_STRUCTURED in type_tags:
        strategies.extend(_text_strategies())

    if TypeTag.MIXED_HETEROGENEOUS in type_tags:
        # Conservative mixed pipeline
        strategies.append(
            Strategy(
                id="T0_mixed_safe",
                pipeline_steps=[
                    "detect_layout",
                    "branch:text_or_table",
                    "clean:light",
                ],
                expected_cost_range=[0.3, 0.6],
                expected_quality_range="medium",
                expected_latency_class="medium",
                risk_types=["layout_misclassification"],
                resource_profile={"cpu": "medium", "gpu": "none", "memory": "medium"},
            )
        )

    # If no strategies determined, provide minimal fail-safe
    if not strategies:
        strategies.append(
            Strategy(
                id="T0_fallback_minimal",
                pipeline_steps=["metadata_only"],
                expected_cost_range=[0.02, 0.05],
                expected_quality_range="low",
                expected_latency_class="low",
                risk_types=["data_unprocessed"],
                resource_profile={"cpu": "low", "gpu": "none", "memory": "low"},
            )
        )

    return [asdict(s) for s in strategies]


def enumerate_for_files(classifications: List[Dict]) -> List[Dict]:
    results = []
    for cls in classifications:
        results.append(
            {
                "file_path": cls.get("file_path"),
                "strategies": enumerate_strategies(cls),
            }
        )
    return results
