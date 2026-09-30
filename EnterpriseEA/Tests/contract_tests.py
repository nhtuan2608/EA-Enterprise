"""Phase 1 contract smoke tests; they do not compile or execute the MQL5 EA."""
from __future__ import annotations

import json
from datetime import datetime
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def assert_minimum_contract(test: unittest.TestCase, schema: dict, instance: dict):
    """Validate required fields and a few shared primitive constraints without dependencies."""
    test.assertTrue(set(schema.get("required", [])).issubset(instance.keys()))
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        test.assertLessEqual(set(instance), set(properties))
    for name, value in instance.items():
        rule = properties.get(name, {})
        if "const" in rule:
            test.assertEqual(value, rule["const"], name)
        if "enum" in rule:
            test.assertIn(value, rule["enum"], name)
        if rule.get("type") == "array" and "items" in rule:
            item_rule = rule["items"]
            if "pattern" in item_rule:
                for item in value:
                    test.assertRegex(item, item_rule["pattern"])


def schema_errors(schema: dict, instance, base: Path | None = None) -> list[str]:
    """Small dependency-free validator for the keywords used by these contracts."""
    base = base or ROOT / "schemas"
    errors: list[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        referenced = json.loads((base / ref).read_text(encoding="utf-8"))
        return schema_errors(referenced, instance, (base / ref).parent)
    types = schema.get("type")
    if types:
        types = types if isinstance(types, list) else [types]
        type_ok = any(
            (t == "object" and isinstance(instance, dict)) or
            (t == "array" and isinstance(instance, list)) or
            (t == "string" and isinstance(instance, str)) or
            (t == "boolean" and isinstance(instance, bool)) or
            (t == "null" and instance is None) or
            (t == "integer" and isinstance(instance, int) and not isinstance(instance, bool)) or
            (t == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool))
            for t in types
        )
        if not type_ok:
            return [f"expected type {types}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"value {instance!r} is outside enum")
    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"missing required field {key}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance.keys() - props.keys():
                errors.append(f"unexpected field {key}")
        for key, value in instance.items():
            if key in props:
                errors.extend(f"{key}: {msg}" for msg in schema_errors(props[key], value, base))
    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(f"[{index}]: {msg}" for msg in schema_errors(schema["items"], item, base))
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append("string is too short")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            errors.append("string does not match pattern")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(instance.replace("Z", "+00:00"))
            except ValueError:
                errors.append("invalid date-time")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append("below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append("above maximum")
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            errors.append("below exclusive minimum")
    for child in schema.get("allOf", []):
        errors.extend(schema_errors(child, instance, base))
    condition = schema.get("if")
    if condition is not None:
        if not schema_errors(condition, instance, base):
            errors.extend(schema_errors(schema.get("then", {}), instance, base))
        elif "else" in schema:
            errors.extend(schema_errors(schema["else"], instance, base))
    return errors


class Phase1Contracts(unittest.TestCase):
    def test_all_json_documents_parse(self):
        for path in ROOT.rglob("*.json"):
            with self.subTest(path=path.relative_to(ROOT)):
                json.loads(path.read_text(encoding="utf-8"))

    def test_default_config_is_unselected_and_observer_only(self):
        config = load("config/observer-v1.0.0.json")
        schema = load("schemas/config.schema.json")
        assert_minimum_contract(self, schema, config)
        policy_schema = load("schemas/account-policy.schema.json")
        assert_minimum_contract(self, policy_schema, config["account_policy"])
        self.assertEqual(config["mode"], "OBSERVER_ONLY")
        self.assertEqual(config["symbol_registry"], [])
        self.assertEqual(config["account_policy"]["status"], "UNSELECTED")
        self.assertIsNone(config["account_policy"]["policy_id"])
        self.assertIsNone(config["account_policy"]["initial_capital"])
        self.assertEqual(schema_errors(schema, config), [])

    def test_event_and_snapshot_fixtures_have_minimum_envelopes(self):
        cases = [
            ("event-envelope.schema.json", "Tests/Fixtures/startup-event.json"),
            ("daily-snapshot.schema.json", "Tests/Fixtures/daily-snapshot-unselected.json"),
            ("portfolio-risk-snapshot.schema.json", "Tests/Fixtures/portfolio-risk-unknown.json"),
        ]
        for schema_name, fixture_name in cases:
            with self.subTest(schema=schema_name):
                assert_minimum_contract(self, load(f"schemas/{schema_name}"), load(fixture_name))

    def test_nested_shared_state_schema_and_fail_closed_cases(self):
        shared_schema = load("schemas/shared-state.schema.json")
        shared = load("Tests/Fixtures/shared-state-unselected.json")
        self.assertEqual(schema_errors(shared_schema, shared), [])

        policy_schema = load("schemas/account-policy.schema.json")
        invalid_active = load("Tests/Fixtures/invalid-active-policy.json")
        self.assertTrue(schema_errors(policy_schema, invalid_active), "ACTIVE policy with null inputs must fail")

        symbol_schema = load("schemas/symbol-registry.schema.json")
        unresolved = load("Tests/Fixtures/unresolved-symbol.json")
        self.assertEqual(schema_errors(symbol_schema, unresolved), [])
        unresolved["resolution_status"] = "RESOLVED"
        self.assertTrue(schema_errors(symbol_schema, unresolved), "RESOLVED symbol without broker metadata must fail")

    def test_ftmo_examples_match_specified_floor_arithmetic(self):
        example = load("Tests/Fixtures/phase1-policy-calculation-examples.json")
        initial = example["initial_capital"]
        reset_balance = example["reset_balance"]
        by_policy = {row["policy_id"]: row for row in example["examples"]}
        one = by_policy["FTMO_1_STEP"]
        two = by_policy["FTMO_2_STEP"]
        self.assertEqual(one["daily_floor"], reset_balance - initial * one["daily_loss_percent_of_initial"] / 100)
        self.assertEqual(one["overall_floor"], max(initial, reset_balance) - initial * one["overall_loss_percent_of_initial"] / 100)
        self.assertEqual(two["daily_floor"], reset_balance - initial * two["daily_loss_percent_of_initial"] / 100)
        self.assertEqual(two["overall_floor"], initial - initial * two["overall_loss_percent_of_initial"] / 100)
        high_water = initial
        sequence = []
        for balance in example["one_step_reset_balance_sequence"]:
            high_water = max(high_water, balance)
            sequence.append(high_water - initial * one["overall_loss_percent_of_initial"] / 100)
        self.assertEqual(sequence, example["one_step_expected_overall_floor_sequence"])

    def test_mql_entry_boundary_and_atomic_writer_are_explicit(self):
        main = (ROOT / "EnterpriseEA.mq5").read_text(encoding="utf-8")
        state = (ROOT / "Core/State.mqh").read_text(encoding="utf-8")
        writer = (ROOT / "Storage/AtomicWriter.mqh").read_text(encoding="utf-8")
        self.assertIn("if(InpObserverOnly==false)", main)
        self.assertIn("return false;", state)
        self.assertIn("EEA_StateCheckCheckpoint", main)
        self.assertIn("EEA_StateSave", main)
        self.assertIn("EEA_STATE_INCOMPATIBLE", main)
        self.assertNotRegex(main, r"\bOrderSend\s*\(")
        self.assertNotIn("CTrade", main)
        self.assertIn("path+\".tmp\"", writer)
        self.assertIn("FileMove(temp,0,path,FILE_REWRITE)", writer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
