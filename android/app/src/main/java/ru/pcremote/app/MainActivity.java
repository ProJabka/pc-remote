package ru.pcremote.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.StatFs;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;
import org.json.JSONArray;
import org.json.JSONObject;
import java.io.*;
import java.text.DateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final int BG = 0xFFF4F6FB, INK = 0xFF19243B, MUTED = 0xFF748097;
    private static final int ACCENT = 0xFF4656D9, WHITE = Color.WHITE;
    private static final int PICK_UPLOAD = 101, PICK_DOWNLOAD = 102;
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final List<Entry> entries = new ArrayList<>(), filtered = new ArrayList<>();
    private CredentialStore credentials;
    private ApiClient api;
    private LinearLayout root;
    private EditText address, token, pin, search;
    private TextView connectionError, pathText, countText, emptyText, transferText;
    private ProgressBar progress;
    private Button connectButton, uploadButton, folderButton, upButton, refreshButton;
    private ListView files;
    private FileAdapter adapter;
    private boolean busy, connected, readOnly, destroyed;
    private long maxUpload;
    private String currentPath = "", computer = "", folder = "";
    private Entry pendingDownload;
    private String pendingUploadPath;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        credentials = new CredentialStore(this);
        showConnection();
    }

    private int dp(float value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private GradientDrawable shape(int color, int radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radius));
        return d;
    }
    private TextView text(String value, int size, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return view;
    }
    private LinearLayout column() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        return view;
    }
    private LinearLayout row() {
        LinearLayout view = new LinearLayout(this);
        view.setOrientation(LinearLayout.HORIZONTAL);
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }
    private void gap(LinearLayout parent, int height) {
        parent.addView(new View(this), new LinearLayout.LayoutParams(1, dp(height)));
    }
    private void add(LinearLayout parent, View child, int top) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(top);
        parent.addView(child, params);
    }
    private Button button(String title, boolean primary) {
        Button button = new Button(this);
        button.setText(title);
        button.setAllCaps(false);
        button.setTextSize(14);
        button.setTextColor(primary ? WHITE : ACCENT);
        button.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        button.setBackground(shape(primary ? ACCENT : 0xFFE9ECFF, 14));
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setPadding(dp(12), dp(8), dp(12), dp(8));
        return button;
    }
    private EditText input(String hint, int type) {
        EditText field = new EditText(this);
        field.setSingleLine(true);
        field.setTextSize(15);
        field.setTextColor(INK);
        field.setHintTextColor(MUTED);
        field.setInputType(type);
        field.setHint(hint);
        field.setPadding(dp(14), dp(12), dp(14), dp(12));
        field.setBackground(shape(BG, 12));
        field.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO);
        return field;
    }
    private void setRoot() {
        root = column();
        root.setBackgroundColor(BG);
        root.setPadding(dp(22), dp(16), dp(22), dp(16));
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(dp(22) + insets.getSystemWindowInsetLeft(),
                    dp(16) + insets.getSystemWindowInsetTop(),
                    dp(22) + insets.getSystemWindowInsetRight(),
                    dp(16) + insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(root);
        root.requestApplyInsets();
    }

    private void showConnection() {
        connected = false;
        setRoot();
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, -1));
        LinearLayout body = column();
        scroll.addView(body);
        gap(body, 20);
        TextView logo = text("PC", 28, WHITE, true);
        logo.setGravity(Gravity.CENTER);
        logo.setBackground(shape(ACCENT, 22));
        body.addView(logo, new LinearLayout.LayoutParams(dp(76), dp(76)));
        add(body, text("Ваш компьютер.\nВсегда под рукой.", 32, INK, true), 26);
        TextView intro = text("Документы, фото и рабочие файлы —\nпо защищённому соединению с вашим ПК.", 15, MUTED, false);
        intro.setLineSpacing(dp(4), 1);
        add(body, intro, 12);
        add(body, text("01  Запустите start-server.cmd на ПК\n02  Подключитесь к одной Wi-Fi сети или VPN\n03  Введите данные из окна сервера", 13, MUTED, false), 24);

        LinearLayout card = column();
        card.setPadding(dp(18), dp(20), dp(18), dp(20));
        card.setBackground(shape(WHITE, 22));
        add(body, card, 22);
        add(card, text("Подключение к ПК", 20, INK, true), 0);
        add(card, text("Адрес сервера", 12, MUTED, true), 20);
        address = input("https://192.168.1.10:8443",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        add(card, address, 8);
        add(card, text("Ключ доступа", 12, MUTED, true), 16);
        token = input("Ключ из окна сервера",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        add(card, token, 8);
        add(card, text("Отпечаток сертификата · SHA-256", 12, MUTED, true), 16);
        pin = input("64 символа из окна сервера",
                InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        add(card, pin, 8);
        connectionError = text("", 13, 0xFFC1404D, false);
        connectionError.setVisibility(View.GONE);
        add(card, connectionError, 12);
        connectButton = button("Подключиться  →", true);
        add(card, connectButton, 20);
        connectButton.setOnClickListener(v -> connect());
        Button forget = button("Забыть сохранённые данные", false);
        add(body, forget, 14);
        forget.setOnClickListener(v -> {
            if (busy) return;
            credentials.clear();
            address.setText(""); token.setText(""); pin.setText("");
            toast("Данные подключения удалены");
        });
        add(body, text("TLS-шифрование · Только выбранная папка\nКлюч хранится с защитой Android Keystore", 12, MUTED, false), 18);
        gap(body, 16);
        JSONObject saved = credentials.load();
        address.setText(saved.optString("address"));
        token.setText(saved.optString("token"));
        pin.setText(saved.optString("pin"));
    }

    private void connect() {
        if (busy) return;
        final String url = address.getText().toString().trim();
        final String secret = token.getText().toString().trim();
        final String fingerprint = pin.getText().toString().trim();
        connectionError.setVisibility(View.GONE);
        connectButton.setEnabled(false);
        connectButton.setText("Подключение…");
        busy = true;
        ((InputMethodManager) getSystemService(INPUT_METHOD_SERVICE))
                .hideSoftInputFromWindow(address.getWindowToken(), 0);
        worker.execute(() -> {
            try {
                ApiClient candidate = new ApiClient(url, secret, fingerprint);
                api = candidate;
                JSONObject info = candidate.json("/api/status", null);
                if (info.optInt("version") != 1) throw new IOException("Неподдерживаемая версия сервера.");
                JSONObject listing = candidate.json("/api/files?path=", null);
                credentials.save(url, secret, fingerprint);
                ui(() -> {
                    computer = info.optString("computer", "Компьютер");
                    folder = info.optString("folder", "Общая папка");
                    readOnly = info.optBoolean("readOnly", true);
                    maxUpload = info.optLong("maxUpload", 0);
                    currentPath = "";
                    busy = false;
                    connected = true;
                    showFiles();
                    applyListing(listing);
                });
            } catch (Exception e) {
                ui(() -> {
                    busy = false;
                    connectButton.setEnabled(true);
                    connectButton.setText("Подключиться  →");
                    connectionError.setText(friendly(e));
                    connectionError.setVisibility(View.VISIBLE);
                });
            }
        });
    }

    private void showFiles() {
        setRoot();
        LinearLayout header = row();
        LinearLayout names = column();
        names.addView(text("PC Remote", 26, INK, true));
        TextView subtitle = text("●  " + computer + "  ·  TLS", 12, 0xFF20866A, false);
        subtitle.setSingleLine(true);
        names.addView(subtitle);
        header.addView(names, new LinearLayout.LayoutParams(0, -2, 1));
        Button menu = button("•••", false);
        header.addView(menu, new LinearLayout.LayoutParams(dp(52), dp(48)));
        menu.setOnClickListener(v -> {
            if (busy) { toast("Дождитесь завершения передачи"); return; }
            PopupMenu popup = new PopupMenu(this, menu);
            popup.getMenu().add("О подключении").setOnMenuItemClickListener(item -> {
                new AlertDialog.Builder(this).setTitle("Защищённое подключение")
                        .setMessage(computer + "\nПапка: " + folder
                                + "\nРежим: " + (readOnly ? "только чтение" : "чтение и загрузка")
                                + "\n\nДоступ ограничен выбранной папкой. Удаление и перезапись файлов отключены."
                                + "\n\nДля доступа вне дома используйте личный VPN.")
                        .setPositiveButton("Понятно", null).show();
                return true;
            });
            popup.getMenu().add("Отключиться").setOnMenuItemClickListener(item -> {
                disconnect(); return true;
            });
            popup.show();
        });
        add(root, header, 0);
        LinearLayout shareCard = column();
        shareCard.setPadding(dp(18), dp(16), dp(18), dp(16));
        shareCard.setBackground(shape(ACCENT, 20));
        shareCard.addView(text("ОБЩАЯ ПАПКА", 10, 0xFFC7CEFF, true));
        add(shareCard, text(folder, 22, WHITE, true), 6);
        add(shareCard, text(readOnly ? "Только чтение · файлы остаются на ПК"
                : "Ваши файлы — без облака и посредников", 12, 0xFFE0E4FF, false), 5);
        add(root, shareCard, 20);
        search = input("Поиск в текущей папке", InputType.TYPE_CLASS_TEXT);
        search.setBackground(shape(WHITE, 14));
        add(root, search, 18);
        search.addTextChangedListener(new TextWatcher() {
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            public void onTextChanged(CharSequence s, int start, int before, int count) { filter(); }
            public void afterTextChanged(Editable s) {}
        });
        LinearLayout navigation = row();
        upButton = button("↑", false);
        navigation.addView(upButton, new LinearLayout.LayoutParams(dp(48), dp(44)));
        upButton.setOnClickListener(v -> goUp());
        pathText = text("", 12, MUTED, true);
        pathText.setSingleLine(true);
        pathText.setEllipsize(android.text.TextUtils.TruncateAt.START);
        pathText.setPadding(dp(12), 0, dp(8), 0);
        navigation.addView(pathText, new LinearLayout.LayoutParams(0, -2, 1));
        refreshButton = button("↻", false);
        refreshButton.setContentDescription("Обновить");
        navigation.addView(refreshButton, new LinearLayout.LayoutParams(dp(48), dp(44)));
        refreshButton.setOnClickListener(v -> load(currentPath));
        add(root, navigation, 16);
        countText = text("ФАЙЛЫ", 11, MUTED, true);
        add(root, countText, 16);
        FrameLayout frame = new FrameLayout(this);
        LinearLayout.LayoutParams listParams = new LinearLayout.LayoutParams(-1, 0, 1);
        listParams.topMargin = dp(10);
        root.addView(frame, listParams);
        files = new ListView(this);
        files.setDivider(null);
        files.setClipToPadding(false);
        files.setPadding(0, 0, 0, dp(8));
        adapter = new FileAdapter();
        files.setAdapter(adapter);
        frame.addView(files, new FrameLayout.LayoutParams(-1, -1));
        emptyText = text("В этой папке пока нет файлов", 15, MUTED, false);
        emptyText.setGravity(Gravity.CENTER);
        frame.addView(emptyText, new FrameLayout.LayoutParams(-1, -1));
        files.setEmptyView(emptyText);
        files.setOnItemClickListener((parent, view, position, id) -> {
            if (busy) return;
            Entry entry = filtered.get(position);
            if (entry.directory) load(entry.path);
            else showFile(entry);
        });
        LinearLayout transfer = column();
        transferText = text("Соединение защищено", 12, MUTED, false);
        transfer.addView(transferText);
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(1000);
        progress.setVisibility(View.GONE);
        add(transfer, progress, 6);
        add(root, transfer, 8);
        LinearLayout actions = row();
        folderButton = button("+ Папка", false);
        LinearLayout.LayoutParams left = new LinearLayout.LayoutParams(0, dp(50), 1);
        left.rightMargin = dp(10);
        actions.addView(folderButton, left);
        uploadButton = button("↑  Загрузить на ПК", true);
        actions.addView(uploadButton, new LinearLayout.LayoutParams(0, dp(50), 2));
        folderButton.setOnClickListener(v -> newFolder());
        uploadButton.setOnClickListener(v -> chooseUpload());
        add(root, actions, 14);
        updateControls();
    }

    private void updateControls() {
        if (!connected) return;
        upButton.setEnabled(!busy && !currentPath.isEmpty());
        refreshButton.setEnabled(!busy);
        folderButton.setEnabled(!busy && !readOnly);
        uploadButton.setEnabled(!busy && !readOnly);
        search.setEnabled(!busy);
        files.setAlpha(busy ? .55f : 1f);
        if (busy) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private interface Task { String run() throws Exception; }
    private void task(String title, Task work, Runnable success) {
        if (busy || !connected) return;
        busy = true;
        progress.setIndeterminate(true);
        progress.setVisibility(View.VISIBLE);
        transferText.setText(title);
        updateControls();
        worker.execute(() -> {
            try {
                String result = work.run();
                ui(() -> {
                    busy = false;
                    progress.setVisibility(View.GONE);
                    transferText.setText(result);
                    updateControls();
                    if (success != null) success.run();
                });
            } catch (Exception e) {
                ui(() -> {
                    busy = false;
                    progress.setVisibility(View.GONE);
                    transferText.setText("Операция не завершена");
                    updateControls();
                    new AlertDialog.Builder(this).setTitle("Не удалось выполнить")
                            .setMessage(friendly(e)).setPositiveButton("Понятно", null).show();
                });
            }
        });
    }

    private void load(String path) {
        final JSONObject[] value = new JSONObject[1];
        task("Открываем папку…", () -> {
            value[0] = api.json("/api/files?path=" + ApiClient.encode(path), null);
            return "Соединение защищено";
        }, () -> {
            currentPath = path;
            search.setText("");
            applyListing(value[0]);
            updateControls();
        });
    }

    private void applyListing(JSONObject listing) {
        entries.clear();
        JSONArray array = listing.optJSONArray("entries");
        if (array != null) for (int i = 0; i < array.length(); i++) {
            JSONObject item = array.optJSONObject(i);
            if (item != null) entries.add(new Entry(item));
        }
        pathText.setText(currentPath.isEmpty() ? "⌂  /" : "⌂  / " + currentPath.replace("/", " / "));
        filter();
    }
    private void filter() {
        if (adapter == null || search == null) return;
        String query = search.getText().toString().toLowerCase(Locale.ROOT).trim();
        filtered.clear();
        for (Entry e : entries) if (e.name.toLowerCase(Locale.ROOT).contains(query)) filtered.add(e);
        countText.setText(getString(R.string.file_count, filtered.size()));
        emptyText.setText(query.isEmpty() ? "В этой папке пока нет файлов\nЗагрузите первый файл с телефона"
                : "Ничего не найдено");
        adapter.notifyDataSetChanged();
    }
    private void goUp() {
        if (busy || currentPath.isEmpty()) return;
        int slash = currentPath.lastIndexOf('/');
        load(slash < 0 ? "" : currentPath.substring(0, slash));
    }

    private void newFolder() {
        if (busy || readOnly) return;
        EditText name = input("Название папки", InputType.TYPE_CLASS_TEXT);
        LinearLayout box = column();
        box.setPadding(dp(24), dp(10), dp(24), 0);
        box.addView(name);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("Новая папка")
                .setView(box).setNegativeButton("Отмена", null)
                .setPositiveButton("Создать", null).create();
        dialog.setOnShowListener(d -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(v -> {
            String value = name.getText().toString().trim();
            if (value.isEmpty()) { name.setError("Введите название"); return; }
            dialog.dismiss();
            String path = currentPath;
            task("Создаём папку…", () -> {
                api.json("/api/folders", new JSONObject().put("path", path).put("name", value));
                return "Папка создана";
            }, () -> load(path));
        }));
        dialog.show();
    }

    private void showFile(Entry entry) {
        new AlertDialog.Builder(this).setTitle(entry.name)
                .setMessage(size(entry.size) + "\nИзменён: "
                        + DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT)
                        .format(new Date(entry.modified))
                        + "\n\nСохранить копию на телефон? Оригинал останется на ПК.")
                .setNegativeButton("Отмена", null)
                .setPositiveButton("Скачать", (d, w) -> {
                    pendingDownload = entry;
                    Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    intent.setType("application/octet-stream");
                    intent.putExtra(Intent.EXTRA_TITLE, entry.name);
                    startActivityForResult(intent, PICK_DOWNLOAD);
                }).show();
    }
    private void chooseUpload() {
        if (busy || readOnly) return;
        pendingUploadPath = currentPath;
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        startActivityForResult(intent, PICK_UPLOAD);
    }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null || data.getData() == null || !connected || busy) return;
        Uri uri = data.getData();
        if (request == PICK_DOWNLOAD && pendingDownload != null) {
            Entry entry = pendingDownload;
            pendingDownload = null;
            task("Скачиваем " + entry.name + "…", () -> {
                boolean complete = false;
                try {
                    try (OutputStream out = getContentResolver().openOutputStream(uri, "w")) {
                        if (out == null) throw new IOException("Не удалось открыть место сохранения.");
                        api.download(entry.path, out, this::transferProgress);
                    }
                    complete = true;
                } finally {
                    if (!complete) {
                        try { DocumentsContract.deleteDocument(getContentResolver(), uri); }
                        catch (Exception ignored) {}
                    }
                }
                return "✓  Файл сохранён на телефон";
            }, () -> toast("Файл сохранён"));
        } else if (request == PICK_UPLOAD && pendingUploadPath != null) {
            String targetPath = pendingUploadPath;
            pendingUploadPath = null;
            task("Подготавливаем файл…", () -> {
                String name = "file-" + System.currentTimeMillis();
                try (Cursor cursor = getContentResolver().query(uri,
                        new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
                    if (cursor != null && cursor.moveToFirst() && !cursor.isNull(0)) name = cursor.getString(0);
                }
                File cache = File.createTempFile("upload-", ".tmp", getCacheDir());
                try {
                    long done = 0;
                    long available = new StatFs(getCacheDir().getAbsolutePath()).getAvailableBytes();
                    long limit = Math.min(maxUpload, Math.max(0, available - 32L * 1024 * 1024));
                    try (InputStream source = getContentResolver().openInputStream(uri);
                         OutputStream out = new FileOutputStream(cache)) {
                        if (source == null) throw new IOException("Не удалось открыть файл.");
                        byte[] buffer = new byte[128 * 1024];
                        int count;
                        while ((count = source.read(buffer)) != -1) {
                            if (Thread.currentThread().isInterrupted()) throw new IOException("Операция отменена.");
                            done += count;
                            if (done > limit) throw new IOException(
                                    "Файл превышает лимит сервера или свободное место на телефоне. Лимит: " + size(limit));
                            out.write(buffer, 0, count);
                        }
                    }
                    ui(() -> transferText.setText("Загружаем файл на ПК…"));
                    try (InputStream input = new FileInputStream(cache)) {
                        api.upload(targetPath, name, cache.length(), input, this::transferProgress);
                    }
                } finally {
                    cache.delete();
                }
                return "✓  Файл загружен на ПК";
            }, () -> { toast("Файл загружен на ПК"); load(targetPath); });
        }
    }

    private void transferProgress(long done, long total) {
        ui(() -> {
            progress.setIndeterminate(total <= 0);
            if (total > 0) progress.setProgress((int) Math.min(1000, done * 1000 / total));
            transferText.setText(total >= 0 ? getString(R.string.transfer_progress, size(done), size(total)) : size(done));
        });
    }
    private void disconnect() {
        if (busy) return;
        if (api != null) api.cancel();
        api = null;
        entries.clear();
        filtered.clear();
        showConnection();
    }
    private void ui(Runnable action) {
        runOnUiThread(() -> { if (!destroyed && !isFinishing()) action.run(); });
    }
    private void toast(String message) { Toast.makeText(this, message, Toast.LENGTH_SHORT).show(); }
    private String friendly(Exception error) {
        if (error instanceof javax.net.ssl.SSLException)
            return "Не удалось проверить TLS-сертификат. Сверьте отпечаток SHA-256 с окном сервера и дату на телефоне.";
        if (error instanceof java.net.SocketTimeoutException || error instanceof java.net.ConnectException)
            return "ПК не отвечает. Проверьте адрес, Wi-Fi/VPN, запущенный сервер и разрешение брандмауэра Windows.";
        String message = error.getMessage();
        return message == null || message.isEmpty() ? "Не удалось выполнить операцию. Проверьте подключение." : message;
    }
    static String size(long bytes) {
        if (bytes < 1024) return bytes + " Б";
        if (bytes < 1024 * 1024) return String.format(Locale.getDefault(), "%.1f КБ", bytes / 1024.0);
        if (bytes < 1024L * 1024 * 1024)
            return String.format(Locale.getDefault(), "%.1f МБ", bytes / (1024.0 * 1024));
        return String.format(Locale.getDefault(), "%.2f ГБ", bytes / (1024.0 * 1024 * 1024));
    }
    @Override public void onBackPressed() {
        if (busy) { toast("Дождитесь завершения операции"); return; }
        if (connected && !currentPath.isEmpty()) goUp();
        else if (connected) new AlertDialog.Builder(this).setTitle("Отключиться от ПК?")
                .setNegativeButton("Остаться", null).setPositiveButton("Отключиться", (d, w) -> disconnect()).show();
        else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        destroyed = true;
        if (api != null) api.cancel();
        worker.shutdownNow();
        super.onDestroy();
    }

    private static final class Entry {
        final String name, path;
        final boolean directory;
        final long size, modified;
        Entry(JSONObject json) {
            name = json.optString("name");
            path = json.optString("path");
            directory = json.optBoolean("directory");
            size = json.optLong("size");
            modified = json.optLong("modified");
        }
    }
    private final class FileAdapter extends BaseAdapter {
        public int getCount() { return filtered.size(); }
        public Entry getItem(int position) { return filtered.get(position); }
        public long getItemId(int position) { return position; }
        public View getView(int position, View reusable, ViewGroup parent) {
            Entry entry = getItem(position);
            LinearLayout outer = column();
            outer.setPadding(0, 0, 0, dp(8));
            LinearLayout line = row();
            line.setPadding(dp(12), dp(13), dp(12), dp(13));
            line.setBackground(shape(WHITE, 16));
            TextView icon = text(entry.directory ? "▰" : extension(entry.name), entry.directory ? 25 : 10,
                    entry.directory ? 0xFFC18B24 : ACCENT, true);
            icon.setGravity(Gravity.CENTER);
            icon.setBackground(shape(entry.directory ? 0xFFFFF3D9 : 0xFFEEF0FF, 12));
            line.addView(icon, new LinearLayout.LayoutParams(dp(46), dp(46)));
            LinearLayout labels = column();
            labels.setPadding(dp(12), 0, dp(8), 0);
            TextView title = text(entry.name, 15, INK, true);
            title.setSingleLine(true);
            title.setEllipsize(android.text.TextUtils.TruncateAt.MIDDLE);
            labels.addView(title);
            TextView detail = text(entry.directory ? "Папка" : size(entry.size) + "  ·  "
                    + DateFormat.getDateInstance(DateFormat.SHORT).format(new Date(entry.modified)), 11, MUTED, false);
            add(labels, detail, 5);
            line.addView(labels, new LinearLayout.LayoutParams(0, -2, 1));
            line.addView(text(entry.directory ? "›" : "↓", 22, MUTED, false));
            outer.addView(line);
            return outer;
        }
        private String extension(String name) {
            int dot = name.lastIndexOf('.');
            String ext = dot >= 0 ? name.substring(dot + 1).toUpperCase(Locale.ROOT) : "FILE";
            return ext.length() > 4 ? "FILE" : ext;
        }
    }
}
