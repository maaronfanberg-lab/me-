"""Real, isolated OBLITERATUS concept-steering pilot. Does not touch live Room."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

MODEL_ID = "HuggingFaceTB/SmolLM2-135M-Instruct"
REVISION = "12fd25f77366fa6b3b4b768ec3050bf629380bac"
CONCEPT = "contextually-correct-versus-swapped-answer"
OBJECTS = [
    "notebook", "compass", "lantern", "pencil", "scarf", "telescope", "mug", "umbrella",
    "timetable", "key", "photograph", "map", "sketch", "violin", "stone", "ribbon",
    "camera", "book", "postcard", "glove", "sundial", "jar", "hat", "folder",
    "passport", "bottle", "ruler", "bell", "mirror", "blanket", "brush", "ticket",
    "flashlight", "candle", "coin", "feather", "tablet", "basket", "chalk", "letter",
    "spoon", "wallet", "model", "flask", "bookmark", "button", "clock", "rope",
    "teapot", "painting", "needle", "pendant", "diagram", "globe", "pendulum", "record",
]
PLACES = [
    "on the blue shelf", "beside the window", "under the wooden desk",
    "near the garden gate", "inside the woven basket", "next to the lamp",
    "above the fireplace", "behind the green chair", "by the hallway door",
    "under the old bench", "on the kitchen table", "beside the small plant",
]


def examples(start, end):
    """Counterbalanced contextual correctness; matched text/word distributions.

    Each object has two mirror-image contexts and the SAME two possible answers.
    The positive examples answer using the actual observed sign; the matched
    controls give the other location. This eliminates basic unigram/trigram
    shortcuts that invalidated the first natural-language contrast.
    """
    groups = {"positive": [], "wrong_answer": []}
    for i, item in enumerate(OBJECTS[start:end], start=start):
        left = PLACES[(i * 3) % len(PLACES)]
        right = PLACES[(i * 3 + 5) % len(PLACES)]
        for correct, incorrect in ((left, right), (right, left)):
            # Both candidate completions occur verbatim in both class prompts.
            # Under OBLITERATUS's binary word/char-trigram lexical features,
            # correct and swapped completions therefore have identical sets.
            prefix = (
                f"Mara: Candidate sentences: Sarah: The {item} is {left}. "
                f"Sarah: The {item} is {right}. "
                f"I checked the label: the correct location for the {item} "
                f"is {correct}, not {incorrect}. Which candidate is supported?\\nSarah: "
            )
            groups["positive"].append(prefix + f"The {item} is {correct}.")
            groups["wrong_answer"].append(prefix + f"The {item} is {incorrect}.")
    return groups


def activations(model, tokenizer, texts, layer):
    import torch
    results = []
    with torch.inference_mode():
        for value in texts:
            tokens = tokenizer(value, return_tensors="pt", max_length=128, truncation=True)
            states = model(**tokens, use_cache=False, output_hidden_states=True).hidden_states
            results.append(states[layer + 1][0, -1, :].float().cpu())
    return torch.stack(results)


def import_trial_module():
    path = Path(__file__).with_name("ab_trial.py")
    spec = importlib.util.spec_from_file_location("isolated_ab_trial", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(model_path, cases_file, output_path, n_cases, max_tokens):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from obliteratus.concepts.target import ExtractionRecipe
    from obliteratus.concepts.extraction import extract_directions
    from obliteratus.concepts.gate import ActivationCache, validate_direction
    from obliteratus.concepts import apply_concept_intervention
    from contextlib import contextmanager

    torch.set_num_threads(2)
    torch.manual_seed(1949)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True,
                                               trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(str(model_path), local_files_only=True,
                  trust_remote_code=False, torch_dtype=torch.float32).eval()
    if model.config.model_type != "llama" or not tokenizer.chat_template:
        raise RuntimeError("Expected local dense Llama model with a chat template")
    layer = max(1, model.config.num_hidden_layers // 2)
    training = examples(0, 24)
    heldout = examples(24, 44)
    train_features = {k: activations(model, tokenizer, v, layer) for k,v in training.items()}
    held_features = {k: activations(model, tokenizer, v, layer) for k,v in heldout.items()}
    recipe = ExtractionRecipe(method="diff_means", pool_controls="mean_of_means",
        layer_select={"strategy": "preset", "folds": 4},
        intervention_layer={"rule": "same"})
    pack_hash = hashlib.sha256(json.dumps(
        {"train": training, "heldout": heldout}, sort_keys=True).encode()).hexdigest()
    direction = extract_directions(
        {layer: train_features["positive"]},
        {k: {layer:v} for k,v in train_features.items() if k != "positive"},
        recipe, seed=1949, model_id=MODEL_ID, model_revision=REVISION,
        concept_id=CONCEPT, pack_hash=pack_hash)
    validation = validate_direction(direction, ActivationCache(
        positive={layer: held_features["positive"]},
        controls={k: {layer:v} for k,v in held_features.items() if k != "positive"},
        texts=(heldout["positive"],
               {k:v for k,v in heldout.items() if k != "positive"})),
        random_directions=256)
    direction.validation = validation
    report = {
        "kind": "real_pretrained_model_and_conditional_reversible_steering",
        "model_id": MODEL_ID, "model_revision": REVISION, "OBLITERATUS_version": "v0.1.4",
        "concept_id": CONCEPT, "activation_layer": layer,
        "training_examples_per_class": 48, "independent_validation_per_class":40,
        "split": "distinct fictional objects; counterbalanced matched-vocabulary correct/incorrect answers",
        "validation": validation, "neural_activations_measured": True,
        "steering_executed": False, "production_room_modified": False,
        "limitations": [
            "135M experimental model is not the 3B quantized production Room model.",
            "Lexical confounds, shared answer templates and short prompts limit transfer.",
            "No continuous five-person dialogue or persistent memory was tested.",
            "No full collateral safety, KL, or KV-cache evaluation was performed.",
            "Single-turn output changes do not demonstrate improved naturalness.",
        ],
    }
    if validation["verdict"] == "fail":
        report["status"] = "VALIDATION_FAILED_NO_STEERING"
    else:
        trial = import_trial_module()
        cases = trial.load_cases(cases_file)[:n_cases]
        def generate(messages):
            ids = tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True, return_tensors="pt")
            with torch.inference_mode():
                seq = model.generate(
                    input_ids=ids, do_sample=False, max_new_tokens=max_tokens,
                    pad_token_id=tokenizer.eos_token_id, eos_token_id=tokenizer.eos_token_id)
            return tokenizer.decode(
                seq[0, ids.shape[1]:], skip_special_tokens=True).strip()
        @contextmanager
        def intervention(alpha):
            with apply_concept_intervention(
                model, direction, "steer", layers="intervention",
                positions="final_token", alpha=alpha, rho=0.4):
                yield
        comparison = trial.run_trial(cases, generate, intervention, [0.0, -0.5, 0.5])
        report["steering_executed"] = True
        report["trial"] = comparison
        report["status"] = (
            "STEERED_AND_RESTORED" if comparison["passed_controls"] else "CONTROLS_FAILED")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n",encoding="utf-8")
    print("PILOT_RESULT " + json.dumps({
        "status":report["status"],
        "validation":validation["verdict"],
        "steering_executed":report["steering_executed"],
        "controls_passed": report.get("trial",{}).get("passed_controls"),
    }), flush=True)
    return 0 if report["status"] != "CONTROLS_FAILED" else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cases", type=Path,
                        default=Path(__file__).with_name("synthetic_cases.json"))
    parser.add_argument("--n-cases", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=36)
    args = parser.parse_args()
    if not 3 <= args.n_cases <= 20 or not 8 <= args.max_tokens <= 80:
        parser.error("Case count or token budget out of range")
    if args.out.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error("Experiment reports must never be written inside Room repository")
    if not args.model_dir.is_dir():
        parser.error("A separately downloaded pinned model is required")
    return run(args.model_dir, args.cases, args.out, args.n_cases, args.max_tokens)


if __name__ == "__main__":
    raise SystemExit(main())
