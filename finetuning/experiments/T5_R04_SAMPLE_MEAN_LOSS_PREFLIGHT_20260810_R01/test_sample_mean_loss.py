import argparse
import ast
import hashlib
import importlib
import json
import sys
from functools import partial
from importlib.metadata import version
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:
    np = None


PACKAGE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_ROOT.parents[2]
SOURCE_VENDOR = (
    REPO_ROOT
    / "TEMP/T5_R04_SYNTHETIC_MICRO24_R01_PREFLIGHT/pipeline_r02/vendor_r02"
)
DERIVED_VENDOR = PACKAGE_ROOT / "vendor_sample_mean"
SOURCE_TRAINER = SOURCE_VENDOR / "mlx_lm/tuner/trainer.py"
DERIVED_TRAINER = DERIVED_VENDOR / "mlx_lm/tuner/trainer.py"
TRAIN96 = (
    REPO_ROOT
    / "finetuning/experiments/"
    "T5_R04_READ1_TRAIN96_TOKEN_WEIGHTED_QUALIFICATION_20260810_R01/"
    "READ_1_TARGET_TRAIN96.jsonl"
)
MODEL = (
    REPO_ROOT.parent
    / "小说架构_隔离实验/models/Qwen3-4B-Instruct-2507_cdbee75f"
)
EXPECTED_SOURCE_TRAINER_SHA256 = (
    "78a4d0d04e4b214a0eb5ebafe5be7dea934365287b5b91f80b0e3ff37145b909"
)
EXPECTED_TRAIN96_SHA256 = (
    "e059529d9ce39e7f9044f3d966dba00d0e19b2206098a827415473c38c46e4ad"
)
PAIRING_A = ((1, 8), (2, 7), (3, 6), (4, 5))
PAIRING_B = ((1, 2), (3, 4), (5, 6), (7, 8))
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


def tree_digest(root):
    digest = hashlib.sha256()
    for relative, path in sorted(non_cache_files(root).items()):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256_file(path)))
        digest.update(b"\0")
    return digest.hexdigest()


def function_ast(path, function_name):
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return ast.dump(node, include_attributes=False)
    raise AssertionError(f"Missing function: {function_name}")


def sample_signals():
    tokens = np.arange(1, 9, dtype=np.float32)
    signals = np.asarray(
        [
            [
                0.25 + token**2,
                (-1.0 if index % 2 else 1.0) * (token + 0.5),
                0.125 * token**3 - token,
            ]
            for index, token in enumerate(tokens, start=1)
        ],
        dtype=np.float32,
    )
    return tokens, signals


def sample_mean_window(pairing, signals):
    microbatch_gradients = []
    contribution_weights = np.zeros(len(signals), dtype=np.float32)
    for pair in pairing:
        indices = np.asarray([sample_id - 1 for sample_id in pair])
        microbatch_gradients.append(signals[indices].mean(axis=0))
        contribution_weights[indices] += 1.0 / len(pair) / len(pairing)
    return (
        np.asarray(microbatch_gradients, dtype=np.float32).mean(axis=0),
        contribution_weights,
    )


def old_microbatch_token_mean(pairing, tokens, signals):
    means = []
    for pair in pairing:
        indices = np.asarray([sample_id - 1 for sample_id in pair])
        pair_tokens = tokens[indices]
        numerator = (signals[indices] * pair_tokens[:, None]).sum(axis=0)
        means.append(numerator / pair_tokens.sum())
    return np.asarray(means, dtype=np.float32).mean(axis=0)


def global_token_mean(pairing, tokens, signals):
    numerator = np.zeros(signals.shape[1], dtype=np.float32)
    denominator = np.float32(0)
    for pair in pairing:
        indices = np.asarray([sample_id - 1 for sample_id in pair])
        pair_tokens = tokens[indices]
        numerator += (signals[indices] * pair_tokens[:, None]).sum(axis=0)
        denominator += pair_tokens.sum()
    return numerator / denominator


def sgd_state(gradient):
    initial = np.asarray([1.25, -0.75, 0.5], dtype=np.float32)
    delta = np.float32(-0.01) * gradient
    return {"parameter": initial + delta, "delta": delta, "step": 1}


def adam_state(gradient):
    initial = np.asarray([1.25, -0.75, 0.5], dtype=np.float32)
    beta1 = np.float32(0.9)
    beta2 = np.float32(0.999)
    learning_rate = np.float32(0.001)
    epsilon = np.float32(1e-8)
    moment = (np.float32(1) - beta1) * gradient
    variance = (np.float32(1) - beta2) * gradient * gradient
    moment_hat = moment / (np.float32(1) - beta1)
    variance_hat = variance / (np.float32(1) - beta2)
    parameter = initial - learning_rate * moment_hat / (
        np.sqrt(variance_hat) + epsilon
    )
    return {
        "parameter": parameter,
        "m": moment,
        "v": variance,
        "step": 1,
    }


def max_abs(left, right):
    return float(np.max(np.abs(np.asarray(left) - np.asarray(right))))


def assert_close(left, right):
    np.testing.assert_allclose(left, right, rtol=RTOL, atol=ATOL)


def collect_numeric_result():
    if np is None:
        raise RuntimeError("NUMPY_RUNTIME_REQUIRED_FOR_NUMERIC_PROOF")
    tokens, signals = sample_signals()
    sample_a, weights_a = sample_mean_window(PAIRING_A, signals)
    sample_b, weights_b = sample_mean_window(PAIRING_B, signals)
    sample_reference = signals.mean(axis=0)
    old_a = old_microbatch_token_mean(PAIRING_A, tokens, signals)
    old_b = old_microbatch_token_mean(PAIRING_B, tokens, signals)
    global_a = global_token_mean(PAIRING_A, tokens, signals)
    global_b = global_token_mean(PAIRING_B, tokens, signals)

    assert_close(sample_a, sample_b)
    assert_close(sample_a, sample_reference)
    assert_close(sample_b, sample_reference)
    assert_close(weights_a, np.full(8, 1 / 8, dtype=np.float32))
    assert_close(weights_b, np.full(8, 1 / 8, dtype=np.float32))
    old_ab_max_abs = max_abs(old_a, old_b)
    assert old_ab_max_abs > ATOL
    assert_close(global_a, global_b)
    global_vs_sample_max_abs = max_abs(global_a, sample_reference)
    assert global_vs_sample_max_abs > ATOL

    sgd_a = sgd_state(sample_a)
    sgd_b = sgd_state(sample_b)
    sgd_reference = sgd_state(sample_reference)
    for field in ("parameter", "delta"):
        assert_close(sgd_a[field], sgd_b[field])
        assert_close(sgd_a[field], sgd_reference[field])

    adam_a = adam_state(sample_a)
    adam_b = adam_state(sample_b)
    adam_reference = adam_state(sample_reference)
    for field in ("parameter", "m", "v"):
        assert_close(adam_a[field], adam_b[field])
        assert_close(adam_a[field], adam_reference[field])
    assert adam_a["step"] == adam_b["step"] == adam_reference["step"] == 1

    return {
        "dtype": "float32",
        "sample_supervised_tokens": tokens.astype(int).tolist(),
        "pairing_a": [list(pair) for pair in PAIRING_A],
        "pairing_b": [list(pair) for pair in PAIRING_B],
        "rtol": RTOL,
        "atol": ATOL,
        "sample_mean": {
            "a_vs_b_max_abs": max_abs(sample_a, sample_b),
            "a_vs_reference_max_abs": max_abs(sample_a, sample_reference),
            "b_vs_reference_max_abs": max_abs(sample_b, sample_reference),
            "per_sample_contribution_a": weights_a.tolist(),
            "per_sample_contribution_b": weights_b.tolist(),
            "each_sample_contribution": 0.125,
        },
        "old_microbatch_token_mean_negative_control": {
            "a_vs_b_equal": False,
            "a_vs_b_max_abs": old_ab_max_abs,
        },
        "global_token_mean_control": {
            "a_vs_b_max_abs": max_abs(global_a, global_b),
            "global_vs_sample_mean_max_abs": global_vs_sample_max_abs,
            "pair_invariant_but_not_sample_mean": True,
        },
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
    }


def collect_source_result():
    assert sha256_file(SOURCE_TRAINER) == EXPECTED_SOURCE_TRAINER_SHA256
    source_files = non_cache_files(SOURCE_VENDOR)
    derived_files = non_cache_files(DERIVED_VENDOR)
    assert set(source_files) == set(derived_files)
    changed = [
        relative
        for relative in sorted(source_files)
        if sha256_file(source_files[relative])
        != sha256_file(derived_files[relative])
    ]
    assert changed == ["mlx_lm/tuner/trainer.py"]
    for function_name in (
        "build_causal_lm_training_views",
        "iterate_batches",
        "evaluate",
        "train",
    ):
        assert function_ast(SOURCE_TRAINER, function_name) == function_ast(
            DERIVED_TRAINER, function_name
        )
    assert function_ast(SOURCE_TRAINER, "default_loss") != function_ast(
        DERIVED_TRAINER, "default_loss"
    )
    loss_ast = function_ast(DERIVED_TRAINER, "default_loss")
    assert "sample_ntoks" in loss_ast
    assert "sample_losses" in loss_ast
    assert "keyword(arg='axis', value=Constant(value=1))" in loss_ast
    assert "attr='mean'" in loss_ast
    assert not any(
        "__pycache__" in path.parts or path.suffix == ".pyc"
        for path in DERIVED_VENDOR.rglob("*")
    )
    return {
        "source_trainer_sha256": sha256_file(SOURCE_TRAINER),
        "derived_trainer_sha256": sha256_file(DERIVED_TRAINER),
        "source_vendor_tree_sha256": tree_digest(SOURCE_VENDOR),
        "derived_vendor_tree_sha256": tree_digest(DERIVED_VENDOR),
        "source_non_cache_file_count": len(source_files),
        "derived_non_cache_file_count": len(derived_files),
        "changed_files": changed,
        "unchanged_function_asts": [
            "build_causal_lm_training_views",
            "iterate_batches",
            "evaluate",
            "train",
        ],
        "only_default_loss_changed": True,
        "cache_files_present": False,
    }


def collect_train96_static_result(run_tokenizer=False):
    assert sha256_file(TRAIN96) == EXPECTED_TRAIN96_SHA256
    rows = [
        json.loads(line)
        for line in TRAIN96.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 96
    assert len(rows) % 2 == 0
    assert len(rows) // 2 == 48
    assert len(rows) // 8 == 12
    result = {
        "train96_path": str(TRAIN96.relative_to(REPO_ROOT)),
        "train96_sha256": sha256_file(TRAIN96),
        "rows": 96,
        "batch_size": 2,
        "complete_batches": 48,
        "grad_accumulation_steps": 4,
        "samples_per_optimizer_window": 8,
        "complete_optimizer_windows": 12,
        "partial_batches": 0,
        "partial_optimizer_windows": 0,
        "tokenizer_check_performed": False,
        "model_weights_loaded": False,
    }
    if run_tokenizer:
        sys.path.insert(0, str(DERIVED_VENDOR))
        from mlx_lm.tuner.datasets import ChatDataset
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            str(MODEL), local_files_only=True, trust_remote_code=True
        )
        dataset = ChatDataset(rows, tokenizer, mask_prompt=True)
        assistant_tokens = []
        sequence_tokens = []
        for row in rows:
            tokens, assistant_offset = dataset.process(row)
            assistant_tokens.append(len(tokens) - assistant_offset)
            sequence_tokens.append(len(tokens))
        assert min(assistant_tokens) == 6
        assert min(assistant_tokens) >= 1
        assert max(sequence_tokens) <= 4608
        result.update(
            {
                "tokenizer_check_performed": True,
                "tokenizer_class": type(tokenizer).__name__,
                "assistant_supervised_tokens_min": min(assistant_tokens),
                "assistant_supervised_tokens_max": max(assistant_tokens),
                "assistant_supervised_tokens_total": sum(assistant_tokens),
                "all_samples_have_supervised_tokens": True,
                "max_sequence_tokens": max(sequence_tokens),
                "samples_over_4608": sum(
                    value > 4608 for value in sequence_tokens
                ),
                "model_weights_loaded": False,
            }
        )
    return result


def collect_mlx_smoke_result():
    sys.path.insert(0, str(DERIVED_VENDOR))
    trainer = importlib.import_module("mlx_lm.tuner.trainer")
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.nn.utils import average_gradients
    from mlx.utils import tree_map

    assert Path(trainer.__file__).resolve() == DERIVED_TRAINER.resolve()

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

    def run_updates(windows, grad_accumulation_steps):
        model = TinyModel()
        optimizer = optim.Adam(learning_rate=0.001)
        loss_value_and_grad = nn.value_and_grad(model, trainer.default_loss)
        state = [model.state, optimizer.state, mx.random.state]

        @partial(mx.compile, inputs=state, outputs=state)
        def compiled_step(microbatch, prev_grad, do_update):
            (loss, tokens), grad = loss_value_and_grad(model, *microbatch)
            if prev_grad is not None:
                grad = tree_map(lambda x, y: x + y, grad, prev_grad)
            if do_update:
                grad = average_gradients(grad)
                if grad_accumulation_steps > 1:
                    grad = tree_map(
                        lambda value: value / grad_accumulation_steps, grad
                    )
                optimizer.update(model, grad)
                grad = None
            return loss, tokens, grad

        reset_after_windows = []
        observed_tokens = []
        for window in windows:
            grad = None
            window_tokens = 0
            for index, sample_ids in enumerate(window):
                loss, tokens, grad = compiled_step(
                    batch(sample_ids), grad, index == len(window) - 1
                )
                mx.eval(state, loss, tokens, grad)
                window_tokens += int(tokens.item())
            reset_after_windows.append(grad is None)
            observed_tokens.append(window_tokens)
        optimizer_state = optimizer.state["bias"]
        return {
            "parameter": model.bias.tolist(),
            "m": optimizer_state["m"].tolist(),
            "v": optimizer_state["v"].tolist(),
            "step": int(optimizer.state["step"].item()),
            "reset_after_windows": reset_after_windows,
            "observed_supervised_tokens": observed_tokens,
        }

    run_a = run_updates((PAIRING_A,), 4)
    run_b = run_updates((PAIRING_B,), 4)
    run_reference = run_updates((((1, 2, 3, 4, 5, 6, 7, 8),),), 1)
    for field in ("parameter", "m", "v"):
        assert_close(run_a[field], run_b[field])
        assert_close(run_a[field], run_reference[field])
    for run_result in (run_a, run_b, run_reference):
        assert run_result["step"] == 1
        assert run_result["reset_after_windows"] == [True]
        assert run_result["observed_supervised_tokens"] == [36]

    model = TinyModel()
    loss_value_and_grad = nn.value_and_grad(model, trainer.default_loss)
    (_, _), pair_grad = loss_value_and_grad(model, *batch((2, 7)))
    (_, _), first_grad = loss_value_and_grad(model, *batch((2,)))
    (_, _), second_grad = loss_value_and_grad(model, *batch((7,)))
    mx.eval(pair_grad, first_grad, second_grad)
    ga1_reference = [
        (left + right) / 2
        for left, right in zip(
            first_grad["bias"].tolist(), second_grad["bias"].tolist()
        )
    ]
    assert_close(pair_grad["bias"].tolist(), ga1_reference)

    two_windows = run_updates((PAIRING_A, PAIRING_B), 4)
    assert two_windows["step"] == 2
    assert two_windows["reset_after_windows"] == [True, True]
    assert two_windows["observed_supervised_tokens"] == [36, 36]

    return {
        "performed": True,
        "python_executable": sys.executable,
        "mlx_version": version("mlx"),
        "derived_trainer_imported": str(Path(trainer.__file__).resolve()),
        "qwen_loaded": False,
        "actual_path": [
            "sample_mean default_loss",
            "nn.value_and_grad",
            "mx.compile",
            "GA4 accumulation",
            "optim.Adam.update",
        ],
        "a_vs_b_max_abs": {
            field: max_abs(run_a[field], run_b[field])
            for field in ("parameter", "m", "v")
        },
        "a_vs_reference_max_abs": {
            field: max_abs(run_a[field], run_reference[field])
            for field in ("parameter", "m", "v")
        },
        "optimizer_steps": [run_a["step"], run_b["step"], run_reference["step"]],
        "ga1_two_sample_mean_max_abs": max_abs(
            pair_grad["bias"].tolist(), ga1_reference
        ),
        "two_consecutive_windows": {
            "optimizer_step": two_windows["step"],
            "reset_after_windows": two_windows["reset_after_windows"],
            "supervised_tokens": two_windows["observed_supervised_tokens"],
        },
    }


def build_result(run_mlx_smoke=False):
    result = {
        "status": "PASS_PREFLIGHT_NOT_RUN_AUTHORITY",
        "numeric_invariance": collect_numeric_result(),
        "source_binding": collect_source_result(),
        "train96_static": collect_train96_static_result(
            run_tokenizer=run_mlx_smoke
        ),
        "mlx_runtime_smoke": {"performed": False, "qwen_loaded": False},
        "external_actions": {
            "qwen_loads": 0,
            "training_runs": 0,
            "inference_runs": 0,
            "api_calls": 0,
            "notion_actions": 0,
            "git_actions": 0,
            "current_pointer_changes": 0,
            "run_roots_created": 0,
            "execution_tickets_created": 0,
        },
    }
    if run_mlx_smoke:
        result["mlx_runtime_smoke"] = collect_mlx_smoke_result()
    return result


def test_sample_mean_loss_static_contract():
    collect_source_result()
    collect_train96_static_result(run_tokenizer=False)


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
