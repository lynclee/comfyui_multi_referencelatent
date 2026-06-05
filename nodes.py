"""
comfyui_multi_referencelatent — MultiReferenceLatent

把若干张参考图一次性挂进同一条 conditioning,供 FLUX.2 dev / klein
等"读 reference_latents 的编辑模型"使用。等价于把多个原生 ReferenceLatent 串成一串,
外加内置 VAE 编码与逐图强度,省掉重复连线。

两种喂图方式,可单用也可并用:
  A) image_1..6 这些 IMAGE socket —— 画布手动用,连 LoadImage、能看预览。
  B) reference_list 多行文本(每行一张图的 base64) —— 程序化/后端用。
     图数 = 文本有几行,完全由数据决定,graph 结构恒定,无"空槽"、无占位图、无动态改线。
     一个静态工作流即可适配任意张数(0..N),后端只往这个文本框填几行就喂几张。

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

conditioning 是唯一必填项;一张参考图都没有时,节点原样返回(直通,等于纯文生图)。
"""

import node_helpers

# image socket 的槽位数量(画布手动用)。reference_list 文本方式不受这个上限约束。
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
        slots["reference_list"] = ("STRING", {
            "multiline": True,
            "default": "",
            "tooltip": (
                "程序化/后端用:每行一张参考图,格式「strength base64」(strength 可省=1.0),"
                "如「1.0 iVBOR...」或直接「iVBOR...」。图数=非空行数,无槽、无占位图。"
                "可与上面的 image_N socket 同时用(socket 在前)。支持 data:image/...;base64, 前缀。"
            ),
        })
        return {
            "required": {
                "conditioning": ("CONDITIONING",),
                "strength_mode": (["manual", "normalize"], {
                    "default": "manual",
                    "tooltip": (
                        "manual:每张图各用各自的 strength。"
                        "normalize:把所有有效图的 strength 按总和归一化(和=1),"
                        "保留相对比例(2/1/1→0.5/0.25/0.25),全相等时即自动均分。"
                        "两种模式下 strength=0 都表示跳过该图。"
                    ),
                }),
            },
            "optional": slots,
        }

    RETURN_TYPES = ("CONDITIONING",)
    RETURN_NAMES = ("conditioning",)
    FUNCTION = "inject_references"
    CATEGORY = "advanced/conditioning/edit_models"
    DESCRIPTION = (
        "把多张参考图挂进 conditioning(FLUX.2 dev/klein 等编辑模型)。"
        "两种喂图:image_N socket(画布)或 reference_list 多行 base64(程序化,图数=行数,无占位图)。"
        "每张图独立 strength,0=跳过;一张不接则直通(纯文生图)。内置 VAE 编码。"
    )

    @staticmethod
    def _to_reference_latent(vae, image):
        """像素图 → 参考用 latent。取 RGB 三通道,丢弃可能存在的 alpha。"""
        rgb = image[..., :3]
        return vae.encode(rgb)

    @staticmethod
    def _parse_list_line(line):
        """
        解析 reference_list 的一行 → (weight, base64) 或 None(空行)。
        行格式:「strength base64」或「base64」。strength 缺省为 1.0。
        base64 字符集不含空格,所以用首个空白切一刀:第一段能转 float 就是 strength。
        """
        s = line.strip()
        if not s:
            return None
        head, _, tail = s.partition(" ")
        if tail:
            try:
                return (float(head), tail.strip())
            except ValueError:
                pass  # 第一段不是数 → 整行都是 base64
        return (1.0, s)

    @staticmethod
    def _b64_to_image(b64):
        """base64(可带 data URI 前缀)→ ComfyUI IMAGE 张量 [1, H, W, 3], float 0..1。"""
        import base64 as _b64m
        import io as _io
        import numpy as _np
        import torch as _torch
        from PIL import Image as _Image

        s = b64.strip()
        if s.startswith("data:"):
            s = s.split(",", 1)[1] if "," in s else s
        raw = _b64m.b64decode(s)
        pil = _Image.open(_io.BytesIO(raw)).convert("RGB")
        arr = _np.asarray(pil, dtype=_np.float32) / 255.0
        return _torch.from_numpy(arr)[None, ]

    def inject_references(self, conditioning, strength_mode="manual",
                          vae=None, reference_list="", **slots):
        # 统一收集"有效"参考图为 (image_tensor, weight),先不编码。
        # 推迟编码:让 normalize 能先看到全部权重、算完总和再缩放,且只编码一次。
        active = []  # [(image_tensor, weight), ...]

        # 来源 A:image_N socket(画布手动),按槽位序 1..N。
        for n in range(1, NUM_SLOTS + 1):
            image = slots.get(f"image_{n}")
            weight = slots.get(f"strength_{n}", 1.0)
            if image is None or weight <= 0.0:
                continue  # 没接图 / strength=0 → 跳过
            active.append((image, weight))

        # 来源 B:reference_list 多行 base64(程序化),图数 = 非空行数。
        for lineno, line in enumerate(reference_list.splitlines(), 1):
            parsed = self._parse_list_line(line)
            if parsed is None:
                continue  # 空行
            weight, b64 = parsed
            if weight <= 0.0:
                continue  # strength=0 → 跳过该行
            try:
                image = self._b64_to_image(b64)
            except Exception as e:
                raise ValueError(
                    f"reference_list 第 {lineno} 行 base64 解码失败:{e}"
                )
            active.append((image, weight))

        # 没有任何有效参考图 → 节点退化为直通,原样把 conditioning 传出去。
        if not active:
            return (conditioning,)

        if vae is None:
            raise ValueError("有参考图但 vae 输入是空的。请把 VAELoader 连到本节点的 vae。")

        # normalize:按总和把各权重归一化到和=1,保留相对比例;全相等时即均分 1/N。
        # 总和必为正(只有 weight>0 的图才进 active),不会除零。
        if strength_mode == "normalize":
            total = sum(weight for _, weight in active)
            active = [(image, weight / total) for image, weight in active]

        # 逐张编码并按权重缩放,append 进 reference_latents,
        # 累积成 [latent_1, latent_2, ...],与原生 ReferenceLatent 的串接语义一致。
        result = conditioning
        for image, weight in active:
            latent = self._to_reference_latent(vae, image)
            result = node_helpers.conditioning_set_values(
                result, {"reference_latents": [latent * weight]}, append=True,
            )
        return (result,)


NODE_CLASS_MAPPINGS = {
    "MultiReferenceLatent": MultiReferenceLatent,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "MultiReferenceLatent": "Multi Reference Latent (≤6, per-image strength)",
}
