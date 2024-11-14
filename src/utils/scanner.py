import pyautogui
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32process
from ctypes import windll

class ImageScanner:
    def __init__(self):
        self.hwnd = None

    def capture_window(self, hwnd):
        # 창 크기 가져오기
        left, top, right, bot = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bot - top

        # 창 DC 가져오기
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()

        # 비트맵 생성
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
        saveDC.SelectObject(saveBitMap)

        # 창 내용 복사
        result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)

        # 이미지를 numpy 배열로 변환
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (height, width, 4)

        # 정리
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)

        return img if result else None

    def find_window_by_pid(self, pid):
        def callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd):
                _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                window_title = win32gui.GetWindowText(hwnd)
                print(f"Found window - PID: {found_pid}, Title: '{window_title}', HWND: {hwnd}")
                if found_pid == pid:
                    hwnds.append(hwnd)
            return True

        hwnds = []
        win32gui.EnumWindows(callback, hwnds)
        return hwnds[0] if hwnds else None

    def find_ldplayer_windows(self):
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title.startswith('LDPlayer-'):
                    windows.append((hwnd, title))
            return True

        windows = []
        win32gui.EnumWindows(callback, windows)
        return sorted(windows, key=lambda x: int(x[1].split('-')[1]))  # LDPlayer-n 숫자 순서로 정렬

    def find_center(self, image_path, window_title=None, confidence=0.8):
        # 기준 해상도 설정
        BASE_WIDTH = 960
        BASE_HEIGHT = 540

        ldplayer_windows = self.find_ldplayer_windows()
        if not ldplayer_windows:
            print("실행 중인 LDPlayer 창을 찾을 수 없습니다.")
            return None

        if window_title:
            ldplayer_windows = [(hwnd, title) for hwnd, title in ldplayer_windows if title == window_title]
            if not ldplayer_windows:
                print(f"지정된 창을 찾을 수 없습니다: {window_title}")
                return None

        template = cv2.imread(image_path)
        if template is None:
            print(f"템플릿 이미지를 불러올 수 없습니다: {image_path}")
            return None
        
        # BGR로 변환하여 알파 채널 제거
        template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
        template_gray = cv2.cvtColor(template, cv2.COLOR_RGB2GRAY)
        print(f"템플릿 이미지 크기: {template_gray.shape}")

        results = []
        for hwnd, title in ldplayer_windows:
            screenshot = self.capture_window(hwnd)
            if screenshot is None:
                print(f"{title}: 스크린샷을 캡처할 수 없습니다.")
                continue
            
            # 스크린샷의 알파 채널 제거
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2RGB)
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_RGB2GRAY)
            print(f"{title} 스크린샷 크기: {screenshot_gray.shape}")

            # 현재 창과 기준 해상도의 비율 계산
            scale = min(
                screenshot_gray.shape[1] / BASE_WIDTH,
                screenshot_gray.shape[0] / BASE_HEIGHT
            )
            
            # 템플릿 이미지 크기 조정
            new_width = int(template_gray.shape[1] * scale)
            new_height = int(template_gray.shape[0] * scale)
            scaled_template = cv2.resize(template_gray, (new_width, new_height), 
                                       interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)

            # 이미지 전처리
            scaled_template = cv2.normalize(scaled_template, None, 0, 255, cv2.NORM_MINMAX)
            screenshot_gray = cv2.normalize(screenshot_gray, None, 0, 255, cv2.NORM_MINMAX)

            print(f"{title} - 스케일: {scale:.3f}, 이미지 이름: {image_path}, 조정된 템플릿 크기: {scaled_template.shape}")

            # 템플릿 매칭 (여러 방법 시도)
            methods = [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED]
            max_val_overall = 0
            best_loc = None
            
            for method in methods:
                result = cv2.matchTemplate(screenshot_gray, scaled_template, method)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                
                if max_val > max_val_overall:
                    max_val_overall = max_val
                    best_loc = max_loc

            print(f"{title} - 매칭 신뢰도: {max_val_overall:.3f}")

            if max_val_overall >= confidence:
                center_x = best_loc[0] + new_width // 2
                center_y = best_loc[1] + new_height // 2
                results.append((title, (center_x, center_y)))
                print(f"{title}: 매칭 성공 - 중심점 ({center_x}, {center_y})")
            else:
                print(f"{title}: 매칭 실패")

        return results
