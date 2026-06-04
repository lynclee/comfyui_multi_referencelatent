# ComfyUI Multi Reference Latent

> 中文 | [English](#english)

把**最多 6 张参考图**一次性注入 conditioning 的单节点,专为 **FLUX.2 dev / klein** 这类吃 `reference_latents` 的图像编辑模型设计。每张图有独立的 `strength`,**`strength = 0` 就跳过那张图** —— 于是一个静态工作流就能覆盖 0~6 张参考图,不用 bypass、不用动态改线、不用为不同图数准备多个工作流。

## 它解决什么

ComfyUI 原生 `ReferenceLatent` 一次只喂一张参考图,要多张就得手动把多个 `ReferenceLatent` 串起来,而且没有逐图强度控制。本节点:

- **一个节点喂多张**(≤6),内部按原生 `reference_latents` append 语义逐张拼接;
- **每张独立 strength**,`0 = 跳过`,`1.0 = 原生强度`,`>1 增强`,`<0 反向参考`;
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

## strength 怎么作用

`reference_latents` 是直接拼进 conditioning 的 latent 列表,没有独立权重位。本节点按社区通行做法,把该图编码后的 latent **整体 ×strength** 来调它对生成的影响。`1.0` 等于原生 `ReferenceLatent` 行为。

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
- **Per-image strength**: `0 = skip`, `1.0 = native`, `>1` stronger, `<0` negative reference;
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

## How strength works

`reference_latents` has no separate weight field, so the encoded latent of each image is scaled by `strength`. `1.0` equals native `ReferenceLatent` behavior.

## License

MIT. An independent implementation built on ComfyUI's public native `ReferenceLatent` mechanism.
