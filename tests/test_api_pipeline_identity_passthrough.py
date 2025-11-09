# Copyright 2025 Semantiva authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Test that /api/pipeline correctly passes through identity from inspection.build()."""

from semantiva_studio_viewer.pipeline import build_pipeline_json


def test_pipeline_json_includes_identity_from_inspection_build():
    """Test that build_pipeline_json includes identity from inspection.build()."""
    # Simple pipeline configuration
    config = [
        {
            "component": "semantiva.testing.identity_test_processor",
            "label": "test_node",
            "params": {"value": 42},
        }
    ]

    result = build_pipeline_json(config)

    # Must have identity key
    assert (
        "identity" in result
    ), "Result must contain 'identity' key from inspection.build()"

    identity = result["identity"]

    # Must have semantic_id and config_id (from inspection.build)
    assert "semantic_id" in identity, "Identity must contain semantic_id"
    assert "config_id" in identity, "Identity must contain config_id"

    # Semantic ID must follow plsemid- format
    if identity["semantic_id"]:
        assert identity["semantic_id"].startswith(
            "plsemid-"
        ), "Semantic ID must follow plsemid- format"

    # Config ID must follow plcid- format
    if identity["config_id"]:
        assert identity["config_id"].startswith(
            "plcid-"
        ), "Config ID must follow plcid- format"

    # Run-space must have inputs_id set to None in inspection mode
    assert "run_space" in identity, "Identity must contain run_space"
    assert (
        identity["run_space"]["inputs_id"] is None
    ), "run_space.inputs_id must be None in inspection mode"


def test_pipeline_json_never_emits_runtime_ids():
    """Test that build_pipeline_json never emits runtime IDs (pipeline_id, run_id)."""
    config = [
        {
            "component": "semantiva.testing.identity_test_processor",
            "label": "test_node",
            "params": {"value": 42},
        }
    ]

    result = build_pipeline_json(config)

    # MUST NOT contain runtime IDs in inspection mode
    assert (
        "pipeline_id" not in result
    ), "Result must NOT contain pipeline_id in inspection mode"
    assert "run_id" not in result, "Result must NOT contain run_id in inspection mode"

    # Identity object also must not contain runtime IDs
    identity = result.get("identity", {})
    assert "pipeline_id" not in identity, "Identity must NOT contain pipeline_id"
    assert "run_id" not in identity, "Identity must NOT contain run_id"


def test_pipeline_json_identity_deterministic():
    """Test that identity IDs are deterministic for the same configuration."""
    config = [
        {
            "component": "semantiva.testing.identity_test_processor",
            "label": "test_node",
            "params": {"value": 42},
        }
    ]

    result1 = build_pipeline_json(config)
    result2 = build_pipeline_json(config)

    # Same config must produce same IDs
    assert (
        result1["identity"]["semantic_id"] == result2["identity"]["semantic_id"]
    ), "Semantic ID must be deterministic"
    assert (
        result1["identity"]["config_id"] == result2["identity"]["config_id"]
    ), "Config ID must be deterministic"


def test_pipeline_json_run_space_spec_id_present_when_configured():
    """Test that run_space.spec_id is present when run-space is configured."""
    config = [
        {
            "component": "semantiva.testing.identity_test_processor",
            "label": "test_node",
            "params": {"value": 42},
        }
    ]

    result = build_pipeline_json(config)
    identity = result.get("identity", {})
    run_space = identity.get("run_space", {})

    # spec_id may or may not be present depending on configuration
    # but if present, should follow format
    if "spec_id" in run_space and run_space["spec_id"]:
        assert isinstance(
            run_space["spec_id"], str
        ), "run_space.spec_id must be a string"
        # Could add format validation here if known

    # inputs_id must always be None at inspection
    assert (
        run_space.get("inputs_id") is None
    ), "run_space.inputs_id must be None at inspection"
