# ComfyUI Multi Reference Latent

> 中文 | [English](#english)

把**最多 6 张参考图**一次性注入 conditioning 的单节点,专为 **FLUX.2 dev / klein** 这类吃 `reference_latents` 的图像编辑模型设计。每张图有独立的 `strength`,**`strength = 0` 就跳过那张图** —— 于是一个静态工作流就能覆盖 0~6 张参考图,不用 bypass、不用动态改线、不用为不同图数准备多个工作流。

## 它解决什么

ComfyUI 原生 `ReferenceLatent` 一次只喂一张参考图,要多张就得手动把多个 `ReferenceLatent` 串起来,而且没有逐图强度控制。本节点:

- **一个节点喂多张**(≤6),内部按原生 `reference_latents` append 语义逐张拼接;
- **每张独立 strength**(范围 `0 ~ 5`),`0 = 跳过`,`1.0 = 原生强度`,`>1 增强`;
- **内置 VAE 编码**,直接接 `IMAGE`,不用每张图外挂一个 `VAEEncode`;
- **全 optional**:一张都不接 → conditioning 原样透传(等于纯文生图)。

## 安装

- **ComfyUI Manager**:搜 `Multi Reference Latent` 安装。
- **手动**:`git clone https://github.com/lynclee/comfyui_multi_referencelatent` 到 `ComfyUI/custom_nodes/`,重启。

## 接线

```
CLIPTextEncode ──conditioning──┐
                               ▼
            ┌──────────────────────────────┐
LoadImage ─►│ image_1   strength_1 = 1.0   │
LoadImage ─►│ image_2   strength_2 = 0.8   │──conditioning──► (接 sampler 的 positive)
            │ image_3   strength_3 = 0  ⟵跳过
            │ ...                          │
VAELoader ─►│ vae                          │
            └──────────────────────────────┘
```

- `conditioning`(必填):一般接正向 `CLIPTextEncode`。
- `vae`(接了图才需要):接 `VAELoader`,用来把参考图编码成 latent。
- `image_1..image_6`(可选):参考图。
- `strength_1..strength_6`:对应图的强度;**留 0 = 该槽不参与**,可只接想用的那几张。

## 一个工作流覆盖 0~6 图

把 6 个图槽留着,想用几张就接几张(或者把不想要的那张 `strength` 调 0)。提交时不参与的槽不产生任何 latent,**云端/本地行为完全一致**,无需为不同图数维护多份工作流。

## strength 怎么作用(以及它的局限)

`reference_latents` 在 conditioning 里只是一串 latent,模型对其中每个 latent **没有独立的权重输入**。所以在 conditioning 这一层,"调强度"唯一能做的就是缩放这张图自己的 latent 数值。这是**近似**,不是干净的"影响力旋钮"——缩放会顺带改变 latent 在 VAE 空间的分布:

- `1.0`:模型原生行为,**最可靠**(等于把这张图原样喂进去);
- `0`:整张跳过,完全不进 conditioning,**可靠**;
- `0 < s < 1`:弱化,近似,可能伴随轻微的内容呈现变化;
- `s > 1`:放大,谨慎用,容易过曝/失真。

把它当"开关 + 微调"用最稳:确定要不要某张图(0 / 1.0),需要时再小幅增减。

### strength_mode:手动 / 自动归一化

节点上有个 `strength_mode` 开关:

- `manual`(默认):每张图各用各自的 strength,行为同上;
- `normalize`:把所有有效图的 strength **按总和归一化(和=1)**,保留你设的相对比例。例如三张设 `2/1/1` → `0.5/0.25/0.25`;全设 `1` → `0.333/0.333/0.333`(即自动均分)。接几张就自动分几份,不必手动改。

两种模式下 `strength=0` 都仍表示**跳过该图**,归一化只在剩下的有效图之间分配。

> 提醒:归一化让"总权重"恒为 1,但因为 strength 本质是缩放 latent(见上),图越多每张被压得越低,可能整体发灰。`normalize` 适合"懒得逐个填、要按比例自动分"的场景;追求单图保真时用 `manual` + `1.0`。

## 显存与分辨率

每张参考图都会被 VAE 编码成 latent 并占用模型上下文,**多张高分辨率图会显著增加显存和 token 数**。建议在接入前用上游节点把参考图缩到合理尺寸(例如长边 ≤1024),尤其是同时接 4~6 张时。本节点刻意不内置自动缩放,把分辨率决策留给你的工作流。

## 许可

MIT。基于 ComfyUI 公开的原生 `ReferenceLatent` 机制独立实现。

---

<a name="english"></a>

# ComfyUI Multi Reference Latent (English)

> [中文](#comfyui-multi-reference-latent) | English

A single node that injects **up to 6 reference images** into conditioning, built for **FLUX.2 dev / klein** and other edit models that consume `reference_latents`. Each image has its own `strength`, and **`strength = 0` skips that image** — so one static workflow covers 0–6 references without bypass, rewiring, or multiple workflows.

## What it solves

Native `ReferenceLatent` feeds one reference at a time and has no per-image strength. This node:

- **Feeds many in one node** (≤6), chaining them with the native `reference_latents` append semantics;
- **Per-image strength** (range `0–5`): `0 = skip`, `1.0 = native`, `>1` stronger;
- **Built-in VAE encode** — wire `IMAGE` directly, no per-image `VAEEncode`;
- **All optional** — connect nothing and conditioning passes through unchanged (plain text-to-image).

## Install

- **ComfyUI Manager**: search `Multi Reference Latent`.
- **Manual**: `git clone https://github.com/lynclee/comfyui_multi_referencelatent` into `ComfyUI/custom_nodes/`, restart.

## Inputs

- `conditioning` (required): usually your positive `CLIPTextEncode`.
- `vae` (needed only when images are connected): from `VAELoader`.
- `image_1..image_6` (optional): reference images.
- `strength_1..strength_6`: per-image strength; **leave 0 to disable that slot**.

## One workflow, 0–6 images

Keep all 6 slots; wire as many as you need (or set an unwanted image's `strength` to 0). Disabled slots produce no latent at all, so behavior is identical locally and on any backend — no need to maintain separate workflows per image count.

## How strength works (and its limits)

`reference_latents` is just a list of latents in the conditioning; the model has **no per-latent weight input**. So at the conditioning level the only thing "strength" can do is scale that image's own latent values. This is an **approximation**, not a clean influence knob — scaling also shifts the latent's distribution in VAE space:

- `1.0`: native behavior, **most reliable** (feeds the image as-is);
- `0`: the image is skipped entirely, **reliable**;
- `0 < s < 1`: weaker, approximate, may slightly alter how the reference reads;
- `s > 1`: stronger, use sparingly — prone to over-exposure / artifacts.

Treat it as a switch plus fine-tune: decide whether an image is in (0 / 1.0), then nudge if needed.

### strength_mode: manual / auto-normalize

The node has a `strength_mode` switch:

- `manual` (default): each image uses its own strength, as above;
- `normalize`: all active strengths are **normalized to sum to 1**, keeping your relative ratios. E.g. three images at `2/1/1` → `0.5/0.25/0.25`; all `1` → `0.333/0.333/0.333` (auto-equal). Wire any number of images and they auto-split.

In both modes `strength=0` still **skips** that image; normalization only distributes across the remaining active ones.

> Note: normalizing keeps total weight at 1, but since strength scales the latent (see above), more images means each is pushed lower and the result may turn flat/grey. Use `normalize` when you want hands-off proportional splitting; use `manual` + `1.0` when single-image fidelity matters.

## VRAM & resolution

Every reference image is VAE-encoded into a latent that occupies model context, so **several high-resolution images noticeably increase VRAM and token count**. Resize references upstream to a sane size (e.g. long edge ≤1024) before wiring them in, especially with 4–6 images at once. This node deliberately ships no auto-resize — the resolution decision stays in your workflow.

## License

MIT. An independent implementation built on ComfyUI's public native `ReferenceLatent` mechanism.
