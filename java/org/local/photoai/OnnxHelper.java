package org.local.photoai;

import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OnnxValue;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/** Тонкая обёртка над ONNX Runtime Java API. */
public class OnnxHelper {

    private static final OrtEnvironment ENV = OrtEnvironment.getEnvironment();
    private static final Map<Integer, OrtSession> SESSIONS = new HashMap<>();
    private static final Map<Integer, String> INPUT_NAMES = new HashMap<>();
    private static int nextId = 1;

    /** Загрузить модель. Возвращает handle (>0) или -1 при ошибке. */
    public static synchronized int loadModel(String path) {
        try {
            OrtSession.SessionOptions opts = new OrtSession.SessionOptions();
            opts.setIntraOpNumThreads(2);
            opts.setInterOpNumThreads(1);

            OrtSession session = ENV.createSession(path, opts);
            int id = nextId++;
            SESSIONS.put(id, session);

            // Первое имя входа
            Iterator<Map.Entry<String, ai.onnxruntime.NodeInfo>> it =
                    session.getInputInfo().entrySet().iterator();
            if (it.hasNext()) {
                INPUT_NAMES.put(id, it.next().getKey());
            }
            return id;
        } catch (Exception e) {
            e.printStackTrace();
            return -1;
        }
    }

    /** HWC uint8 -> CHW float32. Возвращает flat bytes (little-endian float32). */
    private static byte[] hwcU8ToChwF32(byte[] hwc, int w, int h, float scale) {
        int n = w * h;
        float[] chw = new float[n * 3];
        for (int y = 0; y < h; y++) {
            int rowBase = y * w;
            for (int x = 0; x < w; x++) {
                int src = (rowBase + x) * 3;
                int dst = rowBase + x;
                chw[dst]           = (hwc[src]     & 0xFF) * scale;
                chw[n + dst]       = (hwc[src + 1] & 0xFF) * scale;
                chw[2 * n + dst]   = (hwc[src + 2] & 0xFF) * scale;
            }
        }
        ByteBuffer bb = ByteBuffer.allocate(chw.length * 4).order(ByteOrder.LITTLE_ENDIAN);
        bb.asFloatBuffer().put(chw);
        return bb.array();
    }

    /**
     * Запустить инференс. Вход — HWC uint8, выход — CHW float32 (байты).
     * scale: 1/255.0 для моделей, ожидающих [0,1], или 1.0 для [0,255].
     */
    public static synchronized OnnxResult runModelU8(
            int id, byte[] hwc, int w, int h, float scale) {

        OnnxResult res = new OnnxResult();
        try {
            OrtSession session = SESSIONS.get(id);
            if (session == null) {
                res.error = "session not found: " + id;
                return res;
            }
            if (hwc == null || hwc.length != w * h * 3) {
                res.error = "invalid input size: " + (hwc == null ? 0 : hwc.length)
                        + " expected " + (w * h * 3);
                return res;
            }

            byte[] chwBytes = hwcU8ToChwF32(hwc, w, h, scale);
            FloatBuffer fb = ByteBuffer.wrap(chwBytes)
                    .order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();

            long[] shape = new long[]{1, 3, h, w};
            OnnxTensor input = OnnxTensor.createTensor(ENV, fb, shape);

            Map<String, OnnxTensor> inputs = new HashMap<>();
            inputs.put(INPUT_NAMES.get(id), input);

            OrtSession.Result results = session.run(inputs);

            Iterator<Map.Entry<String, OnnxValue>> it = results.iterator();
            if (!it.hasNext()) {
                res.error = "empty output";
                return res;
            }
            OnnxValue value = it.next().getValue();
            if (!(value instanceof OnnxTensor)) {
                res.error = "output is not a tensor";
                return res;
            }
            OnnxTensor outTensor = (OnnxTensor) value;
            long[] outShape = outTensor.getInfo().getShape();

            FloatBuffer outBuf = outTensor.getFloatBuffer();
            int outSize = outBuf.remaining();
            byte[] outBytes = new byte[outSize * 4];
            ByteBuffer obb = ByteBuffer.wrap(outBytes).order(ByteOrder.LITTLE_ENDIAN);
            obb.asFloatBuffer().put(outBuf);

            res.data = outBytes;
            int[] shapeInt = new int[outShape.length];
            for (int i = 0; i < outShape.length; i++) shapeInt[i] = (int) outShape[i];
            res.shape = shapeInt;
            return res;
        } catch (Exception e) {
            e.printStackTrace();
            res.error = e.getClass().getSimpleName() + ": " + e.getMessage();
            return res;
        }
    }

    /** CHW float32 bytes -> HWC uint8. Ожидает shape=[1,3,H,W]. */
    public static byte[] chwF32ToHwcU8(byte[] data, int[] shape) {
        if (shape == null || shape.length != 4 || shape[1] != 3) {
            return null;
        }
        int h = shape[2], w = shape[3];
        int n = h * w;
        FloatBuffer fb = ByteBuffer.wrap(data)
                .order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();

        byte[] out = new byte[n * 3];
        for (int i = 0; i < n; i++) {
            float r = fb.get(i);
            float g = fb.get(n + i);
            float b = fb.get(2 * n + i);
            out[i * 3]     = (byte) clamp255((int) (r * 255.0f));
            out[i * 3 + 1] = (byte) clamp255((int) (g * 255.0f));
            out[i * 3 + 2] = (byte) clamp255((int) (b * 255.0f));
        }
        return out;
    }

    private static int clamp255(int v) {
        if (v < 0) return 0;
        if (v > 255) return 255;
        return v;
    }
}
