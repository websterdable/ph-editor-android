package org.local.photoai;

import ai.onnxruntime.NodeInfo;
import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OnnxValue;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import ai.onnxruntime.TensorInfo;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

public class OnnxHelper {

    private static final OrtEnvironment ENV = OrtEnvironment.getEnvironment();
    private static final Map<Integer, OrtSession> SESSIONS = new HashMap<>();
    private static final Map<Integer, String> INPUT_NAMES = new HashMap<>();
    private static int nextId = 1;

    // Строка ошибки последнего вызова (null = ok). Читается через getLastError().
    private static String lastError = null;

    public static String getLastError() {
        return lastError;
    }

    public static synchronized int loadModel(String path) {
        try {
            OrtSession.SessionOptions opts = new OrtSession.SessionOptions();
            opts.setIntraOpNumThreads(2);
            opts.setInterOpNumThreads(1);

            OrtSession session = ENV.createSession(path, opts);
            int id = nextId++;

            Iterator<Map.Entry<String, NodeInfo>> it =
                    session.getInputInfo().entrySet().iterator();
            String inName = "input";
            if (it.hasNext()) {
                Map.Entry<String, NodeInfo> e = it.next();
                inName = e.getKey();
                long[] ishape = shapeOf(e.getValue());
                System.out.println("[OnnxHelper] input name=" + inName +
                        " shape=" + shapeToString(ishape));
            }
            INPUT_NAMES.put(id, inName);
            SESSIONS.put(id, session);

            Iterator<Map.Entry<String, NodeInfo>> oit =
                    session.getOutputInfo().entrySet().iterator();
            while (oit.hasNext()) {
                Map.Entry<String, NodeInfo> e = oit.next();
                long[] oshape = shapeOf(e.getValue());
                System.out.println("[OnnxHelper] output name=" + e.getKey() +
                        " shape=" + shapeToString(oshape));
            }
            return id;
        } catch (Exception e) {
            System.out.println("[OnnxHelper] loadModel error: " + e);
            e.printStackTrace();
            return -1;
        }
    }

    /** Безопасно достать shape из NodeInfo (ValueInfo -> TensorInfo). */
    private static long[] shapeOf(NodeInfo nodeInfo) {
        try {
            Object info = nodeInfo.getInfo();
            if (info instanceof TensorInfo) {
                return ((TensorInfo) info).getShape();
            }
        } catch (Exception e) {
            // ignore
        }
        return new long[0];
    }

    private static String shapeToString(long[] s) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < s.length; i++) {
            sb.append(s[i]);
            if (i < s.length - 1) sb.append(",");
        }
        return sb.append("]").toString();
    }

    private static byte[] hwcU8ToChwF32(byte[] hwc, int w, int h, float scale) {
        int n = w * h;
        float[] chw = new float[n * 3];
        for (int y = 0; y < h; y++) {
            int rowBase = y * w;
            for (int x = 0; x < w; x++) {
                int src = (rowBase + x) * 3;
                int dst = rowBase + x;
                chw[dst]         = (hwc[src]     & 0xFF) * scale;
                chw[n + dst]     = (hwc[src + 1] & 0xFF) * scale;
                chw[2 * n + dst] = (hwc[src + 2] & 0xFF) * scale;
            }
        }
        ByteBuffer bb = ByteBuffer.allocate(chw.length * 4).order(ByteOrder.LITTLE_ENDIAN);
        bb.asFloatBuffer().put(chw);
        return bb.array();
    }

    /**
     * Инференс. Возвращает byte[] вида:
     *   [int32 rank][int32 d0][int32 d1][int32 d2][int32 d3][float32 data...]
     * shape занимает ровно 16 байт, дальше — сырые float32 значения.
     * При ошибке возвращает null, а текст ошибки доступен через getLastError().
     */
    public static synchronized byte[] runModelU8(
            int id, byte[] hwc, int w, int h, float scale) {

        lastError = null;
        try {
            OrtSession session = SESSIONS.get(id);
            if (session == null) {
                lastError = "session not found: " + id;
                return null;
            }
            if (hwc == null || hwc.length != w * h * 3) {
                lastError = "invalid input size: " +
                        (hwc == null ? 0 : hwc.length) +
                        " expected " + (w * h * 3);
                return null;
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
                lastError = "empty output";
                return null;
            }
            Map.Entry<String, OnnxValue> firstOut = it.next();
            OnnxValue value = firstOut.getValue();
            if (!(value instanceof OnnxTensor)) {
                lastError = "output is not a tensor";
                return null;
            }
            OnnxTensor outTensor = (OnnxTensor) value;
            long[] outShape = outTensor.getInfo().getShape();
            System.out.println("[OnnxHelper] out shape=" + shapeToString(outShape));

            ByteBuffer bb = outTensor.getByteBuffer();
            if (bb == null) {
                lastError = "getByteBuffer returned null";
                return null;
            }
            bb.order(ByteOrder.LITTLE_ENDIAN);
            int total = bb.remaining() / 4;
            byte[] outData = new byte[total * 4];
            bb.get(outData, 0, total * 4);

            // Печатаем первые значения для отладки
            FloatBuffer check = ByteBuffer.wrap(outData)
                    .order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();
            StringBuilder vals = new StringBuilder();
            for (int i = 0; i < Math.min(5, check.limit()); i++) {
                vals.append(check.get(i)).append(" ");
            }
            System.out.println("[OnnxHelper] first values: " + vals);

            // Упаковываем результат: 16 байт shape + data
            ByteBuffer result = ByteBuffer.allocate(16 + outData.length)
                    .order(ByteOrder.LITTLE_ENDIAN);
            result.putInt(outShape.length);
            for (int i = 0; i < 4; i++) {
                if (i < outShape.length) result.putInt((int) outShape[i]);
                else result.putInt(0);
            }
            result.put(outData);
            return result.array();
        } catch (Exception e) {
            System.out.println("[OnnxHelper] run error: " + e);
            e.printStackTrace();
            lastError = e.getClass().getSimpleName() + ": " + e.getMessage();
            return null;
        }
    }

    /** CHW float32 (из shape [1,3,H,W]) -> HWC uint8. */
    public static byte[] chwF32ToHwcU8(byte[] data, int[] shape) {
        if (shape == null || shape.length != 4 || shape[1] != 3) return null;
        int h = shape[2], w = shape[3];
        int n = h * w;
        FloatBuffer fb = ByteBuffer.wrap(data)
                .order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();
        byte[] out = new byte[n * 3];
        for (int i = 0; i < n; i++) {
            out[i * 3]     = (byte) clamp255((int) (fb.get(i) * 255.0f));
            out[i * 3 + 1] = (byte) clamp255((int) (fb.get(n + i) * 255.0f));
            out[i * 3 + 2] = (byte) clamp255((int) (fb.get(2 * n + i) * 255.0f));
        }
        return out;
    }

    /** CHW float32 (из shape [1,1,H,W]) -> HWC uint8 (серое). */
    public static byte[] chw1ToHwcU8(byte[] data, int[] shape) {
        if (shape == null || shape.length != 4 || shape[1] != 1) return null;
        int h = shape[2], w = shape[3];
        int n = h * w;
        FloatBuffer fb = ByteBuffer.wrap(data)
                .order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();
        byte[] out = new byte[n * 3];
        for (int i = 0; i < n; i++) {
            int v = clamp255((int) (fb.get(i) * 255.0f));
            out[i * 3]     = (byte) v;
            out[i * 3 + 1] = (byte) v;
            out[i * 3 + 2] = (byte) v;
        }
        return out;
    }

    private static int clamp255(int v) {
        if (v < 0) return 0;
        if (v > 255) return 255;
        return v;
    }
}
