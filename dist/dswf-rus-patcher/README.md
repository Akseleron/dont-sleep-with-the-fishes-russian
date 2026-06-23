# DSWF Russian Patcher / Русификатор DSWF

## Русская версия

### Описание

**DSWF Russian Patcher** — это установщик русификации для игры **Dont Sleep With The Fishes**.

Патчер сам устанавливает необходимые файлы. Вам нужно только выбрать папку с игрой и нажать кнопку установки.

Поддерживается:

* Windows;
* Linux через Wine.

---

### Что переводится

В текущей версии русификатор включает:

* русский текст;
* русские игровые текстуры;
* русификацию меню и интерфейса;
* автоматическое создание резервных копий перед установкой;
* удаление русификации с восстановлением оригинальных файлов.

---

### Установка

1. Распакуйте игру.
2. Запустите патчер.
3. Нажмите **Выбрать папку игры**.
4. Укажите папку, где находится файл:

```text
DontSleepWithTheFishes.exe
```

5. Оставьте включёнными нужные галочки.
6. Нажмите **Установить**.

Патчер проверит выбранную папку и установит русификацию.

---

### Если русификация уже установлена

Если русификация уже стоит, патчер сообщит об этом и предложит варианты:

* переустановить русификацию;
* удалить русификацию и восстановить оригинальные файлы;
* отменить действие.

---

### Удаление русификации

Чтобы удалить русификацию:

1. Запустите патчер.
2. Выберите папку игры.
3. Нажмите **Удалить русификацию**.
4. Подтвердите восстановление файлов.

Патчер вернёт изменённые файлы из резервной копии.

---

### Запуск на Windows

После установки запускайте игру обычным способом:

```text
DontSleepWithTheFishes.exe
```

---

### Запуск на Linux / Wine

На Linux после установки патчер создаёт файл:

```text
run_dswf_rus.sh
```

Для запуска русифицированной версии используйте его:

```bash
./run_dswf_rus.sh
```

Не рекомендуется запускать игру напрямую через `wine DontSleepWithTheFishes.exe`, потому что в таком случае перевод может не загрузиться.

---

### Важное примечание

В текущей версии шрифт может выглядеть неидеально в некоторых местах интерфейса. Это не мешает работе русификации, но визуальная полировка шрифта ещё не завершена.

---

### Поддерживаемая версия игры

Русификатор рассчитан на:

```text
Dont Sleep With The Fishes v1.1.2
```

На других версиях игры патчер может работать некорректно.

---

### Что делать, если что-то пошло не так

1. Запустите патчер снова.
2. Выберите папку игры.
3. Нажмите **Удалить русификацию**.
4. После восстановления попробуйте установить русификацию заново.

Если игра не запускается или перевод не появился, убедитесь, что выбрана именно папка с `DontSleepWithTheFishes.exe`.

---

## English version

### Description

**DSWF Russian Patcher** is an installer for the Russian localization of **Dont Sleep With The Fishes**.

The patcher installs all required files automatically. You only need to select the game folder and click install.

Supported platforms:

* Windows;
* Linux through Wine.

---

### Included localization

The current version includes:

* Russian text;
* Russian game textures;
* localized menu and interface elements;
* automatic backups before installation;
* uninstall with original file restoration.

---

### Installation

1. Extract the game.
2. Run the patcher.
3. Click **Select game folder**.
4. Select the folder containing:

```text
DontSleepWithTheFishes.exe
```

5. Keep the needed checkboxes enabled.
6. Click **Install**.

The patcher will check the selected folder and install the localization.

---

### If the localization is already installed

If the localization is already installed, the patcher will detect it and offer:

* reinstall localization;
* uninstall localization and restore original files;
* cancel.

---

### Uninstalling

To remove the localization:

1. Run the patcher.
2. Select the game folder.
3. Click **Uninstall localization**.
4. Confirm file restoration.

The patcher will restore changed files from backup.

---

### Running on Windows

After installation, launch the game normally:

```text
DontSleepWithTheFishes.exe
```

---

### Running on Linux / Wine

On Linux, the patcher creates this file after installation:

```text
run_dswf_rus.sh
```

Use it to launch the localized game:

```bash
./run_dswf_rus.sh
```

Launching the game directly through `wine DontSleepWithTheFishes.exe` is not recommended, because the translation may fail to load that way.

---

### Important note

In the current version, the font may look imperfect in some interface elements. This does not prevent the localization from working, but font polish is not finished yet.

---

### Supported game version

The patcher targets:

```text
Dont Sleep With The Fishes v1.1.2
```

Other game versions may not work correctly.

---

### If something goes wrong

1. Run the patcher again.
2. Select the game folder.
3. Click **Uninstall localization**.
4. After restoration, try installing the localization again.

If the game does not launch or the translation does not appear, make sure you selected the folder containing `DontSleepWithTheFishes.exe`.
