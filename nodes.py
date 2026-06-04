"""
MultiReferenceLatent (comfyui_multi_referencelatent) — 一个节点喂多张参考图(最多 6 张),每张独立 strength 开关。

机制对齐 ComfyUI 原生 ReferenceLatent(advanced/conditioning/edit_models):
  conditioning_set_values(cond, {"reference_latents": [latent_samples]}, append=True)
原生节点一次只喂一张、要串联多个;本节点把"串联 N 张 + 内置 VAE 编码 + 每张 strength"
合到一个节点里,适合 flux2 dev / klein 等吃 reference_latents 的编辑模型。

为什么 strength 用乘 latent 实现:reference_latents 是直接拼进 conditioning 的 latent 列表,
没有独立权重位;按 ComfyUI 社区通行做法,把该图 latent 整体 ×strength 来调它的影响,
strength=1.0 等于原生行为,0 则该图完全不参与(跳过,不拼)。

全部 image 输入 optional:
  - 一张都不接 → conditioning 原样透传(等于纯文生图,不加任何 reference)
  - 接 N 张且 strength≠0 → 把这 N 张 append 进 reference_latents
"""
import node_helpers

MAX_REFS = 6


class MultiReferenceLatent:
    @classmethod
    def INPUT_TYPES(cls):
        optional = {"vae": ("VAE",)}
        for i in range(1, MAX_REFS + 1):
            optional[f"image_{i}"] = ("IMAGE",)
            optional[f"strength_{i}"] = ("FLOAT", {
                "default": 1.0, "min": -5.0, "max": 10.0, "step": 0.05,
                "tooltip": f"参考图 {i} 的影响强度。0 = 该图不参与;1.0 = 原生强度;>1 增强;<0 反向参考。",
            })
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
            },
            "optional": optional,
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "apply"
    CATEGORY = "advanced/conditioning/edit_models"
    DESCRIPTION = ("一个节点喂多张参考图(≤6),每张独立 strength(0=跳过)。"
                   "用于 flux2 dev/klein 等编辑模型。不接图=纯透传(文生图)。")

    def _encode(self, vae, image):
        # 与 ComfyUI 内置 VAEEncode 一致:取 RGB 三通道编码
        return vae.encode(image[:, :, :, :3])

    def apply(self, conditioning, vae=None, **kwargs):
        refs = []
        for i in range(1, MAX_REFS + 1):
            img = kwargs.get(f"image_{i}")
            strength = kwargs.get(f"strength_{i}", 1.0)
            if img is None or strength == 0:
                continue  # 没接图 / strength=0 → 跳过该图
            if vae is None:
                raise ValueError("接了参考图但没连 vae —— 请把 VAELoader 连到 vae 输入。")
            samples = self._encode(vae, img)
            if strength != 1.0:
                samples = samples * strength  # 整体缩放调影响强度
            refs.append(samples)

        if not refs:
            return (conditioning,)  # 一张都没有效 → 原样透传(纯文生图)

        # 逐张 append 进 reference_latents(对齐原生 ReferenceLatent 的 append 语义)
        out = conditioning
        for samples in refs:
            out = node_helpers.conditioning_set_values(
                out, {"reference_latents": [samples]}, append=True
            )
        return (out,)


NODE_CLASS_MAPPINGS = {
    "MultiReferenceLatent": MultiReferenceLatent,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiReferenceLatent": "Multi Reference Latent (≤6, per-image strength)",
}
