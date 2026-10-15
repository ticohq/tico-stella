#!/usr/bin/env python3
"""Settings definition and translations for the tico module of Stella.

Run after merging upstream. It builds tools/dump_core_options.c against the
option table it copies out of src/os/libretro/libretro.cxx, so tico/module/settings.json lists exactly
the options the libnx core reads (stella_* keys, values and defaults), laid
out in tabs, followed by the overlay's own display and controls options.
Labels are translation keys; the strings go into tico/lang/*.json, taken from
the LABELS and CHOICES tables below: Stella translates none of its options. Choice labels stay English in settings.json;
the overlay translates them through settings_stella_value_* keys.

    python3 tico/tools/tico_module.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TICO = ROOT / "tico"
SETTINGS = TICO / "module/settings.json"
LANG_DIR = TICO / "lang"
LANGUAGES = ("en", "de", "es", "fr", "ja", "pt", "ru", "zh")
# tico-nx's own strings label the options it already knew; optional
TICO_NX = Path(os.environ.get("TICO_NX_DIR", ROOT.parents[1] / "tico-nx"))

# Core option -> label key. Options are named after their key without stella_.
LABEL_KEYS: dict[str, str] = {}

# Core options the frontend has no use for: tico sends no mouse or lightgun,
# and its own Restart does what "reload" puts on the RetroPad's X.
EXCLUDED = {"stella_paddle_mouse_sensitivity", "stella_lightgun_crosshair", "stella_reload"}

# (tab, [(section, [option keys])]). Every core option the dump lists must be
# placed or excluded; the overlay's own tabs are added around these.
LAYOUT = [
    ("settings_stella_tab_system", [
        ("settings_stella_section_system", ["stella_console", "stella_detect_pal60",
                                            "stella_detect_ntsc50", "stella_messages"]),
    ]),
    ("settings_stella_tab_video", [
        ("settings_stella_section_display", ["stella_filter", "stella_ntsc_aspect",
                                             "stella_pal_aspect", "stella_crop_hoverscan",
                                             "stella_crop_voverscan", "stella_phosphor",
                                             "stella_phosphor_blend"]),
        ("settings_stella_section_palette", ["stella_palette", "stella_pal_contrast",
                                             "stella_pal_brightness", "stella_pal_hue",
                                             "stella_pal_saturation", "stella_pal_gamma"]),
    ]),
    ("settings_stella_tab_audio", [
        ("settings_stella_section_sound", ["stella_stereo", "stella_dpc_pitch"]),
    ]),
    ("settings_stella_tab_input", [
        ("settings_stella_section_paddles", ["stella_paddle_joypad_sensitivity",
                                             "stella_paddle_analog_sensitivity",
                                             "stella_paddle_analog_deadzone",
                                             "stella_paddle_analog_absolute"]),
    ]),
]

# Listed only while another option has a value, like the core's own menus.
DEPENDS_ON: dict[str, tuple[str, str]] = {}

# English names for the core's lower-case values.
EN_CHOICES = {
    "auto": "Auto", "ntsc": "NTSC", "pal": "PAL", "secam": "SECAM", "ntsc50": "NTSC-50",
    "pal60": "PAL-60", "secam60": "SECAM-60", "standard": "Standard", "z26": "z26",
    "user": "User", "custom": "Custom", "composite": "Composite", "s-video": "S-Video",
    "rgb": "RGB", "badly adjusted": "Badly adjusted", "par": "Pixel aspect (PAR)",
    "on": "On", "off": "Off",
}

# Switch buttons an Atari control (or the fast-forward hotkey) can sit on.
SWITCH_BUTTONS = [("A", "A"), ("B", "B"), ("X", "X"), ("Y", "Y"), ("L", "L"), ("R", "R"),
                  ("ZL", "ZL"), ("ZR", "ZR"), ("Plus", "Plus"), ("Minus", "Minus"),
                  ("StickL", "Left stick"), ("StickR", "Right stick"), ("Up", "Up"),
                  ("Down", "Down"), ("Left", "Left"), ("Right", "Right"), ("None", "Disabled")]

POSITIONS = [("hidden", "Hidden"), ("top_left", "Top left"), ("top_right", "Top right"),
             ("bottom_left", "Bottom left"), ("bottom_right", "Bottom right")]

# The overlay's own options: how the game is scaled, fast forward and the HUD.
# "Original" keeps the core's aspect, which its NTSC and PAL aspect options set.
OVERLAY_TAB = ("settings_stella_tab_display", [
    ("settings_stella_section_screen", [
        {"key": "display_mode", "label": "settings_stella_display_mode", "type": "enum",
         "default": "Display", "choices": [("Integer", "Integer"), ("Display", "Display")]},
        {"key": "display_size", "label": "settings_stella_display_size", "type": "enum",
         "default": "Original", "choices": [("Stretch", "Stretch"), ("4:3", "4:3"),
                                            ("16:9", "16:9"), ("Original", "Original"),
                                            ("1x", "1x"), ("2x", "2x"), ("Auto", "Auto")]},
    ]),
    ("settings_stella_section_fast_forward", [
        {"key": "fast_forward_speed", "label": "settings_stella_fast_forward_speed", "type": "enum",
         "default": "200", "choices": [("150", "150%"), ("200", "200%"), ("300", "300%"),
                                        ("400", "400%"), ("unlimited", "Unlimited")]},
        {"key": "fast_forward_mode", "label": "settings_stella_fast_forward_mode", "type": "enum",
         "default": "hold", "choices": [("hold", "Hold"), ("toggle", "Toggle")]},
        {"key": "fast_forward_hotkey", "label": "settings_stella_fast_forward_hotkey",
         "type": "enum", "default": "ZR", "choices": SWITCH_BUTTONS},
    ]),
    ("settings_stella_section_hud", [
        {"key": "fps_counter_position", "label": "settings_stella_fps_counter", "type": "enum",
         "default": "hidden", "choices": POSITIONS},
        {"key": "rendered_ir_position", "label": "settings_stella_rendered_resolution",
         "type": "enum", "default": "hidden", "choices": POSITIONS},
    ]),
])

# The overlay's button mapping: each Atari control and console switch on a
# Switch button (TicoMain.cpp's kButtonMappings). The difficulty switches
# take one button per position; ZR is fast forward, so the right one's B
# position sits on X.
CONTROLS_TAB = ("settings_stella_tab_controls", [
    ("settings_stella_section_button_mapping", [
        {"key": key, "label": "settings_stella_" + key, "type": "enum", "default": default,
         "choices": SWITCH_BUTTONS}
        for key, default in [
            ("map_up", "Up"), ("map_down", "Down"), ("map_left", "Left"), ("map_right", "Right"),
            ("map_fire", "A"), ("map_trigger", "B"), ("map_booster", "Y"),
        ]
    ] + [
        {"key": "analog_dpad", "label": "settings_stella_analog_dpad", "type": "bool",
         "default": "enabled"},
    ]),
    ("settings_stella_section_console_switches", [
        {"key": key, "label": "settings_stella_" + key, "type": "enum", "default": default,
         "choices": SWITCH_BUTTONS}
        for key, default in [
            ("map_select", "Minus"), ("map_reset", "Plus"),
            ("map_left_diff_a", "L"), ("map_left_diff_b", "ZL"),
            ("map_right_diff_a", "R"), ("map_right_diff_b", "X"),
            ("map_color", "StickL"), ("map_bw", "StickR"),
        ]
    ]),
])

# Labels the core does not define. key -> (en, de, es, fr, ja, pt, ru, zh)
LABELS = {
    "settings_stella_tab_system": ("System", "System", "Sistema", "Système", "システム", "Sistema",
                                   "Система", "系统"),
    "settings_stella_section_system": ("System", "System", "Sistema", "Système", "システム",
                                       "Sistema", "Система", "系统"),
    "settings_stella_tab_video": ("Video", "Video", "Vídeo", "Vidéo", "ビデオ", "Vídeo", "Видео",
                                  "视频"),
    "settings_stella_section_display": ("Display", "Anzeige", "Pantalla", "Affichage", "表示",
                                        "Exibição", "Отображение", "显示"),
    "settings_stella_section_palette": ("Palette", "Palette", "Paleta", "Palette", "パレット",
                                        "Paleta", "Палитра", "调色板"),
    "settings_stella_tab_audio": ("Audio", "Audio", "Audio", "Audio", "オーディオ", "Áudio", "Звук",
                                  "音频"),
    "settings_stella_section_sound": ("Sound", "Ton", "Sonido", "Son", "サウンド", "Som", "Звук",
                                      "声音"),
    "settings_stella_tab_input": ("Input", "Eingabe", "Entrada", "Entrée", "入力", "Entrada",
                                  "Ввод", "输入"),
    "settings_stella_section_paddles": ("Paddles", "Paddles", "Paddles", "Paddles", "パドル",
                                        "Paddles", "Паддлы", "旋钮控制器"),
    "settings_stella_console": ("Console display", "Konsolen-Bildformat", "Formato de la consola",
                                "Format de la console", "本体の映像方式", "Formato do console",
                                "Видеостандарт консоли", "主机制式"),
    "settings_stella_detect_pal60": ("Detect PAL-60", "PAL-60 erkennen", "Detectar PAL-60",
                                     "Détecter le PAL-60", "PAL-60を自動検出", "Detectar PAL-60",
                                     "Определять PAL-60", "检测 PAL-60"),
    "settings_stella_detect_ntsc50": ("Detect NTSC-50", "NTSC-50 erkennen", "Detectar NTSC-50",
                                      "Détecter le NTSC-50", "NTSC-50を自動検出",
                                      "Detectar NTSC-50", "Определять NTSC-50", "检测 NTSC-50"),
    "settings_stella_messages": ("Info messages", "Infomeldungen", "Mensajes informativos",
                                 "Messages d'information", "情報メッセージ",
                                 "Mensagens informativas", "Информационные сообщения", "提示信息"),
    "settings_stella_filter": ("TV effects", "TV-Effekte", "Efectos de TV", "Effets TV",
                               "テレビ効果", "Efeitos de TV", "Эффекты ТВ", "电视效果"),
    "settings_stella_ntsc_aspect": ("NTSC aspect %", "NTSC-Seitenverhältnis %",
                                    "Aspecto NTSC %", "Format NTSC %", "NTSC アスペクト %",
                                    "Proporção NTSC %", "Пропорции NTSC %", "NTSC 宽高比 %"),
    "settings_stella_pal_aspect": ("PAL aspect %", "PAL-Seitenverhältnis %", "Aspecto PAL %",
                                   "Format PAL %", "PAL アスペクト %", "Proporção PAL %",
                                   "Пропорции PAL %", "PAL 宽高比 %"),
    "settings_stella_crop_hoverscan": ("Crop horizontal overscan",
                                       "Horizontalen Overscan abschneiden",
                                       "Recortar sobrebarrido horizontal",
                                       "Rogner le surbalayage horizontal",
                                       "横のオーバースキャンを切り取る",
                                       "Cortar overscan horizontal",
                                       "Обрезать горизонтальный оверскан", "裁剪水平过扫描"),
    "settings_stella_crop_voverscan": ("Crop vertical overscan", "Vertikalen Overscan abschneiden",
                                       "Recortar sobrebarrido vertical",
                                       "Rogner le surbalayage vertical",
                                       "縦のオーバースキャンを切り取る", "Cortar overscan vertical",
                                       "Обрезать вертикальный оверскан", "裁剪垂直过扫描"),
    "settings_stella_phosphor": ("Phosphor mode", "Phosphor-Modus", "Modo fósforo",
                                 "Mode phosphore", "残光モード", "Modo fósforo",
                                 "Режим послесвечения", "荧光残影模式"),
    "settings_stella_phosphor_blend": ("Phosphor blend %", "Phosphor-Mischung %",
                                       "Mezcla de fósforo %", "Mélange phosphore %",
                                       "残光ブレンド %", "Mistura de fósforo %",
                                       "Смешивание послесвечения %", "荧光混合 %"),
    "settings_stella_palette": ("Palette colors", "Palettenfarben", "Colores de la paleta",
                                "Couleurs de la palette", "パレットの色", "Cores da paleta",
                                "Цвета палитры", "调色板颜色"),
    "settings_stella_pal_contrast": ("Contrast", "Kontrast", "Contraste", "Contraste",
                                     "コントラスト", "Contraste", "Контраст", "对比度"),
    "settings_stella_pal_brightness": ("Brightness", "Helligkeit", "Brillo", "Luminosité",
                                       "明るさ", "Brilho", "Яркость", "亮度"),
    "settings_stella_pal_hue": ("Hue", "Farbton", "Tono", "Teinte", "色相", "Matiz", "Оттенок",
                                "色调"),
    "settings_stella_pal_saturation": ("Saturation", "Sättigung", "Saturación", "Saturation",
                                       "彩度", "Saturação", "Насыщенность", "饱和度"),
    "settings_stella_pal_gamma": ("Gamma", "Gamma", "Gamma", "Gamma", "ガンマ", "Gama", "Гамма",
                                  "伽马"),
    "settings_stella_stereo": ("Stereo sound", "Stereoton", "Sonido estéreo", "Son stéréo",
                               "ステレオ音声", "Som estéreo", "Стереозвук", "立体声"),
    "settings_stella_dpc_pitch": ("Pitfall II music pitch", "Tonhöhe der Pitfall-II-Musik",
                                  "Tono de la música de Pitfall II",
                                  "Hauteur de la musique de Pitfall II",
                                  "Pitfall II の音楽のピッチ", "Tom da música de Pitfall II",
                                  "Высота музыки Pitfall II", "Pitfall II 音乐音高"),
    "settings_stella_paddle_joypad_sensitivity": ("D-Pad sensitivity", "Steuerkreuz-Empfindlichkeit",
                                                  "Sensibilidad de la cruceta",
                                                  "Sensibilité de la croix", "十字キーの感度",
                                                  "Sensibilidade do direcional",
                                                  "Чувствительность крестовины", "方向键灵敏度"),
    "settings_stella_paddle_analog_sensitivity": ("Stick sensitivity", "Stick-Empfindlichkeit",
                                                  "Sensibilidad del stick",
                                                  "Sensibilité du stick", "スティックの感度",
                                                  "Sensibilidade do analógico",
                                                  "Чувствительность стика", "摇杆灵敏度"),
    "settings_stella_paddle_analog_deadzone": ("Stick dead zone", "Stick-Totzone",
                                               "Zona muerta del stick", "Zone morte du stick",
                                               "スティックのデッドゾーン", "Zona morta do analógico",
                                               "Мёртвая зона стика", "摇杆死区"),
    "settings_stella_paddle_analog_absolute": ("Stick sets the position", "Stick bestimmt die Position",
                                               "El stick fija la posición",
                                               "Le stick fixe la position",
                                               "スティックで位置を直接指定",
                                               "Analógico define a posição",
                                               "Стик задаёт положение", "摇杆直接定位"),
    "settings_stella_tab_display": ("Display", "Anzeige", "Pantalla", "Affichage", "表示", "Tela",
                                    "Экран", "显示"),
    "settings_stella_section_screen": ("Screen", "Bild", "Imagen", "Image", "画面", "Imagem",
                                       "Изображение", "画面"),
    "settings_stella_section_hud": ("On-screen info", "Bildschirmanzeige", "Información en pantalla",
                                    "Affichage à l'écran", "画面表示", "Informações na tela",
                                    "Экранная информация", "屏幕信息"),
    "settings_stella_display_mode": ("Display Mode", "Anzeigemodus", "Modo de pantalla",
                                     "Mode d'affichage", "表示モード", "Modo de exibição",
                                     "Режим отображения", "显示模式"),
    "settings_stella_display_size": ("Size", "Größe", "Tamaño", "Taille", "サイズ", "Tamanho",
                                     "Размер", "尺寸"),
    "settings_stella_fps_counter": ("FPS counter", "FPS-Zähler", "Contador de FPS",
                                    "Compteur de FPS", "FPSカウンター", "Contador de FPS",
                                    "Счётчик FPS", "帧率计数器"),
    "settings_stella_rendered_resolution": ("Rendered resolution", "Gerenderte Auflösung",
                                            "Resolución renderizada", "Résolution de rendu",
                                            "描画解像度", "Resolução renderizada",
                                            "Разрешение рендеринга", "渲染分辨率"),
    "settings_stella_section_fast_forward": ("Fast Forward", "Vorspulen", "Avance rápido",
                                             "Avance rapide", "早送り", "Avanço rápido",
                                             "Перемотка", "快进"),
    "settings_stella_fast_forward_speed": ("Fast forward speed", "Vorspul-Geschwindigkeit",
                                           "Velocidad de avance rápido", "Vitesse d'avance rapide",
                                           "早送りの速度", "Velocidade do avanço rápido",
                                           "Скорость перемотки", "快进速度"),
    "settings_stella_fast_forward_mode": ("Fast forward mode", "Vorspul-Modus",
                                          "Modo de avance rápido", "Mode d'avance rapide",
                                          "早送りモード", "Modo do avanço rápido",
                                          "Режим перемотки", "快进模式"),
    "settings_stella_fast_forward_hotkey": ("Fast forward button", "Vorspul-Taste",
                                            "Botón de avance rápido", "Bouton d'avance rapide",
                                            "早送りボタン", "Botão do avanço rápido",
                                            "Кнопка перемотки", "快进按键"),
    "settings_stella_tab_controls": ("Controls", "Steuerung", "Controles", "Commandes", "操作",
                                     "Controles", "Управление", "控制"),
    "settings_stella_section_button_mapping": ("Button mapping", "Tastenbelegung",
                                               "Asignación de botones", "Attribution des boutons",
                                               "ボタン割り当て", "Mapeamento de botões",
                                               "Назначение кнопок", "按键映射"),
    "settings_stella_section_console_switches": ("Console switches", "Konsolenschalter",
                                                 "Interruptores de la consola",
                                                 "Interrupteurs de la console", "本体のスイッチ",
                                                 "Chaves do console", "Переключатели консоли",
                                                 "主机开关"),
    "settings_stella_map_up": ("Joystick Up", "Joystick oben", "Joystick arriba", "Joystick haut",
                               "ジョイスティック上", "Joystick para cima", "Джойстик вверх",
                               "摇杆上"),
    "settings_stella_map_down": ("Joystick Down", "Joystick unten", "Joystick abajo", "Joystick bas",
                                 "ジョイスティック下", "Joystick para baixo", "Джойстик вниз",
                                 "摇杆下"),
    "settings_stella_map_left": ("Joystick Left", "Joystick links", "Joystick izquierda",
                                 "Joystick gauche", "ジョイスティック左", "Joystick para a esquerda",
                                 "Джойстик влево", "摇杆左"),
    "settings_stella_map_right": ("Joystick Right", "Joystick rechts", "Joystick derecha",
                                  "Joystick droite", "ジョイスティック右",
                                  "Joystick para a direita", "Джойстик вправо", "摇杆右"),
    "settings_stella_map_fire": ("Fire", "Feuer", "Disparo", "Tir", "ファイア", "Disparo", "Огонь",
                                 "开火"),
    "settings_stella_map_trigger": ("Booster Grip: trigger", "Booster Grip: Abzug",
                                    "Booster Grip: gatillo", "Booster Grip : gâchette",
                                    "Booster Grip：トリガー", "Booster Grip: gatilho",
                                    "Booster Grip: спуск", "Booster Grip：扳机"),
    "settings_stella_map_booster": ("Booster Grip: booster", "Booster Grip: Booster",
                                    "Booster Grip: booster", "Booster Grip : booster",
                                    "Booster Grip：ブースター", "Booster Grip: booster",
                                    "Booster Grip: ускоритель", "Booster Grip：加速"),
    "settings_stella_map_select": ("Game Select", "Game Select", "Game Select", "Game Select",
                                   "ゲームセレクト", "Game Select", "Game Select", "游戏选择"),
    "settings_stella_map_reset": ("Game Reset", "Game Reset", "Game Reset", "Game Reset",
                                  "ゲームリセット", "Game Reset", "Game Reset", "游戏重置"),
    "settings_stella_map_left_diff_a": ("Left difficulty A", "Linke Schwierigkeit A",
                                        "Dificultad izquierda A", "Difficulté gauche A",
                                        "左の難易度 A", "Dificuldade esquerda A",
                                        "Левая сложность A", "左难度 A"),
    "settings_stella_map_left_diff_b": ("Left difficulty B", "Linke Schwierigkeit B",
                                        "Dificultad izquierda B", "Difficulté gauche B",
                                        "左の難易度 B", "Dificuldade esquerda B",
                                        "Левая сложность B", "左难度 B"),
    "settings_stella_map_right_diff_a": ("Right difficulty A", "Rechte Schwierigkeit A",
                                         "Dificultad derecha A", "Difficulté droite A",
                                         "右の難易度 A", "Dificuldade direita A",
                                         "Правая сложность A", "右难度 A"),
    "settings_stella_map_right_diff_b": ("Right difficulty B", "Rechte Schwierigkeit B",
                                         "Dificultad derecha B", "Difficulté droite B",
                                         "右の難易度 B", "Dificuldade direita B",
                                         "Правая сложность B", "右难度 B"),
    "settings_stella_map_color": ("TV type: Color", "TV-Typ: Farbe", "Tipo de TV: color",
                                  "Type de TV : couleur", "テレビ：カラー", "Tipo de TV: cor",
                                  "Тип ТВ: цветной", "电视：彩色"),
    "settings_stella_map_bw": ("TV type: B/W", "TV-Typ: S/W", "Tipo de TV: B/N",
                               "Type de TV : N/B", "テレビ：白黒", "Tipo de TV: P/B",
                               "Тип ТВ: Ч/Б", "电视：黑白"),
    "settings_stella_analog_dpad": ("Left stick as joystick", "Linker Stick als Joystick",
                                    "Stick izquierdo como joystick",
                                    "Stick gauche comme joystick",
                                    "左スティックをジョイスティックとして使う",
                                    "Analógico esquerdo como joystick",
                                    "Левый стик как джойстик", "左摇杆作为摇杆"),
}

# Choice labels the core does not translate. English -> (de, es, fr, ja, pt, ru, zh)
CHOICES = {
    "NTSC": ("NTSC", "NTSC", "NTSC", "NTSC", "NTSC", "NTSC", "NTSC"),
    "Standard": ("Standard", "Estándar", "Standard", "標準", "Padrão", "Стандартная", "标准"),
    "User": ("Benutzer", "Usuario", "Utilisateur", "ユーザー", "Usuário", "Пользовательская",
             "用户"),
    "Custom": ("Eigene", "Personalizada", "Personnalisée", "カスタム", "Personalizada",
               "Своя", "自定义"),
    "Composite": ("Composite", "Compuesto", "Composite", "コンポジット", "Composto", "Композитный",
                  "复合"),
    "Badly adjusted": ("Schlecht eingestellt", "Mal ajustado", "Mal réglé", "調整不良",
                       "Mal ajustado", "Плохо настроен", "调校不良"),
    "Pixel aspect (PAR)": ("Pixel-Seitenverhältnis (PAR)", "Aspecto de píxel (PAR)",
                           "Format des pixels (PAR)", "ピクセル比（PAR）",
                           "Proporção de pixel (PAR)", "Пропорции пикселя (PAR)", "像素比（PAR）"),
    "On": ("An", "Activado", "Activé", "オン", "Ligado", "Вкл.", "开"),
    "Off": ("Aus", "Desactivado", "Désactivé", "オフ", "Desligado", "Выкл.", "关"),
    "Disabled": ("Deaktiviert", "Desactivado", "Désactivé", "無効", "Desativado", "Выключено",
                 "禁用"),
    "Enabled": ("Aktiviert", "Activado", "Activé", "有効", "Ativado", "Включено", "启用"),
    "Integer": ("Ganzzahlig", "Entero", "Entier", "整数倍", "Inteiro", "Целочисленный", "整数"),
    "Display": ("Anzeige", "Pantalla", "Écran", "画面", "Tela", "Экран", "屏幕"),
    "Stretch": ("Strecken", "Estirar", "Étirer", "引き伸ばし", "Esticar", "Растянуть", "拉伸"),
    "Original": ("Original", "Original", "Original", "オリジナル", "Original", "Оригинал", "原始"),
    "Auto": ("Auto", "Auto", "Auto", "自動", "Auto", "Авто", "自动"),
    "Unlimited": ("Unbegrenzt", "Ilimitado", "Illimité", "無制限", "Ilimitado", "Без ограничений",
                  "无限制"),
    "Hold": ("Halten", "Mantener", "Maintenir", "長押し", "Segurar", "Удерживать", "按住"),
    "Toggle": ("Umschalten", "Alternar", "Basculer", "切り替え", "Alternar", "Переключать", "切换"),
    "Right stick": ("Rechter Stick", "Stick derecho", "Stick droit", "右スティック", "Analógico direito",
                    "Правый стик", "右摇杆"),
    "Left stick": ("Linker Stick", "Stick izquierdo", "Stick gauche", "左スティック", "Analógico esquerdo",
                   "Левый стик", "左摇杆"),
    "Plus": ("Plus", "Más", "Plus", "プラス", "Mais", "Плюс", "加号"),
    "Minus": ("Minus", "Menos", "Moins", "マイナス", "Menos", "Минус", "减号"),
    "Up": ("Oben", "Arriba", "Haut", "上", "Cima", "Вверх", "上"),
    "Down": ("Unten", "Abajo", "Bas", "下", "Baixo", "Вниз", "下"),
    "Left": ("Links", "Izquierda", "Gauche", "左", "Esquerda", "Влево", "左"),
    "Right": ("Rechts", "Derecha", "Droite", "右", "Direita", "Вправо", "右"),
    "Hidden": ("Ausgeblendet", "Oculto", "Masqué", "非表示", "Oculto", "Скрыто", "隐藏"),
    "Top left": ("Oben links", "Arriba a la izquierda", "En haut à gauche", "左上",
                 "Superior esquerdo", "Сверху слева", "左上"),
    "Top right": ("Oben rechts", "Arriba a la derecha", "En haut à droite", "右上",
                  "Superior direito", "Сверху справа", "右上"),
    "Bottom left": ("Unten links", "Abajo a la izquierda", "En bas à gauche", "左下",
                    "Inferior esquerdo", "Снизу слева", "左下"),
    "Bottom right": ("Unten rechts", "Abajo a la derecha", "En bas à droite", "右下",
                     "Inferior direito", "Снизу справа", "右下"),
}

RESTART_SUFFIX = re.compile(r"\s*\((Restart Required|Restart|Reload Core|[^)]*[Nn]eustart[^)]*|[^)]*[Rr]einici[^)]*|"
                            r"[^)]*[Rr]edémarr[^)]*|[^)]*再起動[^)]*|[^)]*перезапуск[^)]*|"
                            r"[^)]*重启[^)]*|[^)]*[Rr]einicializa[^)]*)\)")


def value_key(label: str) -> str:
    """tico_config.cpp's ValueKey: settings_stella_value_ + label as a slug."""
    return "settings_stella_value_" + "_".join(re.findall(r"[a-z0-9]+", label.lower()))


def clean_label(text: str) -> str:
    return RESTART_SUFFIX.sub("", text).lstrip("> ").strip()


def english_choice(value: str, label: str) -> str:
    # the core leaves its values unlabelled, most in lower case
    if label in ("disabled", "enabled"):
        return label.capitalize()
    return EN_CHOICES.get(label, label)


def extract_option_defs() -> str:
    """Stella's option table, as it stands in retro_set_environment."""
    src = (ROOT / "src/os/libretro/libretro.cxx").read_text()
    start = src.index("static struct retro_core_option_v2_definition option_defs[] = {")
    end = src.index("\n  };", start) + len("\n  };")
    return src[start:end].replace("static struct", "struct", 1) + "\n"


def dump_options() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "dump_core_options"
        (Path(tmp) / "stella_option_defs.h").write_text(extract_option_defs())
        subprocess.run(["cc", "-std=gnu11", "-w",
                        "-I", tmp, "-I", str(ROOT / "src/os/libretro"),
                        "-o", str(exe), str(Path(__file__).with_name("dump_core_options.c"))],
                       check=True)
        return json.loads(subprocess.run([str(exe)], check=True, capture_output=True,
                                         text=True).stdout)


def label_key(key: str) -> str:
    return LABEL_KEYS.get(key, "settings_stella_" + key.removeprefix("stella_"))


def build_settings(dump: dict) -> dict:
    core = {o["key"]: o for o in dump["en"]}
    placed = {key for _, sections in LAYOUT for _, keys in sections for key in keys}
    missing = sorted(set(core) - placed - EXCLUDED)
    if missing:
        raise SystemExit(f"core options not placed in LAYOUT: {missing}")

    tabs = []
    for tab, sections in LAYOUT:
        out_sections = []
        for title, keys in sections:
            options = []
            for key in keys:
                source = core[key]
                values = [v for v, _ in source["values"]]
                option = {"key": key, "label": label_key(key)}
                # a default the core does not list is its first choice
                default = source["default"] if source["default"] in values else values[0]
                if sorted(values) == ["disabled", "enabled"]:
                    option.update(type="bool", default=default)
                else:
                    option.update(type="enum", default=default, choices=[
                        {"label": english_choice(v, l), "value": v} for v, l in source["values"]])
                if RESTART_SUFFIX.search(source["desc"]):
                    option["restart"] = True
                if key in DEPENDS_ON:
                    on, value = DEPENDS_ON[key]
                    option["depends_on"] = {"key": on, "value": value}
                options.append(option)
            out_sections.append({"title": title, "options": options})
        tabs.append({"name": tab, "sections": out_sections})

    def overlay_tab(definition):
        tab, sections = definition
        return {"name": tab, "sections": [
            {"title": title, "options": [
                {**o, "choices": [{"label": l, "value": v} for v, l in o["choices"]]}
                if "choices" in o else dict(o)
                for o in options]}
            for title, options in sections]}

    tabs.insert(1, overlay_tab(OVERLAY_TAB))
    tabs.append(overlay_tab(CONTROLS_TAB))

    return {
        "core_id": "stella",
        "display_name": "Stella",
        "config_file": "stella.jsonc",
        "slugs": ["atari-2600"],
        "bool_true_value": "enabled",
        "bool_false_value": "disabled",
        "tabs": tabs,
    }


def tico_owned(key: str) -> bool:
    """Labels tico itself defines, whose wording tico keeps."""
    return key in LABEL_KEYS.values() or key.startswith(("settings_stella_tab_",
                                                          "settings_stella_section_"))


def build_strings(dump: dict, settings: dict,
                  existing: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    strings: dict[str, dict[str, str]] = {lang: {} for lang in LANGUAGES}
    english = {o["key"]: o for o in dump["en"]}
    for lang in LANGUAGES:
        out = strings[lang]
        index = LANGUAGES.index(lang)
        for option in dump[lang]:
            if option["key"] in EXCLUDED or option["key"] not in english:
                continue
            key, en = option["key"], english[option["key"]]
            out[label_key(key)] = clean_label(option["desc"])
            # by value: a translation may list the choices differently
            en_labels = dict(en["values"])
            for value, label in option["values"]:
                if label is None or value not in en_labels:
                    continue
                en_text = english_choice(value, en_labels[value])
                if label != en_labels[value]:
                    out[value_key(en_text)] = label
        for key, texts in LABELS.items():
            out[key] = texts[index]
        if lang != "en":
            for choice, translations in CHOICES.items():
                out[value_key(choice)] = translations[index - 1]
        if lang == "en":
            for key in list(out):
                if key.startswith("settings_stella_value_"):
                    del out[key]
    # tico's own labels keep tico's wording: from tico-nx when it is checked
    # out, otherwise as the language files already have them
    for lang in LANGUAGES:
        path = TICO_NX / "assets/lang" / f"{lang}.json"
        source = json.loads(path.read_text()) if path.exists() else existing[lang]
        for key, value in source.items():
            if tico_owned(key):
                strings[lang][key] = value
    used = set()

    def walk(node):
        if isinstance(node, dict):
            for field in ("label", "name", "title"):
                if isinstance(node.get(field), str) and node[field].startswith("settings_"):
                    used.add(node[field])
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(settings)
    unlabelled = sorted(used - set(strings["en"]))
    if unlabelled:
        raise SystemExit(f"labels without English text: {unlabelled}")
    return strings


def main() -> None:
    dump = dump_options()
    settings = build_settings(dump)
    SETTINGS.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    current_files = {lang: json.loads((LANG_DIR / f"{lang}.json").read_text())
                     if (LANG_DIR / f"{lang}.json").exists() else {} for lang in LANGUAGES}
    for lang, strings in build_strings(dump, settings, current_files).items():
        path = LANG_DIR / f"{lang}.json"
        current = {k: v for k, v in current_files[lang].items()
                   if not k.startswith("settings_stella_")}
        current.update(dict(sorted(strings.items())))
        path.write_text(json.dumps(current, indent=4, ensure_ascii=False) + "\n")
    print(f"wrote {SETTINGS.relative_to(ROOT)} and {len(LANGUAGES)} language files")


if __name__ == "__main__":
    main()
