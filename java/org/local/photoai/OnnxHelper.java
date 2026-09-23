package org.local.photoai;

import java.util.ArrayList;
import java.util.List;

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

    // Текст последней ошибки (null = ok). Читается через getLastError().
    private static String lastError = null;

    public static String getLastError() {
        return lastError;
    }

    // ─── Загрузка модели ────────────────────────────────────────

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

    // ─── Конвертация входа HWC uint8 -> CHW float32 ────────────

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
        ByteBuffer bb = ByteBuffer.allocate(chw.length * 4)
                .order(ByteOrder.LITTLE_ENDIAN);
        bb.asFloatBuffer().put(chw);
        return bb.array();
    }

    // ─── Инференс ───────────────────────────────────────────────

    /**
     * Запуск модели. Возвращает byte[] вида:
     *   [int32 rank][int32 d0][int32 d1][int32 d2][int32 d3][float32 data...]
     * Первые 16 байт — shape. Дальше — сырые float32 (LE).
     * При ошибке возвращает null, текст ошибки — в getLastError().
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
            OnnxValue outValue = firstOut.getValue();
            if (!(outValue instanceof OnnxTensor)) {
                lastError = "output is not a tensor";
                return null;
            }
            OnnxTensor outTensor = (OnnxTensor) outValue;
            long[] outShape = outTensor.getInfo().getShape();
            System.out.println("[OnnxHelper] out shape=" + shapeToString(outShape));

            // Считаем общий размер из shape
            long totalFloats = 1;
            for (long s : outShape) totalFloats *= s;
            if (totalFloats <= 0 || totalFloats > 100_000_000L) {
                lastError = "unreasonable output size: " + totalFloats;
                return null;
            }

            // Читаем через getValue() — многомерный Java-массив float/Object
            Object rawValue = outTensor.getValue();
            float[] flat = new float[(int) totalFloats];
            int written = flattenFloats(rawValue, flat, 0);
            if (written != totalFloats) {
                lastError = "flatten size mismatch: " + written +
                        " expected " + totalFloats;
                return null;
            }

            // Отладочный вывод первых 5 значений
            StringBuilder vals = new StringBuilder();
            for (int i = 0; i < Math.min(5, flat.length); i++) {
                vals.append(flat[i]).append(" ");
            }
            System.out.println("[OnnxHelper] first values: " + vals);

            // Упаковка: 16 байт shape + данные
            ByteBuffer dataBuf = ByteBuffer.allocate(flat.length * 4)
                    .order(ByteOrder.LITTLE_ENDIAN);
            dataBuf.asFloatBuffer().put(flat);
            byte[] outData = dataBuf.array();

            ByteBuffer result = ByteBuffer.allocate(20 + outData.length)
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

    /** Рекурсивно уплощает float[]/Object[] в плоский float[]. */
    private static int flattenFloats(Object src, float[] dst, int offset) {
        if (src == null) return offset;
        if (src instanceof float[]) {
            float[] a = (float[]) src;
            System.arraycopy(a, 0, dst, offset, a.length);
            return offset + a.length;
        }
        if (src instanceof Object[]) {
            for (Object sub : (Object[]) src) {
                offset = flattenFloats(sub, dst, offset);
            }
            return offset;
        }
        return offset;
    }

    // ─── Конвертация выхода CHW float32 -> HWC uint8 ───────────

    /** [1,3,H,W] -> HWC uint8. */
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

    /** [1,1,H,W] -> HWC uint8 (серое). */
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
    // ─── YuNet: детекция лиц ────────────────────────────────────

    /**
     * Запускает YuNet (детекция лиц). Возвращает int[] вида:
     *   [count, x1, y1, w1, h1, score1*10000, x2, y2, w2, h2, score2*10000, ...]
     * Или null при ошибке.
     */
    public static synchronized int[] runYuNet(int id, byte[] hwc, int w, int h) {
        lastError = null;
        try {
            OrtSession session = SESSIONS.get(id);
            if (session == null) { lastError = "session not found"; return null; }
            if (hwc == null || hwc.length != w * h * 3) {
                lastError = "invalid input"; return null;
            }

            // YuNet: вход CHW float32, scale=1.0 (без нормализации)
            byte[] chwBytes = hwcU8ToChwF32(hwc, w, h, 1.0f);
            FloatBuffer fb = ByteBuffer.wrap(chwBytes)
                    .order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer();
            long[] inputShape = new long[]{1, 3, h, w};
            OnnxTensor input = OnnxTensor.createTensor(ENV, fb, inputShape);

            Map<String, OnnxTensor> inputs = new HashMap<>();
            inputs.put(INPUT_NAMES.get(id), input);
            OrtSession.Result results = session.run(inputs);

            // Собираем все выходы
            Map<String, float[]> out = new HashMap<>();
            Iterator<Map.Entry<String, OnnxValue>> it = results.iterator();
            while (it.hasNext()) {
                Map.Entry<String, OnnxValue> e = it.next();
                if (!(e.getValue() instanceof OnnxTensor)) continue;
                OnnxTensor t = (OnnxTensor) e.getValue();
                long[] os = t.getInfo().getShape();
                long total = 1;
                for (long s : os) total *= s;
                Object raw = t.getValue();
                float[] flat = new float[(int) total];
                flattenFloats(raw, flat, 0);
                out.put(e.getKey(), flat);
                System.out.println("[OnnxHelper] yuNet out " + e.getKey() +
                        " shape=" + shapeToString(os));
            }

            // Ищем ключи (могут быть cls_8, cls_8_extra, output_cls_8, ...)
            int[][] stridesArr = {{8, 0}, {16, 1}, {32, 2}};
            List<float[]> faces = new ArrayList<>();

            for (int[] item : stridesArr) {
                int stride = item[0];
                String clsK  = findKey(out, "cls", stride);
                String objK  = findKey(out, "obj", stride);
                String bboxK = findKey(out, "bbox", stride);
                if (clsK == null || objK == null || bboxK == null) {
                    System.out.println("[OnnxHelper] yuNet: keys missing for stride " + stride);
                    continue;
                }
                float[] cls  = out.get(clsK);
                float[] obj  = out.get(objK);
                float[] bbox = out.get(bboxK);

                int fw = w / stride;
                int fh = h / stride;
                int n = fw * fh;
                System.out.println("[OnnxHelper] yuNet stride=" + stride +
                        " fw=" + fw + " fh=" + fh + " n=" + n +
                        " cls.len=" + cls.length);

                for (int idx = 0; idx < n && idx < cls.length; idx++) {
                    float score = (float) Math.sqrt(
                            Math.max(0f, cls[idx]) * Math.max(0f, obj[idx]));
                    if (score < 0.6f) continue;
                    int i = idx / fw;
                    int j = idx % fw;
                    float cx = (j + 0.5f) * stride + bbox[idx * 4] * stride;
                    float cy = (i + 0.5f) * stride + bbox[idx * 4 + 1] * stride;
                    float bw = (float) Math.exp(bbox[idx * 4 + 2]) * stride;
                    float bh = (float) Math.exp(bbox[idx * 4 + 3]) * stride;
                    faces.add(new float[]{
                        cx - bw / 2, cy - bh / 2, bw, bh, score
                    });
                }
            }

            System.out.println("[OnnxHelper] yuNet raw faces: " + faces.size());
            faces = nms(faces, 0.3f);
            System.out.println("[OnnxHelper] yuNet after NMS: " + faces.size());

            int[] result = new int[1 + faces.size() * 5];
            result[0] = faces.size();
            for (int i = 0; i < faces.size(); i++) {
                float[] f = faces.get(i);
                result[1 + i * 5]     = (int) f[0];
                result[1 + i * 5 + 1] = (int) f[1];
                result[1 + i * 5 + 2] = (int) f[2];
                result[1 + i * 5 + 3] = (int) f[3];
                result[1 + i * 5 + 4] = (int) (f[4] * 10000);
            }
            return result;
        } catch (Exception e) {
            System.out.println("[OnnxHelper] yuNet error: " + e);
            e.printStackTrace();
            lastError = e.toString();
            return null;
        }
    }

    private static String findKey(Map<String, float[]> out, String prefix, int stride) {
        String target = prefix + "_" + stride;
        for (String key : out.keySet()) {
            if (key.equals(target) || key.endsWith(target) || key.contains(target)) {
                return key;
            }
        }
        return null;
    }

    private static List<float[]> nms(List<float[]> faces, float iouThresh) {
        List<float[]> sorted = new ArrayList<>(faces);
        sorted.sort((a, b) -> Float.compare(b[4], a[4]));
        List<float[]> keep = new ArrayList<>();
        while (!sorted.isEmpty()) {
            float[] best = sorted.remove(0);
            keep.add(best);
            List<float[]> remaining = new ArrayList<>();
            for (float[] f : sorted) {
                if (iou(best, f) < iouThresh) remaining.add(f);
            }
            sorted = remaining;
        }
        return keep;
    }

    private static float iou(float[] a, float[] b) {
        float ax1 = a[0], ay1 = a[1], ax2 = a[0] + a[2], ay2 = a[1] + a[3];
        float bx1 = b[0], by1 = b[1], bx2 = b[0] + b[2], by2 = b[1] + b[3];
        float ix1 = Math.max(ax1, bx1);
        float iy1 = Math.max(ay1, by1);
        float ix2 = Math.min(ax2, bx2);
        float iy2 = Math.min(ay2, by2);
        float iw = Math.max(0, ix2 - ix1);
        float ih = Math.max(0, iy2 - iy1);
        float inter = iw * ih;
        float union = a[2] * a[3] + b[2] * b[3] - inter;
        return union > 0 ? inter / union : 0;
    }
}
