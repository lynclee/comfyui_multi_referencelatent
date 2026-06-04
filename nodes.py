"""
comfyui_multi_referencelatent — MultiReferenceLatent

把若干张参考图(本节点上限 6)一次性挂进同一条 conditioning,供 FLUX.2 dev / klein
等"读 reference_latents 的编辑模型"使用。等价于把多个原生 ReferenceLatent 串成一串,
外加内置 VAE 编码与逐图开关,省掉重复连线。

实现只依赖 ComfyUI 公开的两个东西:
  1. vae.encode(pixels) —— 与内置 VAEEncode 同款,把像素图编码成 latent;
  2. node_helpers.conditioning_set_values(cond, {"reference_latents": [...]}, append=True)
     —— 原生 ReferenceLatent 用来把 latent 追加进 conditioning 的唯一入口。

关于 strength 的诚实说明:
  reference_latents 在 conditioning 里只是一串 latent,模型对每个 latent 没有独立的
  权重输入。因此"调强度"在 conditioning 这一层能做的只有一件事 —— 缩放该图的 latent
  数值本身。这是近似:缩放会一并改变 latent 在 VAE 空间的分布,并非纯粹的"影响力旋钮"。
    - strength == 1.0 : 模型原生行为(最可靠)
    - strength == 0   : 该图整张跳过,完全不进 conditioning(可靠)
    - 0 < strength < 1 : 弱化该图(近似,可能伴随轻微的内容呈现变化)
    - strength > 1     : 放大该图(谨慎,容易过曝/失真)

输入设计:
  conditioning 是唯一必填项。vae 与全部 image 均为可选。
    - 一张参考图都不接 → conditioning 原样返回(此时节点是个直通,等于纯文生图);
    - 接了 N 张有效图 → 逐张编码并追加,得到含 N 个 reference_latents 的 conditioning。
  好处:同一个静态工作流,接几张就生效几张,不必为不同参考图数量另存工作流,
  也不必动用 bypass 或改连线。
"""

import node_helpers

# 节点暴露的参考图槽位数量。要扩到更多,改这里即可,UI 与逻辑都按它生成。
NUM_SLOTS = 6


class MultiReferenceLatent:
    @classmethod
    def INPUT_TYPES(cls):
        slots = {"vae": ("VAE",)}
        for n in range(1, NUM_SLOTS + 1):
            slots[f"image_{n}"] = ("IMAGE",)
            slots[f"strength_{n}"] = ("FLOAT", {
                "default": 1.0,
                "min": 0.0,      # 0 = 跳过该图;不开放负值(负 latent 行为未定义)
                "max": 5.0,
                "step": 0.05,
                "tooltip": (
                    f"参考图 {n} 的强度。0=跳过该图;1.0=原生强度(最可靠);"
                    f"<1 弱化、>1 放大均为近似,见节点说明。"
                ),
            })
        return {
            "required": {"conditioning": ("CONDITIONING",)},
            "optional": slots,
        }

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "inject_references"
    CATEGORY = "advanced/conditioning/edit_models"
    DESCRIPTION = (
        "把至多 6 张参考图挂进 conditioning(FLUX.2 dev/klein 等编辑模型)。"
        "每张图独立 strength,0=跳过;一张不接则直通(纯文生图)。内置 VAE 编码。"
    )

    @staticmethod
    def _to_reference_latent(vae, image):
        """像素图 → 参考用 latent。取 RGB 三通道,丢弃可能存在的 alpha。"""
        rgb = image[..., :3]
        return vae.encode(rgb)

    def inject_references(self, conditioning, vae=None, **slots):
        # 先收集所有"有效"的参考图(接了图且 strength>0),顺序按槽位 1..N。
        encoded = []
        for n in range(1, NUM_SLOTS + 1):
            image = slots.get(f"image_{n}")
            weight = slots.get(f"strength_{n}", 1.0)
            if image is None or weight <= 0.0:
                continue
            if vae is None:
                raise ValueError(
                    f"image_{n} 接了参考图,但 vae 输入是空的。"
                    f"请把 VAELoader 连到本节点的 vae。"
                )
            latent = self._to_reference_latent(vae, image)
            # strength 即对该图 latent 的整体缩放;weight==1.0 时乘法恒等,不必特判。
            encoded.append(latent * weight)

        # 没有任何有效参考图 → 节点退化为直通,原样把 conditioning 传出去。
        if not encoded:
            return (conditioning,)

        # 逐张追加:每次把一个 latent append 进 reference_latents,
        # 累积成 [latent_1, latent_2, ...],与原生 ReferenceLatent 的串接语义一致。
        result = conditioning
        for latent in encoded:
            result = node_helpers.conditioning_set_values(
                result, {"reference_latents": [latent]}, append=True,
            )
        return (result,)


NODE_CLASS_MAPPINGS = {
    "MultiReferenceLatent": MultiReferenceLatent,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiReferenceLatent": "Multi Reference Latent (≤6, per-image strength)",
}
