package ru.pcremote.app;

import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.util.Locale;
import javax.net.ssl.HttpsURLConnection;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManager;
import javax.net.ssl.X509TrustManager;

/** TLS uses an explicit, out-of-band SHA-256 leaf certificate pin, never trust-all. */
final class ApiClient {
    interface Progress { void update(long done, long total); }
    private final String base;
    private final String token;
    private final javax.net.ssl.SSLSocketFactory sockets;
    private volatile HttpsURLConnection active;
    private volatile boolean cancelled;

    @android.annotation.SuppressLint("CustomX509TrustManager") // Exact pinned leaf; no CA fallback.
    ApiClient(String base, String token, String fingerprint) throws Exception {
        URI uri = new URI(base.trim());
        if (!"https".equalsIgnoreCase(uri.getScheme()) || uri.getHost() == null
                || uri.getRawUserInfo() != null || uri.getRawQuery() != null
                || uri.getRawFragment() != null
                || (uri.getPath() != null && !uri.getPath().isEmpty() && !"/".equals(uri.getPath()))) {
            throw new IOException("Введите адрес вида https://192.168.1.10:8443");
        }
        this.base = base.trim().replaceAll("/+$", "");
        this.token = token.trim();
        if (!this.token.matches("[A-Za-z0-9_-]{32,128}"))
            throw new IOException("Скопируйте ключ доступа из окна сервера на ПК.");
        String pin = fingerprint.replaceAll("[:\\s]", "").toUpperCase(Locale.ROOT);
        if (!pin.matches("[0-9A-F]{64}"))
            throw new IOException("Отпечаток SHA-256 должен содержать 64 шестнадцатеричных символа.");
        X509TrustManager trust = new X509TrustManager() {
            public X509Certificate[] getAcceptedIssuers() { return new X509Certificate[0]; }
            public void checkClientTrusted(X509Certificate[] chain, String authType)
                    throws CertificateException { throw new CertificateException("Client TLS unsupported"); }
            public void checkServerTrusted(X509Certificate[] chain, String authType)
                    throws CertificateException {
                try {
                    if (chain == null || chain.length == 0) throw new CertificateException("Нет сертификата.");
                    chain[0].checkValidity();
                    byte[] digest = MessageDigest.getInstance("SHA-256").digest(chain[0].getEncoded());
                    StringBuilder actual = new StringBuilder();
                    for (byte b : digest) actual.append(String.format(Locale.ROOT, "%02X", b & 255));
                    if (!MessageDigest.isEqual(actual.toString().getBytes(StandardCharsets.US_ASCII),
                            pin.getBytes(StandardCharsets.US_ASCII))) {
                        throw new CertificateException("Отпечаток сертификата не совпадает.");
                    }
                } catch (CertificateException e) { throw e; }
                catch (Exception e) { throw new CertificateException(e); }
            }
        };
        SSLContext context = SSLContext.getInstance("TLS");
        context.init(null, new TrustManager[]{trust}, null);
        sockets = context.getSocketFactory();
    }

    private HttpsURLConnection open(String route, String method) throws Exception {
        if (cancelled) throw new IOException("Операция отменена.");
        HttpsURLConnection c = (HttpsURLConnection) new URI(base + route).toURL().openConnection();
        c.setSSLSocketFactory(sockets);
        // Identity is the exact pinned leaf certificate, rather than a DNS/CA identity.
        c.setHostnameVerifier((hostname, session) -> true);
        c.setInstanceFollowRedirects(false); // Never forward the bearer token to another host.
        c.setConnectTimeout(12000);
        c.setReadTimeout(30000);
        c.setRequestProperty("Authorization", "Bearer " + token);
        c.setRequestProperty("Accept", "application/json");
        c.setRequestMethod(method);
        active = c;
        if (cancelled) { c.disconnect(); throw new IOException("Операция отменена."); }
        return c;
    }

    static String encode(String value) {
        try {
            return URLEncoder.encode(value, "UTF-8");
        } catch (java.io.UnsupportedEncodingException impossible) {
            throw new AssertionError(impossible);
        }
    }

    private String text(InputStream input) throws IOException {
        if (input == null) return "";
        try (InputStream source = input; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int count;
            while ((count = source.read(buffer)) != -1) {
                if (out.size() + count > 8 * 1024 * 1024) throw new IOException("Слишком большой ответ.");
                out.write(buffer, 0, count);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }

    private void verify(HttpsURLConnection c) throws Exception {
        int code = c.getResponseCode();
        if (code < 200 || code >= 300) {
            String message = "Ошибка сервера: " + code;
            try { message = new JSONObject(text(c.getErrorStream())).optString("error", message); }
            catch (Exception ignored) {}
            throw new IOException(message);
        }
    }

    JSONObject json(String route, JSONObject body) throws Exception {
        HttpsURLConnection c = open(route, body == null ? "GET" : "POST");
        try {
            if (body != null) {
                byte[] data = body.toString().getBytes(StandardCharsets.UTF_8);
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                c.setFixedLengthStreamingMode(data.length);
                try (OutputStream out = c.getOutputStream()) { out.write(data); }
            }
            verify(c);
            return new JSONObject(text(c.getInputStream()));
        } finally { c.disconnect(); active = null; }
    }

    void download(String path, OutputStream target, Progress progress) throws Exception {
        HttpsURLConnection c = open("/api/download?path=" + encode(path), "GET");
        try {
            verify(c);
            try (InputStream input = c.getInputStream()) {
                copy(input, target, c.getContentLengthLong(), progress);
            }
        } finally { c.disconnect(); active = null; }
    }

    void upload(String path, String name, long size, InputStream source, Progress progress)
            throws Exception {
        HttpsURLConnection c = open("/api/upload?path=" + encode(path) + "&name=" + encode(name), "PUT");
        try {
            c.setDoOutput(true);
            c.setRequestProperty("Content-Type", "application/octet-stream");
            c.setFixedLengthStreamingMode(size);
            try (OutputStream output = c.getOutputStream()) { copy(source, output, size, progress); }
            verify(c);
        } finally { c.disconnect(); active = null; }
    }

    private void copy(InputStream source, OutputStream target, long total, Progress progress)
            throws IOException {
        byte[] buffer = new byte[128 * 1024];
        long done = 0;
        int count;
        long last = 0;
        while ((count = source.read(buffer)) != -1) {
            if (cancelled || Thread.currentThread().isInterrupted()) throw new IOException("Операция отменена.");
            target.write(buffer, 0, count);
            done += count;
            long now = System.currentTimeMillis();
            if (now - last > 150) { progress.update(done, total); last = now; }
        }
        if (total >= 0 && done != total) throw new IOException("Передача прервана. Размер файла не совпал.");
        target.flush();
        progress.update(done, total);
    }

    void cancel() {
        cancelled = true;
        HttpsURLConnection c = active;
        if (c != null) c.disconnect();
    }
}
