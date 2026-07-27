const cloudbase = require("@cloudbase/node-sdk");

const app = cloudbase.init({
  env: process.env.TCB_ENV,
});

exports.main = async (event) => {
  try {
    const ai = app.ai();
    const imgModel = ai.createImageModel("hunyuan-image");

    // Try v3 model first (newer), fall back to base model
    const model = event.model || "hunyuan-image-v3.0-v1.0.4";

    const result = await imgModel.generateImage({
      model: model,
      prompt: event.prompt || "test cat",
      size: event.size || "1024x1024",
      n: event.n || 1,
    });

    return {
      success: true,
      image_url: result.data?.[0]?.url || "",
      revised_prompt: result.data?.[0]?.revised_prompt || "",
      model_used: model,
    };
  } catch (e) {
    // Try fallback model
    try {
      const ai2 = app.ai();
      const imgModel2 = ai2.createImageModel("hunyuan-image");
      const result2 = await imgModel2.generateImage({
        model: "hunyuan-image",
        prompt: event.prompt || "test cat",
        size: event.size || "1024x1024",
        n: 1,
      });
      return {
        success: true,
        image_url: result2.data?.[0]?.url || "",
        revised_prompt: result2.data?.[0]?.revised_prompt || "",
        model_used: "hunyuan-image (fallback)",
      };
    } catch (e2) {
      return {
        success: false,
        error: e.message || String(e),
        fallback_error: e2.message || String(e2),
        code: e.code || "",
      };
    }
  }
};
