import { app } from "../../scripts/app.js";

// 给 Multi Reference Latent 节点一个固定配色,方便在画布上认出来。
app.registerExtension({
    name: "comfyui.multi_referencelatent",
    nodeCreated(node) {
        if (node.comfyClass === "MultiReferenceLatent") {
            node.color = "#2a3a4a";
            node.bgcolor = "#1f2a35";
        }
    },
});
