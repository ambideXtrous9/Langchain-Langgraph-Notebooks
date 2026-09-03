"""Unit Tests for Structured Output Classifier Agent."""

import pytest
from app.agents.classifier_agent import ClassifierAgent
from app.schemas.state import Classify


@pytest.mark.asyncio
async def test_classifier_pydantic_schema():
    """Tests Pydantic model validation on Classify output."""
    valid_data = {"classification": "policy", "reply": "POLICY"}
    obj = Classify(**valid_data)
    assert obj.classification == "policy"
    assert obj.reply == "POLICY"


@pytest.mark.asyncio
async def test_classifier_rule_fallback():
    """Tests classifier heuristic fallback when LLM is unavailable."""
    classifier = ClassifierAgent()

    exit_res = await classifier.aclassify("I want to exit now")
    assert exit_res["classification"] == "exit"
    assert exit_res["reply"] == "exit"

    policy_res = await classifier.aclassify("What is the compliance benchmark path for an enterprise data pipeline?")
    assert policy_res["classification"] == "policy"

    generic_res = await classifier.aclassify("Hello, good morning!")
    assert generic_res["classification"] == "generic"
