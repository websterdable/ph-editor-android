package org.local.photoai;

/** Результат инференса: data (float32 bytes), shape, error. */
public class OnnxResult {
    public byte[] data;
    public int[] shape;
    public String error;

    public OnnxResult() {
        this.data = null;
        this.shape = null;
        this.error = null;
    }
}
