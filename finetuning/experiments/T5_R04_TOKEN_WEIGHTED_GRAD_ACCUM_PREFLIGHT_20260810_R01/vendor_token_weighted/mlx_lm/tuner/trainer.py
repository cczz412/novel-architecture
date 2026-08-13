# Copyright © 2024 Apple Inc.


import time
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import numpy as np
from mlx.nn.utils import average_gradients
from mlx.utils import tree_flatten, tree_map
from tqdm import tqdm

from .callbacks import TrainingCallback
from .datasets import CacheDataset


IGNORE_INDEX = -100


def build_causal_lm_training_views(batch, lengths):
    """Build shifted inputs, explicit labels, and a right-padding attention mask.

    ``lengths`` stores ``(assistant_offset, real_sequence_length)``.  Target
    position ``k`` predicts the original token at absolute position ``k``;
    therefore real targets end at ``real_sequence_length - 1``.  Prompt and
    padding targets are written as ``IGNORE_INDEX`` while the assistant EOT
    remains a normal supervised token.
    """

    input_ids = batch[:, :-1]
    raw_labels = batch[:, 1:]
    target_positions = mx.arange(1, raw_labels.shape[1] + 1)
    input_positions = mx.arange(input_ids.shape[1])

    attention_mask = input_positions < (lengths[:, 1:2] - 1)
    label_mask = mx.logical_and(
        target_positions >= lengths[:, 0:1],
        target_positions < lengths[:, 1:2],
    )
    labels = mx.where(
        label_mask,
        raw_labels,
        mx.array(IGNORE_INDEX, raw_labels.dtype),
    )
    return input_ids, labels, attention_mask


def grad_checkpoint(layer):
    """
    Update all instances of type(layer) to use gradient checkpointing.
    """
    fn = type(layer).__call__

    def checkpointed_fn(model, *args, **kwargs):
        def inner_fn(params, *args, **kwargs):
            model.update(params)
            return fn(model, *args, **kwargs)

        return mx.checkpoint(inner_fn)(model.trainable_parameters(), *args, **kwargs)

    type(layer).__call__ = checkpointed_fn


@dataclass
class TrainingArgs:
    batch_size: int = field(default=4, metadata={"help": "Minibatch size."})
    iters: int = field(default=100, metadata={"help": "Iterations to train for."})
    val_batches: int = field(
        default=25,
        metadata={
            "help": "Number of validation batches, -1 uses the entire validation set."
        },
    )
    steps_per_report: int = field(
        default=10,
        metadata={"help": "Number of training steps between loss reporting."},
    )
    steps_per_eval: int = field(
        default=200, metadata={"help": "Number of training steps between validations."}
    )
    steps_per_save: int = field(
        default=100, metadata={"help": "Save the model every number steps"}
    )
    max_seq_length: int = field(
        default=2048, metadata={"help": "Maximum sequence length."}
    )
    adapter_file: str = field(
        default="adapters.safetensors",
        metadata={"help": "Save/load path for the trained adapter weights."},
    )
    grad_checkpoint: bool = field(
        default=False,
        metadata={"help": "Use gradient checkpointing to reduce memory use."},
    )
    grad_accumulation_steps: int = field(
        default=1,
        metadata={
            "help": "Number of steps to accumulate gradients before applying an optimizer update."
        },
    )


def default_loss(model, batch, lengths):
    inputs, labels, _ = build_causal_lm_training_views(batch, lengths)
    label_mask = labels != IGNORE_INDEX
    safe_labels = mx.where(label_mask, labels, mx.array(0, labels.dtype))

    logits = model(inputs)

    ce = nn.losses.cross_entropy(logits, safe_labels) * label_mask
    ntoks = label_mask.sum()
    ce = ce.astype(mx.float32).sum() / ntoks

    return ce, ntoks


def require_single_process(world_size):
    """Reject distributed runs before compiling the token-weighted reducer."""
    if world_size != 1:
        raise RuntimeError(
            "Token-weighted gradient accumulation requires world_size == 1."
        )


def accumulate_token_weighted_gradients(
    grad,
    supervised_tokens,
    grad_numerator,
    token_total,
):
    """Add one mean microbatch gradient to a token-weighted window numerator."""
    weighted_grad = tree_map(lambda x: x * supervised_tokens, grad)
    if grad_numerator is not None:
        weighted_grad = tree_map(
            lambda x, y: x + y,
            weighted_grad,
            grad_numerator,
        )
    return weighted_grad, token_total + supervised_tokens


def finalize_token_weighted_gradients(grad_numerator, token_total):
    """Normalize one optimizer window and reset both reducer accumulators."""
    normalized_grad = tree_map(lambda x: x / token_total, grad_numerator)
    return normalized_grad, None, token_total * 0


def token_weighted_optimizer_step(
    loss_value_and_grad,
    model,
    optimizer,
    batch,
    prev_grad_numerator,
    prev_token_total,
    do_update,
):
    """Run the actual loss-to-update path for one token-weighted microbatch."""
    (lvalue, toks), grad = loss_value_and_grad(model, *batch)
    grad_numerator, token_total = accumulate_token_weighted_gradients(
        grad,
        toks,
        prev_grad_numerator,
        prev_token_total,
    )

    if do_update:
        grad_numerator = average_gradients(grad_numerator)
        normalized_grad, grad_numerator, token_total = (
            finalize_token_weighted_gradients(grad_numerator, token_total)
        )
        optimizer.update(model, normalized_grad)

    return lvalue, toks, grad_numerator, token_total


def iterate_batches(
    dataset,
    batch_size,
    max_seq_length,
    loop=False,
    seed=None,
    comm_group=None,
):
    # A/C 单变量实验必须让配对样本进入同一批次。A 与 C 的文本长度不同，
    # 若沿用上游“按长度排序”会悄悄改变批次组成。教材已经用同一 pair_id
    # 顺序固定洗牌，因此这里保留文件顺序，再由相同 seed 随机化批次顺序。
    idx = list(range(len(dataset)))
    if len(dataset) < batch_size:
        raise ValueError(
            f"Dataset must have at least batch_size={batch_size}"
            f" examples but only has {len(dataset)}."
        )

    # If running in distributed mode (N machines) then each one should skip N-1
    # samples
    if comm_group is not None:
        offset = comm_group.rank()
        step = comm_group.size()
    else:
        offset = 0
        step = 1
    if batch_size % step != 0:
        raise ValueError("The batch size must be divisible by the number of workers")

    # Make the batches:
    batch_idx = [
        idx[i + offset : i + offset + batch_size : step]
        for i in range(0, len(idx) - batch_size + 1, batch_size)
    ]
    if seed:
        np.random.seed(seed)
    while True:
        indices = np.random.permutation(len(batch_idx))
        for i in indices:
            batch = [dataset[j] for j in batch_idx[i]]
            if len(batch[0]) == 2:
                batch, offsets = zip(*batch)
            else:
                offsets = [0] * len(batch)
            lengths = [len(x) for x in batch]
            if max(lengths) > max_seq_length:
                print(
                    f"[WARNING] Some sequences are longer than {max_seq_length} tokens. "
                    f"The longest sentence {max(lengths)} will be truncated to {max_seq_length}. "
                    "Consider pre-splitting your data to save memory."
                )

            # Pad to one plus nearest multiple of pad_to or the maximum length
            pad_to = 32
            max_length_in_batch = 1 + pad_to * ((max(lengths) + pad_to - 1) // pad_to)
            max_length_in_batch = min(max_length_in_batch, max_seq_length)

            batch_arr = np.zeros((batch_size // step, max_length_in_batch), np.int32)

            for j in range(batch_size // step):
                truncated_length = min(lengths[j], max_seq_length)
                batch_arr[j, :truncated_length] = batch[j][:truncated_length]
                lengths[j] = (
                    truncated_length  # Update lengths to match truncated lengths
                )
            batch = mx.array(batch_arr)
            yield batch, mx.array(list(zip(offsets, lengths)))

        if not loop:
            break


def evaluate(
    model,
    dataset,
    batch_size,
    num_batches,
    max_seq_length=2048,
    loss: callable = default_loss,
    iterate_batches: callable = iterate_batches,
):
    model.eval()
    all_losses = mx.array(0.0)
    ntokens = mx.array(0)

    index_iterator = iter(range(num_batches)) if num_batches != -1 else iter(int, 1)

    for _, batch in tqdm(
        zip(
            index_iterator,
            iterate_batches(
                dataset=dataset,
                batch_size=batch_size,
                max_seq_length=max_seq_length,
                comm_group=mx.distributed.init(),
            ),
        ),
        desc="Calculating loss...",
        total=min(len(dataset) // batch_size, num_batches),
    ):
        losses, toks = loss(model, *batch)
        all_losses += losses * toks
        ntokens += toks
        mx.eval(all_losses, ntokens)

    all_losses = mx.distributed.all_sum(all_losses, stream=mx.cpu)
    ntokens = mx.distributed.all_sum(ntokens, stream=mx.cpu)

    return (all_losses / ntokens).item()


def train(
    model,
    optimizer,
    train_dataset,
    val_dataset=None,
    args: TrainingArgs = TrainingArgs(),
    loss: callable = default_loss,
    iterate_batches: callable = iterate_batches,
    training_callback: TrainingCallback = None,
):
    if mx.metal.is_available():
        device_info = mx.metal.device_info()
        gib = 1024**3
        safe_wired_limit = min(
            device_info["max_recommended_working_set_size"], 20 * gib
        )
        mx.set_wired_limit(safe_wired_limit)
        mx.set_memory_limit(22 * gib)
        mx.set_cache_limit(1 * gib)
        print(
            "Local memory guard: "
            f"wired={safe_wired_limit / gib:.1f} GiB, "
            "memory=22.0 GiB, cache=1.0 GiB",
            flush=True,
        )
    print(f"Starting training..., iters: {args.iters}")
    world = mx.distributed.init()
    world_size = world.size()
    rank = world.rank()
    require_single_process(world_size)

    if args.grad_checkpoint:
        grad_checkpoint(model.layers[0])

    loss_value_and_grad = nn.value_and_grad(model, loss)

    grad_accum_steps = args.grad_accumulation_steps
    if grad_accum_steps < 1:
        raise ValueError("grad_accumulation_steps must be at least 1")

    state = [model.state, optimizer.state, mx.random.state]

    @partial(mx.compile, inputs=state, outputs=state)
    def step(batch, prev_grad_numerator, prev_token_total, do_update):
        return token_weighted_optimizer_step(
            loss_value_and_grad,
            model,
            optimizer,
            batch,
            prev_grad_numerator,
            prev_token_total,
            do_update,
        )

    model.train()
    losses = 0
    n_tokens = 0
    steps = 0
    trained_tokens = 0
    train_time = 0
    grad_accum = None
    grad_token_total = mx.array(0)

    # Main training loop
    for it, batch in zip(
        range(1, args.iters + 1),
        iterate_batches(
            dataset=train_dataset,
            batch_size=args.batch_size,
            max_seq_length=args.max_seq_length,
            loop=True,
            comm_group=world,
        ),
    ):
        tic = time.perf_counter()
        # Report validation loss if needed, the first validation loss
        # is always measured before any training.
        if val_dataset and (
            it == 1 or it % args.steps_per_eval == 0 or it == args.iters
        ):
            tic = time.perf_counter()
            val_loss = evaluate(
                model=model,
                dataset=val_dataset,
                loss=loss,
                batch_size=args.batch_size,
                num_batches=args.val_batches,
                max_seq_length=args.max_seq_length,
                iterate_batches=iterate_batches,
            )
            model.train()
            val_time = time.perf_counter() - tic
            if rank == 0:
                print(
                    f"Iter {it}: "
                    f"Val loss {val_loss:.3f}, "
                    f"Val took {val_time:.3f}s",
                    flush=True,
                )

            if training_callback is not None:
                val_info = {
                    "iteration": it - 1,
                    "val_loss": val_loss,
                    "val_time": val_time,
                }
                training_callback.on_val_loss_report(val_info)

            tic = time.perf_counter()

        lvalue, toks, grad_accum, grad_token_total = step(
            batch,
            grad_accum,
            grad_token_total,
            it % grad_accum_steps == 0,
        )

        losses += lvalue
        n_tokens += toks
        steps += 1
        mx.eval(state, losses, n_tokens, grad_accum, grad_token_total)
        if it % grad_accum_steps == 0:
            mx.clear_cache()
        train_time += time.perf_counter() - tic

        # Report training loss if needed
        if it % args.steps_per_report == 0 or it == args.iters:
            train_loss = mx.distributed.all_sum(losses, stream=mx.cpu).item()
            train_loss /= steps * world_size
            n_tokens = mx.distributed.all_sum(n_tokens, stream=mx.cpu).item()
            learning_rate = optimizer.learning_rate.item()
            it_sec = args.steps_per_report / train_time
            tokens_sec = float(n_tokens) / train_time
            trained_tokens += n_tokens
            peak_mem = mx.get_peak_memory() / 1e9
            if rank == 0:
                print(
                    f"Iter {it}: Train loss {train_loss:.3f}, "
                    f"Learning Rate {learning_rate:.3e}, "
                    f"It/sec {it_sec:.3f}, "
                    f"Tokens/sec {tokens_sec:.3f}, "
                    f"Trained Tokens {trained_tokens}, "
                    f"Peak mem {peak_mem:.3f} GB",
                    flush=True,
                )

            if training_callback is not None:
                train_info = {
                    "iteration": it,
                    "train_loss": train_loss,
                    "learning_rate": learning_rate,
                    "iterations_per_second": it_sec,
                    "tokens_per_second": tokens_sec,
                    "trained_tokens": trained_tokens,
                    "peak_memory": peak_mem,
                }
                training_callback.on_train_loss_report(train_info)

            losses = 0
            n_tokens = 0
            steps = 0
            train_time = 0

        # Save adapter weights
        if it % args.steps_per_save == 0 and rank == 0:
            adapter_weights = dict(tree_flatten(model.trainable_parameters()))
            mx.save_safetensors(str(args.adapter_file), adapter_weights)
            checkpoint = (
                Path(args.adapter_file).parent / f"{it:07d}_adapters.safetensors"
            )
            mx.save_safetensors(str(checkpoint), adapter_weights)
            print(
                f"Iter {it}: Saved adapter weights to "
                f"{args.adapter_file} and {checkpoint}."
            )

    # Save final weights
    if rank == 0:
        adapter_weights = dict(tree_flatten(model.trainable_parameters()))
        mx.save_safetensors(str(args.adapter_file), adapter_weights)
        print(f"Saved final weights to {args.adapter_file}.")
