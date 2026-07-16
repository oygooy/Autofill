"""
코드 수정일: 2026.06.01
랜덤 문자열 자동 입력기 v3
============================
- 5종류: 숫자 / 영어대문자 / 영어소문자 / 한글 / 특수문자
- 작업표시줄 버튼 클릭  → 활성화 (첫 클릭 무시, 두 번째 클릭에 입력)
- 입력 완료 후 자동 종료
- 작업표시줄 우클릭 → 창 닫기 = 실제 종료
- 시스템 트레이 우클릭 → 옵션 설정 / 활성화 / 종료
- 옵션: 종류별 사용 체크 + 글자수 + 순서 변경 (▲▼)
- 설정 자동 저장

설치:
  pip install pynput pystray pillow

.exe 변환:
  pip install pyinstaller
  pyinstaller --onefile --windowed --name Autofill --icon="Autofill.ico" --add-data "Autofill.ico;." Autofill.py

[수정 사항 - exe 빌드 대응]
  Fix 1: spurious FocusIn 차단을 시간 기반 → 횟수 기반으로 변경
          (시간 기반은 PC 속도에 따라 불안정, 횟수 기반은 항상 정확)
  Fix 2: 클립보드 설정 시 root.update() → root.update_idletasks()
          (update()는 exe 환경에서 이벤트 큐 충돌 유발 가능)
  Fix 3: on_mouse_click 내 tray.title 직접 변경 → root.after() 경유
          (pynput 스레드에서 직접 tray 접근 시 exe 환경에서 간헐적 오류)
"""

# ── 기본 라이브러리 임포트 ──────────────────────────────────────────
import sys          # 시스템 종료 등 기본 시스템 기능
import random       # 랜덤 문자 선택에 사용
import string       # 기본 문자열 상수 (digits 등)
import threading    # 백그라운드 실행을 위한 스레드
import time         # 딜레이(대기) 처리
import json         # 설정 파일 저장/불러오기 (JSON 형식)
import os           # 파일 경로, 프로세스 종료 등 OS 기능
import math         # 트레이 아이콘의 별 모양 계산에 사용
import tkinter as tk                    # GUI 창 만들기
from tkinter import messagebox          # 알림/오류 팝업 창
import subprocess                       # (미사용 예비 임포트)

# ── 외부 패키지 임포트 (없으면 안내 후 종료) ──────────────────────
try:
    from pynput import mouse                        # 마우스 클릭 감지
    from pynput.keyboard import Controller as KeyboardController  # 키보드 자동 입력
    import pystray                                  # 시스템 트레이 아이콘
    from PIL import Image, ImageDraw                # 트레이 아이콘 이미지 생성
except ImportError as e:
    # 필요한 패키지가 없을 때 오류 창 표시 후 종료
    r = tk.Tk(); r.withdraw()
    messagebox.showerror("패키지 필요",
        f"pip install pynput pystray pillow\n\n오류: {e}")
    sys.exit(1)

# ════════════════════════════════════════════════════════════════════
# ── 설정 파일 경로 및 문자 풀(pool) 정의 ───────────────────────────
# ════════════════════════════════════════════════════════════════════

# 설정을 저장할 JSON 파일 경로 (사용자 홈 디렉토리에 저장)
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".random_typer_v3_settings.json")

# 각 유형별로 실제로 사용할 문자 목록 (딕셔너리)
CHAR_POOLS = {
    "숫자":       "0123456789",
    "영어대문자": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "영어소문자": "abcdefghijklmnopqrstuvwxyz",
    "한글": (
        "가각간갈감갑강개갱거건걸검겁게겨격견결겸경계고곡골곰곱공과관광괜"
        "구국군굴굼굽궁귀규그극근글금급기긴길김나낙난날남납낭내냉너넉넌널"
        "넘네녀년념녕노녹논놀놈농누눈눌능니닐님다닥단달담답당대더덕던덜덤"
        "덥도독돈돌돔동두둑둘둠둥뒤드득든들듬등디따딱딴딸땀땅때떠떡떨데"
        "또뛰뜨뜬뜰뜻라락란랄람랍랑래러럭런럴럼럽레려력련렬령례로록론롬롭"
        "롱루룩룬룰룸룹류른를름릇리릭린림립링마막만많말맑맘맙망매맥맨맵"
        "맹머먹먼멀멈멋메며면멸명모목몰몸몹못무묵묶문묻물뭄뭐뮤미민밀밈"
        "바박반받발밝밟밤밥방배백뱀버벅번벌범법벗베별병보복본볼봄봉부북"
        "분불붓붙뷰브블비빅빈빌빔빕빛빠빨뻔뻘뼈뽑뿌사삭산살삼삽상새색"
        "샌생서석선설섬섭성세션소속손솔솜솟송쇠수숙순술숨습싱시식신실심"
        "십씩씨아악안알암압앙애액야약얀얇어억언얼엄없에여역연열염엽영예"
        "오옥온올옴옵와완왕왜요욕용우욱운울움웅위유육은을음읍이익인일임"
        "잇자작잔잘잠잡장재저적전절점접정제조족존졸좀좋주죄죽준줄중즉즐"
        "증지직진질짐짓집짝짧째쪽차착찬찰참창채처척천철첨첫청체초촉총최"
        "추축출충취층치칙친칠침카칸칼캐커컨컬컴컵켜코콕콘콜콤큰클타탁"
        "탄탈탐탑탓터텀텅테톤통투툭틀팀파팬팽퍼펑페편평폐포폭표푸풀품"
        "피픽필하학한할함합항해핵햇행허헌험헤현협형혜호혹혼홀홈홉화확환활황회"
    ),
    "특수문자": r"~`!@#$%^&*()_+-={}|[]\:"";'<>?,./",
}

# ── 키보드에서 입력 가능한 특수문자 전체 목록 (그룹별로 분류) ─────
ALL_SPECIAL_GROUPS = [
    ("숫자행 위 (Shift+1~0)",  list("!@#$%^&*()")),
    ("대시 / 등호 / 언더바",   list("_+-=")),
    ("괄호류",                 list("{}[]()")),
    ("슬래시 / 파이프 / 역슬래시", list(r"|\/:")),
    ("문장 부호",              list(";'\"<>?,./")),
    ("물결 / 백틱",            list("~`")),
]

# ── 중복 없이 전체 특수문자 합치기 ─────────────────────────────────
_seen = set()
_all  = []
for _grp_name, _chars in ALL_SPECIAL_GROUPS:
    for _c in _chars:
        if _c not in _seen:
            _seen.add(_c)
            _all.append(_c)
ALL_SPECIAL_CHARS = "".join(_all)

# ── 기본 설정값 ───────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "segments": [
        {"type": "숫자",       "enabled": True,  "count": 4},
        {"type": "영어대문자", "enabled": False, "count": 2},
        {"type": "영어소문자", "enabled": True,  "count": 3},
        {"type": "한글",       "enabled": False, "count": 2},
        {"type": "특수문자",   "enabled": False, "count": 2},
    ],
    "special_chars": list(ALL_SPECIAL_CHARS),
    "total_count": "",
}

# ── 설정 불러오기 함수 ─────────────────────────────────────────────
def load_settings():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "segments" in data and len(data["segments"]) == 5:
                    types = {s["type"] for s in data["segments"]}
                    if types == set(CHAR_POOLS.keys()):
                        valid = all(
                            isinstance(s.get("type"), str) and s["type"] in CHAR_POOLS
                            and isinstance(s.get("enabled"), bool)
                            and isinstance(s.get("count"), int)
                            for s in data["segments"]
                        )
                        if valid:
                            if "special_chars" not in data:
                                data["special_chars"] = list(ALL_SPECIAL_CHARS)
                            elif not isinstance(data["special_chars"], list):
                                data["special_chars"] = list(ALL_SPECIAL_CHARS)
                            if len(data["special_chars"]) == 0:
                                data["special_chars"] = list(ALL_SPECIAL_CHARS)
                            if "total_count" not in data:
                                data["total_count"] = ""
                            if "total_count_enabled" in data:
                                if not data["total_count_enabled"]:
                                    data["total_count"] = ""
                                del data["total_count_enabled"]
                            if "picker_geometry" not in data:
                                data["picker_geometry"] = "380x500"
                            return data
    except Exception:
        pass
    return json.loads(json.dumps(DEFAULT_SETTINGS))

# ── 설정 저장 함수 ─────────────────────────────────────────────────
def save_settings(cfg):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[설정 저장 실패] {e}")

settings = load_settings()

# ════════════════════════════════════════════════════════════════════
# ── 랜덤 문자열 생성 함수 ──────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
def generate_string():
    sc_selected = settings.get("special_chars", list(ALL_SPECIAL_CHARS))
    sp_pool = "".join(sc_selected) if sc_selected else ALL_SPECIAL_CHARS

    total_count_str = str(settings.get("total_count", "")).strip()
    use_total = total_count_str.isdigit() and int(total_count_str) > 0

    if use_total:
        combined_pool = ""
        for seg in settings["segments"]:
            if seg["enabled"]:
                if seg["type"] == "특수문자":
                    combined_pool += sp_pool
                else:
                    combined_pool += CHAR_POOLS[seg["type"]]
        if not combined_pool:
            combined_pool = string.digits
        total = int(total_count_str)
        return "".join(random.choices(combined_pool, k=total))
    else:
        parts = []
        for seg in settings["segments"]:
            if seg["enabled"] and seg["count"] > 0:
                seg_type = seg["type"]
                if seg_type == "특수문자":
                    pool = sp_pool
                else:
                    pool = CHAR_POOLS[seg_type]
                parts.append("".join(random.choices(pool, k=seg["count"])))
        return "".join(parts) or "".join(random.choices(string.digits, k=10))

# ════════════════════════════════════════════════════════════════════
# ── 전역 상태 변수 ─────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
kb = KeyboardController()
mouse_listener = None
click_count = 0
is_active = False
_activating = False
_activate_time = 0.0      # activate() 호출된 시각 (time.monotonic)
_ACTIVATE_GUARD_SEC = 0.15  # activate 후 이 시간(초) 안에 온 클릭은 spurious로 무시
                             # 더블클릭(~0.25초)보다 짧게 설정 → 빠른 연속 클릭도 인식 가능

# ── [Fix 1] spurious FocusIn 차단: 시간 기반 → 횟수 기반으로 변경 ──
#
# 기존 방식(시간 기반)의 문제:
#   PyInstaller exe는 PC 성능에 따라 시작 속도가 달라서,
#   고정된 2000ms 타이머로는 spurious FocusIn이 그 안에 끝날지 보장 안 됨.
#   빠른 PC → 2초가 너무 길어서 사용자가 기다려야 함.
#   느린 PC → 2초 안에 spurious가 다 안 끝나서 오작동.
#
# 새 방식(횟수 기반):
#   exe 환경에서 spurious FocusIn은 항상 정해진 횟수(통상 1~2회)만 발생.
#   처음 _SPURIOUS_IGNORE_COUNT 번은 무조건 무시하고,
#   그 이후부터 실제 클릭으로 인정.
#   PC 속도와 무관하게 항상 정확하게 동작.
#
_SPURIOUS_IGNORE_COUNT = 0   # FocusIn 횟수 기반 차단 비활성화
                              # → 대신 activate() 내 리스너 시작 딜레이(600ms)로 spurious 클릭 흘려보냄
_spurious_remain = _SPURIOUS_IGNORE_COUNT


# ════════════════════════════════════════════════════════════════════
# ── 트레이 아이콘 이미지 생성 ──────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
def make_tray_image(active: bool) -> Image.Image:
    S = 128
    img  = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if active:
        bg1 = (34, 197, 94)
        bg2 = (16, 185, 129)
        accent = (255, 255, 255)
        glow   = (134, 239, 172, 80)
    else:
        bg1 = (99, 102, 241)
        bg2 = (139, 92, 246)
        accent = (255, 255, 255)
        glow   = (167, 139, 250, 60)

    draw.ellipse([8, 8, S-8, S-8], fill=glow)
    draw.ellipse([14, 14, S-14, S-14], fill=bg2)
    draw.ellipse([18, 18, S-18, S-18], fill=bg1)

    kx1, ky1, kx2, ky2 = 22, 44, 106, 88
    draw.rounded_rectangle([kx1, ky1, kx2, ky2], radius=8,
                            fill=(255, 255, 255, 220))

    key_color  = bg1
    key_color2 = bg2

    for ki in range(6):
        x = kx1 + 6 + ki * 13
        draw.rounded_rectangle([x, ky1+5, x+10, ky1+13], radius=2, fill=key_color)
    for ki in range(5):
        x = kx1 + 10 + ki * 14
        draw.rounded_rectangle([x, ky1+18, x+11, ky1+26], radius=2, fill=key_color)
    draw.rounded_rectangle([kx1+20, ky1+31, kx2-20, ky1+39], radius=3, fill=key_color2)

    def draw_star(cx, cy, r, color):
        points = []
        for i in range(8):
            angle = math.radians(i * 45 - 90)
            radius = r if i % 2 == 0 else r * 0.45
            points.append((cx + radius * math.cos(angle),
                            cy + radius * math.sin(angle)))
        draw.polygon(points, fill=color)

    star_col = (255, 255, 200, 230)
    draw_star(88, 28, 9,  star_col)
    draw_star(104, 20, 6, (255, 240, 150, 200))
    draw_star(96, 38, 4,  (255, 255, 180, 180))

    return img.resize((64, 64), Image.LANCZOS)


# ════════════════════════════════════════════════════════════════════
# ── 종료 함수 ──────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
def do_exit():
    deactivate()
    try:
        tray.stop()
    except:
        pass
    root.quit()
    os._exit(0)

# ════════════════════════════════════════════════════════════════════
# ── 메인 창 생성 ───────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
root = tk.Tk()
root.title("✨ Autofill")

if getattr(sys, 'frozen', False):
    icon_path = os.path.join(sys._MEIPASS, "Autofill.ico")
else:
    icon_path = "Autofill.ico"

if os.path.exists(icon_path):
    root.iconbitmap(icon_path)

sw = root.winfo_screenwidth()
sh = root.winfo_screenheight()
root.geometry(f"1x1+{sw-1}+{sh-1}")
root.resizable(False, False)
root.attributes("-alpha", 0.0)
root.overrideredirect(False)
root.protocol("WM_DELETE_WINDOW", do_exit)

# ════════════════════════════════════════════════════════════════════
# ── 문자 입력 실행 함수 ─────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
def generate_and_type():
    """
    랜덤 문자열을 생성하고 현재 포커스된 입력창에 자동 타이핑.

    [Fix 2] root.update() → root.update_idletasks() 로 변경
      root.update()는 tkinter 이벤트 큐 전체를 강제 처리하므로
      exe 환경에서 after 콜백들과 충돌하여 clipboard_ready.set()이
      늦게 호출되거나 타임아웃이 발생할 수 있음.
      update_idletasks()는 idle 이벤트(화면 갱신 등)만 처리하므로 안전.
    """
    from pynput.keyboard import Key

    text = generate_string()
    time.sleep(0.15)

    clipboard_ready = threading.Event()

    def _set_clipboard():
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update_idletasks()   # ★ Fix 2: update() → update_idletasks()
        except Exception as e:
            print(f"[클립보드 오류] {e}")
        finally:
            clipboard_ready.set()

    # ── 클립보드 복사 재시도 루프 ────────────────────────────────────
    MAX_CLIP_RETRY = 3
    for attempt in range(MAX_CLIP_RETRY):
        clipboard_ready.clear()
        root.after(0, _set_clipboard)
        ok = clipboard_ready.wait(timeout=3.0)
        if ok:
            break
        print(f"[클립보드 대기 타임아웃] 재시도 {attempt+1}/{MAX_CLIP_RETRY}")
        time.sleep(0.2)

    time.sleep(0.05)

    kb.press(Key.ctrl)
    kb.press('v')
    kb.release('v')
    kb.release(Key.ctrl)

    print(f"[입력됨] {text}")
    root.after(0, deactivate)

# ════════════════════════════════════════════════════════════════════
# ── 활성화 / 비활성화 함수 ─────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
def activate():
    global mouse_listener, click_count, is_active, _activating
    if _activating:
        return
    _activating = True
    try:
        if is_active:
            deactivate()
            return
        is_active = True
        click_count = 0
        root.title("🟢 대기 중")
        tray.title = "🟢 대기 중 — 다음 클릭에 입력"
        tray.icon  = make_tray_image(True)
        print("[활성화]")

        if mouse_listener:
            try: mouse_listener.stop()
            except: pass

        def _activate_time_setter():
            global _activate_time
            _activate_time = time.monotonic()

        def _start_listener():
            global mouse_listener
            mouse_listener = mouse.Listener(on_click=on_mouse_click)
            mouse_listener.start()

        _activate_time_setter()
        root.after(100, _start_listener)   # 100ms 후 리스너 시작 (spurious 흘려보내기 최소화)
                                            # 실제 spurious 클릭 차단은 on_mouse_click 내
                                            # _ACTIVATE_GUARD_SEC 시간 비교로 처리

    finally:
        _activating = False

def deactivate():
    global mouse_listener, is_active, click_count
    is_active = False
    click_count = 0

    if mouse_listener:
        try: mouse_listener.stop()
        except: pass
        mouse_listener = None

    root.title("✨ 랜덤입력기")
    try:
        tray.title = "✨ 랜덤입력기 — 트레이 우클릭: 옵션"
        tray.icon  = make_tray_image(False)
    except:
        pass
    print("[비활성화]")

def on_mouse_click(x, y, button, pressed):
    """
    [Fix 3] tray.title 직접 변경 → root.after() 경유로 변경
      on_mouse_click은 pynput의 별도 스레드에서 호출됨.
      exe 환경에서는 스레드 안전성이 더 엄격하여,
      pynput 스레드에서 tray 객체를 직접 변경하면 간헐적 오류 발생.
      tkinter 메인 루프 스레드에서 처리하도록 root.after(0, ...) 경유.
    """
    global click_count
    if not pressed:
        return
    if button != mouse.Button.left:
        return
    if not is_active:
        return

    # activate 직후 _ACTIVATE_GUARD_SEC 이내에 온 클릭은 spurious로 무시
    # (아이콘 클릭 자체가 리스너에 잡히는 것 방지)
    # 이후 클릭은 더블클릭 속도라도 정상 인식
    elapsed = time.monotonic() - _activate_time
    if elapsed < _ACTIVATE_GUARD_SEC:
        print(f"[클릭 무시] activate 후 {elapsed:.3f}초 — guard 범위")
        return

    click_count += 1

    if click_count == 1:
        root.after(0, lambda: root.title("🟡 다음 클릭에 입력!"))
        root.after(0, lambda: setattr(tray, 'title', "🟡 다음 클릭에 입력!"))  # ★ Fix 3
        print("[클릭1] 무시")
    elif click_count >= 2:
        root.after(0, lambda: root.title("✨ 랜덤입력기"))
        threading.Thread(target=generate_and_type, daemon=True).start()

def on_focus_in(event):
    """
    작업표시줄 버튼 클릭으로 창이 포커스를 받았을 때 호출됨.

    spurious 횟수 차단 제거 → activate() 내 600ms 딜레이로 대신 처리.
    FocusIn 발생 즉시 activate 예약 + 창 내리기.
    이미 활성화 중이면 activate() 내부에서 deactivate 후 리턴하므로 중복 없음.
    """
    root.after(10, activate)
    root.after(30, lambda: root.lower())

root.bind("<FocusIn>", on_focus_in)

# ════════════════════════════════════════════════════════════════════
# ── 옵션 창 ────────────────────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
option_window = None

def open_options():
    global option_window
    if option_window and option_window.winfo_exists():
        option_window.lift()
        option_window.focus_force()
        return

    win = tk.Toplevel(root)
    win.title("✨ 랜덤입력기 옵션")
    win.geometry("560x680")
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.attributes("-alpha", 1.0)
    option_window = win

    BG       = "#0f0f1a"
    PANEL    = "#1a1a2e"
    PANEL2   = "#16213e"
    ACCENT   = "#6366f1"
    ACCENT2  = "#8b5cf6"
    FG       = "#e2e8f0"
    FG2      = "#94a3b8"
    BTN_BG   = "#1e293b"
    BTN_HOV  = "#334155"
    ENTRY_BG = "#0a0a14"
    DANGER   = "#ef4444"
    SUCCESS  = "#22c55e"
    UP_COL   = "#3b82f6"
    DN_COL   = "#f59e0b"

    win.configure(bg=BG)

    FONT_H  = ("Malgun Gothic", 14, "bold")
    FONT_B  = ("Malgun Gothic", 11)
    FONT_S  = ("Malgun Gothic", 10)
    FONT_XS = ("Malgun Gothic", 9)

    hdr = tk.Frame(win, bg=PANEL, pady=14)
    hdr.pack(fill="x")
    tk.Label(hdr, text="✨ 랜덤 문자열 조합 설정",
             font=FONT_H, bg=PANEL, fg=FG).pack()
    tk.Label(hdr, text="5종류 중 원하는 조합을 선택하고 순서와 글자수를 지정하세요.",
             font=FONT_XS, bg=PANEL, fg=FG2).pack(pady=(2,0))

    outer = tk.Frame(win, bg=BG)
    outer.pack(fill="x", padx=20, pady=12)

    col_cfg = [("순서",4), ("이동",8), ("종류",13), ("사용",5), ("글자수",7), ("세부",5)]
    for c, (txt, w) in enumerate(col_cfg):
        tk.Label(outer, text=txt, font=("Malgun Gothic",9,"bold"),
                 bg=BG, fg=FG2, width=w, anchor="center"
                 ).grid(row=0, column=c, padx=3, pady=(0,4))

    tmp_segs   = json.loads(json.dumps(settings["segments"]))
    row_widgets = []
    en_vars     = []
    cnt_vars    = []

    ICONS = {
        "숫자":       "🔢",
        "영어대문자": "🔠",
        "영어소문자": "🔡",
        "한글":       "가나",
        "특수문자":   "!@#",
    }
    ROW_COLORS = [PANEL, PANEL2]

    def _sync():
        for i in range(len(tmp_segs)):
            if i < len(en_vars):
                tmp_segs[i]["enabled"] = en_vars[i].get()
            if i < len(cnt_vars):
                try:
                    tmp_segs[i]["count"] = max(0, int(cnt_vars[i].get()))
                except ValueError:
                    pass

    def open_special_chars_picker():
        sub = tk.Toplevel(win)
        sub.title("⌨ 특수문자 선택")
        sub.attributes("-topmost", True)
        sub.configure(bg=BG)

        saved_geo = settings.get("picker_geometry", "380x500")
        try:
            _w, _h = saved_geo.split("x")
            int(_w); int(_h)
        except Exception:
            saved_geo = "380x500"
        sub.geometry(saved_geo)

        sub.resizable(True, True)
        sub.minsize(320, 380)

        def _on_close():
            geo = sub.geometry()
            size_only = geo.split("+")[0]
            settings["picker_geometry"] = size_only
            sub.destroy()

        sub.protocol("WM_DELETE_WINDOW", _on_close)

        header_frame = tk.Frame(sub, bg=PANEL)
        header_frame.pack(fill="x", side="top")
        tk.Label(header_frame, text="⌨ 사용할 특수문자 선택",
                 font=FONT_H, bg=PANEL, fg=FG, pady=10).pack()
        tk.Label(header_frame, text="체크된 특수문자만 랜덤 생성에 사용됩니다.",
                 font=FONT_XS, bg=PANEL, fg=FG2).pack(pady=(0,6))

        bottom_frame = tk.Frame(sub, bg=BG)
        bottom_frame.pack(fill="x", side="bottom", pady=(0, 4))

        btn_row = tk.Frame(bottom_frame, bg=BG)
        btn_row.pack(pady=(6, 2))

        current_selected = set(settings.get("special_chars", list(ALL_SPECIAL_CHARS)))
        char_vars = {}

        def select_all():
            for v in char_vars.values():
                v.set(True)

        def deselect_all():
            for v in char_vars.values():
                v.set(False)

        tk.Button(btn_row, text="전체 선택", command=select_all,
                  bg=ACCENT2, fg="white", font=FONT_S,
                  relief="flat", cursor="hand2", padx=10, pady=4
                  ).pack(side="left", padx=6)
        tk.Button(btn_row, text="전체 해제", command=deselect_all,
                  bg=BTN_BG, fg=FG2, font=FONT_S,
                  relief="flat", cursor="hand2", padx=10, pady=4
                  ).pack(side="left", padx=6)

        confirm_row = tk.Frame(bottom_frame, bg=BG)
        confirm_row.pack(pady=(2, 8))

        def do_save_chars():
            selected = [ch for ch, v in char_vars.items() if v.get()]
            if not selected:
                messagebox.showwarning(
                    "선택 없음",
                    "최소 1개 이상 선택해야 합니다.\n전체 특수문자로 초기화합니다.",
                    parent=sub
                )
                selected = list(ALL_SPECIAL_CHARS)
            settings["special_chars"] = selected
            for rw in row_widgets:
                if "sp_btn_var" in rw:
                    rw["sp_btn_var"].set(f"⚙ {len(selected)}개")
            geo = sub.geometry()
            settings["picker_geometry"] = geo.split("+")[0]
            messagebox.showinfo(
                "저장 완료",
                f"{len(selected)}개 특수문자가 선택되었습니다.\n"
                "옵션 창에서 [💾 저장]을 눌러야 최종 저장됩니다.",
                parent=sub
            )
            sub.destroy()

        tk.Button(confirm_row, text="✔ 저장", command=do_save_chars,
                  bg=SUCCESS, fg="white", font=FONT_B,
                  relief="flat", cursor="hand2", padx=14, pady=6
                  ).pack(side="left", padx=6)
        tk.Button(confirm_row, text="✕ 취소", command=_on_close,
                  bg=BTN_BG, fg=FG, font=FONT_B,
                  relief="flat", cursor="hand2", padx=10, pady=6
                  ).pack(side="left", padx=6)

        canvas_frame = tk.Frame(sub, bg=BG)
        canvas_frame.pack(fill="both", expand=True, padx=0, pady=0)

        canvas = tk.Canvas(canvas_frame, bg=BG, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")

        canvas.configure(yscrollcommand=scrollbar.set)

        inner = tk.Frame(canvas, bg=BG)
        canvas_window = canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")

        def _on_inner_resize(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event):
            canvas.itemconfig(canvas_window, width=event.width)

        inner.bind("<Configure>", _on_inner_resize)
        canvas.bind("<Configure>", _on_canvas_resize)

        def _on_mousewheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        sub.bind("<MouseWheel>", _on_mousewheel)
        sub.bind("<Button-4>",   _on_mousewheel)
        sub.bind("<Button-5>",   _on_mousewheel)

        for group_name, chars in ALL_SPECIAL_GROUPS:
            tk.Label(inner, text=group_name,
                     font=("Malgun Gothic", 9, "bold"),
                     bg=BG, fg=FG2, anchor="w"
                     ).pack(fill="x", padx=14, pady=(10, 2))

            row_f = tk.Frame(inner, bg=PANEL, pady=6, padx=8)
            row_f.pack(fill="x", padx=14)

            for ch in chars:
                var = tk.BooleanVar(value=(ch in current_selected))
                char_vars[ch] = var

                cb = tk.Checkbutton(
                    row_f, text=ch, variable=var,
                    font=("Consolas", 13, "bold"),
                    bg=PANEL, fg=FG,
                    activebackground=PANEL,
                    selectcolor=ACCENT,
                    relief="flat", cursor="hand2",
                    width=2
                )
                cb.pack(side="left", padx=2)

    def build_rows():
        for rw in row_widgets:
            for w in rw.values():
                try: w.destroy()
                except: pass
        row_widgets.clear()
        en_vars.clear()
        cnt_vars.clear()

        for i, seg in enumerate(tmp_segs):
            rb = ROW_COLORS[i % 2]
            r  = i + 1

            num = tk.Label(outer, text=str(i+1), font=FONT_B,
                           bg=rb, fg=FG2, width=4, anchor="center")
            num.grid(row=r, column=0, padx=3, pady=6)

            bf = tk.Frame(outer, bg=rb)
            bf.grid(row=r, column=1, padx=3, pady=6)

            def mk_up(idx):
                def _():
                    if idx == 0: return
                    _sync()
                    tmp_segs[idx], tmp_segs[idx-1] = tmp_segs[idx-1], tmp_segs[idx]
                    build_rows()
                return _

            def mk_dn(idx):
                def _():
                    if idx == len(tmp_segs)-1: return
                    _sync()
                    tmp_segs[idx], tmp_segs[idx+1] = tmp_segs[idx+1], tmp_segs[idx]
                    build_rows()
                return _

            tk.Button(bf, text="▲", command=mk_up(i),
                      bg=UP_COL, fg="white", font=("Malgun Gothic",8,"bold"),
                      relief="flat", cursor="hand2", width=3, pady=1,
                      activebackground="#60a5fa"
                      ).pack(side="left", padx=(0,2))
            tk.Button(bf, text="▼", command=mk_dn(i),
                      bg=DN_COL, fg="white", font=("Malgun Gothic",8,"bold"),
                      relief="flat", cursor="hand2", width=3, pady=1,
                      activebackground="#fbbf24"
                      ).pack(side="left")

            icon = ICONS.get(seg["type"], "")
            lbl = tk.Label(outer, text=f"{icon} {seg['type']}", font=FONT_B,
                           bg=rb, fg=FG, width=13, anchor="w")
            lbl.grid(row=r, column=2, padx=3, pady=6)

            en_var = tk.BooleanVar(value=seg["enabled"])
            chk = tk.Checkbutton(outer, variable=en_var,
                                 bg=rb, activebackground=rb,
                                 selectcolor=ACCENT, relief="flat", cursor="hand2")
            chk.grid(row=r, column=3, padx=3, pady=6)
            en_vars.append(en_var)

            cnt_var = tk.StringVar(value=str(seg["count"]))
            ent = tk.Entry(outer, textvariable=cnt_var, width=7,
                           font=FONT_B, justify="center",
                           bg=ENTRY_BG, fg=FG, insertbackground=FG,
                           relief="flat", highlightthickness=1,
                           highlightcolor=ACCENT, highlightbackground=BTN_BG)
            ent.grid(row=r, column=4, padx=3, pady=6)
            cnt_vars.append(cnt_var)

            if seg["type"] == "특수문자":
                sc_count = len(settings.get("special_chars", list(ALL_SPECIAL_CHARS)))
                sp_btn_var = tk.StringVar(value=f"⚙ {sc_count}개")

                sp_btn = tk.Button(
                    outer,
                    textvariable=sp_btn_var,
                    command=open_special_chars_picker,
                    bg="#334155", fg="#93c5fd",
                    font=("Malgun Gothic", 8, "bold"),
                    relief="flat", cursor="hand2",
                    width=5, pady=3,
                    activebackground="#475569"
                )
                sp_btn.grid(row=r, column=5, padx=3, pady=6)
                row_widgets.append({"num":num,"bf":bf,"lbl":lbl,"chk":chk,"ent":ent,
                                    "sp_btn":sp_btn,"sp_btn_var":sp_btn_var})
            else:
                empty = tk.Label(outer, text="", bg=rb, width=5)
                empty.grid(row=r, column=5, padx=3, pady=6)
                row_widgets.append({"num":num,"bf":bf,"lbl":lbl,"chk":chk,"ent":ent,
                                    "empty":empty})

    build_rows()

    sep = tk.Frame(win, bg=ACCENT, height=1)
    sep.pack(fill="x", padx=20, pady=(8,6))

    total_frame = tk.Frame(win, bg=PANEL2, pady=10, padx=18)
    total_frame.pack(fill="x", padx=20, pady=(0,6))

    total_count_var = tk.StringVar(value="")

    tk.Label(total_frame,
             text="총 글자수 (비우면 위 설정대로, 숫자 입력 시 섞어서 생성):",
             font=FONT_S, bg=PANEL2, fg=FG2
             ).pack(side="left", padx=(0, 8))

    total_entry = tk.Entry(
        total_frame, textvariable=total_count_var,
        width=6, font=FONT_B, justify="center",
        bg=ENTRY_BG, fg=FG, insertbackground=FG,
        relief="flat", highlightthickness=1,
        highlightcolor=ACCENT, highlightbackground=BTN_BG
    )
    total_entry.pack(side="left")

    sep2 = tk.Frame(win, bg="#1e293b", height=1)
    sep2.pack(fill="x", padx=20, pady=(6,6))

    pf = tk.Frame(win, bg=PANEL, pady=10, padx=18)
    pf.pack(fill="x", padx=20)

    pf_top = tk.Frame(pf, bg=PANEL)
    pf_top.pack(fill="x")
    tk.Label(pf_top,
             text="미리보기  (직접 수정 및 드래그 복사 가능)",
             font=FONT_XS, bg=PANEL, fg=FG2).pack(side="left")

    prev_var = tk.StringVar(value="")

    prev_entry = tk.Entry(
        pf, textvariable=prev_var,
        font=("Consolas", 14, "bold"),
        bg="#0d1117", fg=SUCCESS,
        insertbackground=SUCCESS,
        relief="flat",
        highlightthickness=1,
        highlightcolor=ACCENT,
        highlightbackground="#1e293b",
        state="normal"
    )
    prev_entry.pack(fill="x", pady=(6,2))

    len_var = tk.StringVar(value="")
    tk.Label(pf, textvariable=len_var, font=FONT_XS,
             bg=PANEL, fg=FG2).pack(anchor="w", pady=(0,2))

    def _build_preview_pool():
        _sync()
        sc_sel = settings.get("special_chars", list(ALL_SPECIAL_CHARS))
        sp_p   = "".join(sc_sel) if sc_sel else ALL_SPECIAL_CHARS

        tc_str = total_count_var.get().strip()
        use_total = tc_str.isdigit() and int(tc_str) > 0

        if use_total:
            combined = ""
            for seg in tmp_segs:
                if seg["enabled"]:
                    combined += (sp_p if seg["type"] == "특수문자"
                                 else CHAR_POOLS[seg["type"]])
            if not combined:
                return "(선택된 유형 없음)", 0
            total = int(tc_str)
            result = "".join(random.choices(combined, k=total))
        else:
            parts = []
            for seg in tmp_segs:
                if seg["enabled"] and seg["count"] > 0:
                    p = (sp_p if seg["type"] == "특수문자"
                         else CHAR_POOLS[seg["type"]])
                    parts.append("".join(random.choices(p, k=seg["count"])))
            result = "".join(parts)
            if not result:
                return "(선택된 항목 없음)", 0

        return result, len(result)

    def do_preview():
        result, length = _build_preview_pool()
        prev_var.set(result)
        prev_entry.icursor(tk.END)
        if length:
            win.clipboard_clear()
            win.clipboard_append(result)
            win.update()
            len_var.set(f"총 {length}자리  ✔ 클립보드에 복사됨! (수정 후 다시 Ctrl+C 가능)")
        else:
            len_var.set("")

    bf2 = tk.Frame(win, bg=BG)
    bf2.pack(pady=14)

    def mkbtn(p, txt, cmd, color=BTN_BG, fg=FG, w=10):
        tk.Button(p, text=txt, command=cmd,
                  bg=color, fg=fg, font=FONT_B,
                  relief="flat", cursor="hand2", width=w, pady=7,
                  activebackground=BTN_HOV, activeforeground=FG
                  ).pack(side="left", padx=5)

    def do_save():
        _sync()
        for i, seg in enumerate(tmp_segs):
            try:
                n = max(0, int(cnt_vars[i].get() if i < len(cnt_vars) else seg["count"]))
            except ValueError:
                messagebox.showerror("입력 오류",
                    f"'{seg['type']}' 글자수는 숫자로 입력하세요.", parent=win)
                return
            tmp_segs[i]["count"] = n

        tc_str = total_count_var.get().strip()
        if tc_str and not tc_str.isdigit():
            messagebox.showerror("입력 오류", "총 글자수는 숫자 또는 빈 칸으로 입력하세요.", parent=win)
            return

        settings["segments"]    = json.loads(json.dumps(tmp_segs))
        settings["total_count"] = tc_str
        save_settings(settings)
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다!", parent=win)
        win.destroy()

    def do_reset():
        global settings
        keep_picker_geo = settings.get("picker_geometry", "380x500")
        keep_win_geo    = win.geometry()

        settings = json.loads(json.dumps(DEFAULT_SETTINGS))
        settings["picker_geometry"] = keep_picker_geo
        save_settings(settings)

        win.destroy()
        open_options()

        def _restore_pos():
            global option_window
            if option_window and option_window.winfo_exists():
                try:
                    pos = "+" + "+".join(keep_win_geo.split("+")[1:])
                    cur_size = option_window.geometry().split("+")[0]
                    option_window.geometry(cur_size + pos)
                except Exception:
                    pass
        root.after(50, _restore_pos)

    mkbtn(bf2, "💾 저장",     do_save,    color=ACCENT,  w=10)
    mkbtn(bf2, "👁 미리보기", do_preview,                w=10)
    mkbtn(bf2, "↺ 초기화",   do_reset,   color=DANGER,  w=8)
    mkbtn(bf2, "✕ 닫기",     win.destroy,               w=6)

    def seg_summary(s):
        if s["type"] == "특수문자":
            sc_n = len(settings.get("special_chars", list(ALL_SPECIAL_CHARS)))
            return f"특수문자 {s['count']}자 ({sc_n}종)"
        return f"{s['type']} {s['count']}자"

    summary = " + ".join(
        seg_summary(s) for s in settings["segments"] if s["enabled"]
    ) or "선택 없음"
    tk.Label(win, text=f"현재 적용 중: {summary}",
             font=FONT_XS, bg=BG, fg=FG2).pack(pady=(0,10))

# ════════════════════════════════════════════════════════════════════
# ── 트레이 메뉴 콜백 함수들 ────────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
def tray_activate(icon, item):
    root.after(0, activate)

def tray_options(icon, item):
    root.after(0, open_options)

def tray_exit(icon, item):
    root.after(0, do_exit)

# ════════════════════════════════════════════════════════════════════
# ── 트레이 아이콘 및 메뉴 생성 ────────────────────────────────────
# ════════════════════════════════════════════════════════════════════
tray = pystray.Icon(
    name="RandomTyper",
    icon=make_tray_image(False),
    title="✨ 랜덤입력기 — 우클릭: 옵션",
    menu=pystray.Menu(
        pystray.MenuItem(
            lambda text: "⏸ 비활성화" if is_active else "▶ 활성화",
            tray_activate,
        ),
        pystray.MenuItem("🛠 옵션 설정", tray_options),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("❌ 종료", tray_exit),
    ),
)

tray_thread = threading.Thread(target=tray.run, daemon=True)
tray_thread.start()

# ════════════════════════════════════════════════════════════════════
# ── 시작 안내 출력 및 메인루프 시작 ───────────────────────────────
# ════════════════════════════════════════════════════════════════════
print("=" * 55)
print("  ✨ 랜덤 문자열 자동 입력기 v3")
print("=" * 55)
print("  [작업표시줄] 클릭→활성화  /  우클릭→창닫기=종료")
print("  [트레이 아이콘] 우클릭→옵션/활성화/종료")
print("  5종류: 숫자/영어대문자/영어소문자/한글/특수문자")
print("  ★ 입력 완료 후 자동 종료됩니다.")
print(f"  spurious FocusIn 차단: 처음 {_SPURIOUS_IGNORE_COUNT}회")
print("=" * 55)

root.mainloop()

##마지막에할일
    ## dist 폴더 내에 실행파일 exe 만들기 (cd 어쩌구....폴더 경로 <<-py파일있는 폴더로 가서~), ico 파일도 py랑 같은 폴더에 넣고
    ##     python -m PyInstaller --onefile --windowed --name Autofill --icon="Autofill.ico" --add-data "Autofill.ico;." Autofill.py