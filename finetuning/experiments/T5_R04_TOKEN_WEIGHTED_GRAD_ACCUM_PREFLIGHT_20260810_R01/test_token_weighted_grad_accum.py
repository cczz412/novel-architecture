import argparse
import ast
import hashlib
import importlib
import json
import math
import struct
import sys
from functools import partial
from importlib.metadata import version
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
SOURCE_VENDOR = (
    REPO_ROOT
    / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
)
DERIVED_VENDOR = PACKAGE_ROOT / "vendor_token_weighted"
SOURCE_TRAINER = SOURCE_VENDOR / "mlx_lm/tuner/trainer.py"
DERIVED_TRAINER = DERIVED_VENDOR / "mlx_lm/tuner/trainer.py"
EXPECTED_SOURCE_TRAINER_SHA256 = (
    "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909"
)
RTOL = 1e-5
ATOL = 1e-6


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def non_cache_files(root):
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    }


def load_functions_from_trainer():
    source = DERIVED_TRAINER.read_text(encoding="utf-8")
    module = ast.parse(source)
    wanted = {
        "require_single_process",
        "accumulate_token_weighted_gradients",
        "finalize_token_weighted_gradients",
    }
    nodes = [
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name in wanted
    ]
    assert {node.name for node in nodes} == wanted

    def tree_map(function, *trees):
        if isinstance(trees[0], list):
            return [tree_map(function, *items) for items in zip(*trees)]
        return function(*trees)

    namespace = {"tree_map": tree_map}
    extracted = ast.Module(body=nodes, type_ignores=[])
    exec(compile(extracted, str(DERIVED_TRAINER), "exec"), namespace)
    return namespace


def function_ast(path, function_name):
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return ast.dump(node, include_attributes=False)
    raise AssertionError(f"Missing function: {function_name}")


def f32(value):
    return struct.unpack("f", struct.pack("f", float(value)))[0]


def sample_signals():
    tokens = [f32(value) for value in range(1, 9)]
    signals = [
        [
            f32(0.25 + token**2),
            f32((-1.0 if index % 2 else 1.0) * (token + 0.5)),
            f32(0.125 * token**3 - token),
        ]
        for index, token in enumerate(tokens, start=1)
    ]
    return tokens, signals


PAIRING_A = ((1, 8), (2, 7), (3, 6), (4, 5))
PAIRING_B = ((1, 2), (3, 4), (5, 6), (7, 8))


def microbatch_mean(pair, tokens, signals):
    indices = [value - 1 for value in pair]
    total = f32(sum(tokens[index] for index in indices))
    mean_gradient = []
    for component in range(len(signals[0])):
        numerator = f32(0)
        for index in indices:
            weighted = f32(signals[index][component] * tokens[index])
            numerator = f32(numerator + weighted)
        mean_gradient.append(f32(numerator / total))
    return mean_gradient, total


def run_new_reducer(pairing, tokens, signals):
    functions = load_functions_from_trainer()
    accumulate = functions["accumulate_token_weighted_gradients"]
    finalize = functions["finalize_token_weighted_gradients"]
    numerator = None
    token_total = f32(0)
    for pair in pairing:
        mean_gradient, microbatch_tokens = microbatch_mean(pair, tokens, signals)
        numerator, token_total = accumulate(
            mean_gradient,
            microbatch_tokens,
            numerator,
            token_total,
        )
    normalized, numerator, token_total_after_reset = finalize(
        numerator,
        token_total,
    )
    return {
        "gradient": [f32(value) for value in normalized],
        "token_total": float(token_total),
        "numerator_after_reset": numerator,
        "token_total_after_reset": float(token_total_after_reset),
        "optimizer_steps": 1,
    }


def run_old_reducer(pairing, tokens, signals):
    means = [microbatch_mean(pair, tokens, signals)[0] for pair in pairing]
    return [
        f32(sum(mean[component] for mean in means) / len(means))
        for component in range(len(means[0]))
    ]


def reference_gradient(tokens, signals):
    token_total = f32(sum(tokens))
    reference = []
    for component in range(len(signals[0])):
        numerator = f32(0)
        for token, signal in zip(tokens, signals):
            numerator = f32(numerator + f32(token * signal[component]))
        reference.append(f32(numerator / token_total))
    return reference


def sgd_state(gradient):
    initial = [f32(1.25), f32(-0.75), f32(0.5)]
    learning_rate = f32(0.01)
    delta = [f32(-learning_rate * value) for value in gradient]
    parameter = [f32(value + change) for value, change in zip(initial, delta)]
    return {"parameter": parameter, "delta": delta, "step": 1}


def adam_state(gradient):
    initial = [f32(1.25), f32(-0.75), f32(0.5)]
    learning_rate = f32(0.001)
    beta1 = f32(0.9)
    beta2 = f32(0.999)
    epsilon = f32(1e-8)
    step = 1
    moment = [f32(f32(1.0 - beta1) * value) for value in gradient]
    variance = [
        f32(f32(1.0 - beta2) * f32(value * value)) for value in gradient
    ]
    moment_hat = [f32(value / f32(1.0 - beta1**step)) for value in moment]
    variance_hat = [f32(value / f32(1.0 - beta2**step)) for value in variance]
    parameter = [
        f32(
            initial_value
            - f32(learning_rate * mean_value)
            / f32(f32(math.sqrt(variance_value)) + epsilon)
        )
        for initial_value, mean_value, variance_value in zip(
            initial,
            moment_hat,
            variance_hat,
        )
    ]
    return {
        "parameter": parameter,
        "m": moment,
        "v": variance,
        "step": step,
    }


def max_abs(left, right):
    return max(abs(float(a) - float(b)) for a, b in zip(left, right))


def assert_close(left, right):
    assert len(left) == len(right)
    for actual, expected in zip(left, right):
        assert math.isclose(actual, expected, rel_tol=RTOL, abs_tol=ATOL), (
            actual,
            expected,
        )


def collect_numeric_result():
    tokens, signals = sample_signals()
    result_a = run_new_reducer(PAIRING_A, tokens, signals)
    result_b = run_new_reducer(PAIRING_B, tokens, signals)
    reference = reference_gradient(tokens, signals)
    old_a = run_old_reducer(PAIRING_A, tokens, signals)
    old_b = run_old_reducer(PAIRING_B, tokens, signals)

    assert_close(result_a["gradient"], result_b["gradient"])
    assert_close(result_a["gradient"], reference)
    assert_close(result_b["gradient"], reference)
    old_ab_max_abs = max_abs(old_a, old_b)
    assert old_ab_max_abs > ATOL
    assert result_a["token_total"] == 36.0
    assert result_b["token_total"] == 36.0
    assert result_a["optimizer_steps"] == 1
    assert result_b["optimizer_steps"] == 1
    assert result_a["numerator_after_reset"] is None
    assert result_b["numerator_after_reset"] is None
    assert result_a["token_total_after_reset"] == 0.0
    assert result_b["token_total_after_reset"] == 0.0

    sgd_a = sgd_state(result_a["gradient"])
    sgd_b = sgd_state(result_b["gradient"])
    sgd_reference = sgd_state(reference)
    for field in ("parameter", "delta"):
        assert_close(sgd_a[field], sgd_b[field])
        assert_close(sgd_a[field], sgd_reference[field])

    adam_a = adam_state(result_a["gradient"])
    adam_b = adam_state(result_b["gradient"])
    adam_reference = adam_state(reference)
    for field in ("parameter", "m", "v"):
        assert_close(adam_a[field], adam_b[field])
        assert_close(adam_a[field], adam_reference[field])
    assert adam_a["step"] == adam_b["step"] == adam_reference["step"] == 1

    second_signals = [
        [f32(value * f32(-0.75)) for value in row] for row in reversed(signals)
    ]
    second_window = run_new_reducer(PAIRING_B, tokens, second_signals)
    second_reference = reference_gradient(tokens, second_signals)
    assert_close(second_window["gradient"], second_reference)
    assert second_window["token_total"] == 36.0
    assert second_window["token_total_after_reset"] == 0.0
    assert second_window["numerator_after_reset"] is None
    two_window_optimizer_steps = result_a["optimizer_steps"] + second_window[
        "optimizer_steps"
    ]
    assert two_window_optimizer_steps == 2

    ga1_mean, ga1_tokens = microbatch_mean((2, 7), tokens, signals)
    ga1_new = run_new_reducer(((2, 7),), tokens, signals)["gradient"]
    assert_close(ga1_new, ga1_mean)

    functions = load_functions_from_trainer()
    require_single_process = functions["require_single_process"]
    assert require_single_process(1) is None
    try:
        require_single_process(2)
    except RuntimeError as error:
        world_size_error = str(error)
    else:
        raise AssertionError("world_size=2 did not hard stop")

    return {
        "dtype": "float32",
        "sample_supervised_tokens": list(range(1, 9)),
        "pairing_a": [list(pair) for pair in PAIRING_A],
        "pairing_b": [list(pair) for pair in PAIRING_B],
        "rtol": RTOL,
        "atol": ATOL,
        "new_gradient_max_abs": {
            "a_vs_b": max_abs(result_a["gradient"], result_b["gradient"]),
            "a_vs_reference": max_abs(result_a["gradient"], reference),
            "b_vs_reference": max_abs(result_b["gradient"], reference),
        },
        "old_negative_control": {
            "a_vs_b_equal": False,
            "a_vs_b_max_abs": old_ab_max_abs,
        },
        "token_total": 36,
        "optimizer_steps": 1,
        "sgd_max_abs": {
            "parameter_a_vs_b": max_abs(
                sgd_a["parameter"], sgd_b["parameter"]
            ),
            "delta_a_vs_reference": max_abs(
                sgd_a["delta"], sgd_reference["delta"]
            ),
        },
        "adam_max_abs": {
            field: max_abs(adam_a[field], adam_b[field])
            for field in ("parameter", "m", "v")
        },
        "adam_step": 1,
        "two_window_reset": {
            "passed": True,
            "window_token_totals": [36, 36],
            "token_total_after_each_update": [0, 0],
            "optimizer_steps": two_window_optimizer_steps,
        },
        "ga1_compatibility": {
            "passed": True,
            "supervised_tokens": int(ga1_tokens),
            "max_abs": max_abs(ga1_new, ga1_mean),
        },
        "world_size_gate": {
            "world_size_1_passed": True,
            "world_size_2_hard_stopped": True,
            "error": world_size_error,
        },
    }


def collect_source_result():
    assert sha256_file(SOURCE_TRAINER) == EXPECTED_SOURCE_TRAINER_SHA256
    source_files = non_cache_files(SOURCE_VENDOR)
    derived_files = non_cache_files(DERIVED_VENDOR)
    assert set(source_files) == set(derived_files)
    changed = [
        relative
        for relative in sorted(source_files)
        if sha256_file(source_files[relative]) != sha256_file(derived_files[relative])
    ]
    assert changed == ["mlx_lm/tuner/trainer.py"]
    for function_name in ("default_loss", "iterate_batches", "evaluate"):
        assert function_ast(SOURCE_TRAINER, function_name) == function_ast(
            DERIVED_TRAINER,
            function_name,
        )

    derived_source = DERIVED_TRAINER.read_text(encoding="utf-8")
    train_ast = function_ast(DERIVED_TRAINER, "train")
    optimizer_step_ast = function_ast(
        DERIVED_TRAINER,
        "token_weighted_optimizer_step",
    )
    accumulate_ast = function_ast(
        DERIVED_TRAINER,
        "accumulate_token_weighted_gradients",
    )
    finalize_ast = function_ast(
        DERIVED_TRAINER,
        "finalize_token_weighted_gradients",
    )
    assert "require_single_process" in train_ast
    assert "token_weighted_optimizer_step" in train_ast
    assert "accumulate_token_weighted_gradients" in optimizer_step_ast
    assert "finalize_token_weighted_gradients" in optimizer_step_ast
    assert "optimizer" in optimizer_step_ast and "update" in optimizer_step_ast
    assert "Mult" in accumulate_ast and "supervised_tokens" in accumulate_ast
    assert "Add" in accumulate_ast and "token_total" in accumulate_ast
    assert "Div" in finalize_ast and "token_total" in finalize_ast
    assert "Mult" in finalize_ast and "Constant(value=0)" in finalize_ast
    step_source = derived_source.split("def step(batch", maxsplit=1)[1].split(
        "model.train()",
        maxsplit=1,
    )[0]
    assert "/ grad_accum_steps" not in step_source
    assert not any(
        "__pycache__" in path.parts or path.suffix == ".pyc"
        for path in DERIVED_VENDOR.rglob("*")
    )
    return {
        "source_trainer_sha256": sha256_file(SOURCE_TRAINER),
        "derived_trainer_sha256": sha256_file(DERIVED_TRAINER),
        "source_non_cache_file_count": len(source_files),
        "derived_non_cache_file_count": len(derived_files),
        "changed_files": changed,
        "unchanged_function_asts": [
            "default_loss",
            "iterate_batches",
            "evaluate",
        ],
        "optimizer_window_calls_actual_helpers": True,
        "compiled_train_step_calls_shared_optimizer_step": True,
        "old_grad_accumulation_steps_division_removed": True,
        "cache_files_present": False,
    }


def collect_mlx_smoke_result():
    sys.path.insert(0, str(DERIVED_VENDOR))
    trainer = importlib.import_module("mlx_lm.tuner.trainer")
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim

    class TinyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.bias = mx.array([0.1, -0.2, 0.3, 0.0], dtype=mx.float32)

        def __call__(self, inputs):
            return mx.broadcast_to(self.bias, (*inputs.shape, 4))

    def sample(sample_id):
        supervised_tokens = sample_id
        sequence = [
            (sample_id + position) % 4
            for position in range(supervised_tokens + 1)
        ]
        return sequence, (1, supervised_tokens + 1)

    def batch(sample_ids):
        samples = [sample(sample_id) for sample_id in sample_ids]
        max_length = max(len(sequence) for sequence, _ in samples)
        rows = [
            sequence + [0] * (max_length - len(sequence))
            for sequence, _ in samples
        ]
        lengths = [length for _, length in samples]
        return mx.array(rows), mx.array(lengths)

    def run(pairing):
        model = TinyModel()
        optimizer = optim.Adam(learning_rate=0.001)
        loss_value_and_grad = nn.value_and_grad(model, trainer.default_loss)
        state = [model.state, optimizer.state, mx.random.state]

        @partial(mx.compile, inputs=state, outputs=state)
        def compiled_step(
            microbatch,
            grad_numerator,
            token_total,
            do_update,
        ):
            return trainer.token_weighted_optimizer_step(
                loss_value_and_grad,
                model,
                optimizer,
                microbatch,
                grad_numerator,
                token_total,
                do_update,
            )

        grad_numerator = None
        token_total = mx.array(0, dtype=mx.float32)
        observed_tokens = 0
        for index, sample_ids in enumerate(pairing):
            loss, tokens, grad_numerator, token_total = compiled_step(
                batch(sample_ids),
                grad_numerator,
                token_total,
                index == len(pairing) - 1,
            )
            mx.eval(state, loss, tokens, grad_numerator, token_total)
            observed_tokens += int(tokens.item())
        assert grad_numerator is None
        optimizer_state = optimizer.state["bias"]
        moment = optimizer_state["m"].tolist()
        normalized_gradient = [f32(value / f32(1.0 - 0.9)) for value in moment]
        return {
            "parameter": model.bias.tolist(),
            "m": moment,
            "v": optimizer_state["v"].tolist(),
            "step": int(optimizer.state["step"].item()),
            "normalized_gradient_from_m": normalized_gradient,
            "observed_supervised_tokens": observed_tokens,
            "token_total_after_reset": float(token_total.item()),
        }

    run_a = run(PAIRING_A)
    run_b = run(PAIRING_B)
    run_reference = run(((1, 2, 3, 4, 5, 6, 7, 8),))
    for field in ("parameter", "m", "v", "normalized_gradient_from_m"):
        assert_close(run_a[field], run_b[field])
        assert_close(run_a[field], run_reference[field])
    for run_result in (run_a, run_b, run_reference):
        assert run_result["step"] == 1
        assert run_result["observed_supervised_tokens"] == 36
        assert run_result["token_total_after_reset"] == 0.0
    trainer.require_single_process(1)
    try:
        trainer.require_single_process(2)
    except RuntimeError:
        pass
    else:
        raise AssertionError("MLX runtime did not hard stop world_size=2")
    return {
        "performed": True,
        "python_executable": sys.executable,
        "mlx_version": version("mlx"),
        "qwen_loaded": False,
        "actual_path": [
            "default_loss",
            "nn.value_and_grad",
            "mx.compile",
            "token_weighted_optimizer_step",
            "optim.Adam.update"
        ],
        "a_vs_b_max_abs": {
            field: max_abs(run_a[field], run_b[field])
            for field in ("parameter", "m", "v", "normalized_gradient_from_m")
        },
        "a_vs_reference_max_abs": {
            field: max_abs(run_a[field], run_reference[field])
            for field in ("parameter", "m", "v", "normalized_gradient_from_m")
        },
        "observed_supervised_tokens": [36, 36, 36],
        "optimizer_steps": [1, 1, 1],
        "accumulator_reset": True,
        "world_size_2_hard_stopped": True,
    }


def build_result(run_mlx_smoke=False):
    result = {
        "status": "PASS_PREFLIGHT_NOT_RUN_AUTHORITY",
        "numeric_invariance": collect_numeric_result(),
        "source_binding": collect_source_result(),
        "mlx_runtime_smoke": {"performed": False, "qwen_loaded": False},
        "external_actions": {
            "qwen_loads": 0,
            "training_runs": 0,
            "inference_runs": 0,
            "api_calls": 0,
            "notion_writes": 0,
            "git_actions": 0,
        },
    }
    if run_mlx_smoke:
        result["mlx_runtime_smoke"] = collect_mlx_smoke_result()
    return result


def test_token_weighted_invariance_contract():
    build_result(run_mlx_smoke=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mlx-smoke", action="store_true")
    parser.add_argument("--write-result", type=Path)
    args = parser.parse_args()
    result = build_result(run_mlx_smoke=args.mlx_smoke)
    if args.write_result:
        args.write_result.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
