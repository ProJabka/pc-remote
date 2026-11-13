# Публикация проекта в GitHub / GitLab

Сейчас в папке уже есть исходный код, презентация и APK:

```text
android/
server/
docs/
Презентация_PC_Remote.pptx
release/PC-Remote.apk
README.md
```

После создания пустого репозитория `https://github.com/ProJabka/pc-remote`
без README выполните из папки `pc-remote`:

```powershell
git init
git branch -M main
git add .
git commit -m "PC Remote: Android app, HTTPS server, APK and presentation"
git remote add origin https://github.com/ProJabka/pc-remote.git
git push -u origin main
```

Затем:

1. Повторно запустите генерацию презентации:

```powershell
.\tools\python\python.exe .\docs\create_presentation.py
```

2. Загрузите обновлённую презентацию:

```powershell
git add Презентация_PC_Remote.pptx docs/create_presentation.py
git commit -m "Add repository link to presentation"
git push
```

В репозиторий **не нужно** добавлять папку `tools/`, временные логи,
эмулятор и файлы Gradle-сборки — они исключены `.gitignore`.
