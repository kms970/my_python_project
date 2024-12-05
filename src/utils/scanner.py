import pyautogui
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32process
from ctypes import windll
import os

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
        # 파일명 추출
        filename = os.path.basename(image_path)
        print(f"\n현재 검사 중인 이미지: {filename}")

        # LDPlayer 창 목록 가져오기
        ldplayer_windows = self.find_ldplayer_windows()
        if not ldplayer_windows:
            print("실행 중인 LDPlayer 창을 찾을 수 없습니다.")
            return None

        if window_title:
            ldplayer_windows = [(hwnd, title) for hwnd, title in ldplayer_windows if title == window_title]
            if not ldplayer_windows:
                print(f"지정된 창을 찾을 수 없습니다: {window_title}")
                return None

        # 템플릿 이미지 로드 및 전처리
        template = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            print(f"템플릿 이미지를 불러올 수 없습니다: {filename}")
            return None
        
        print(f"템플릿 이미지 크기 ({filename}): {template.shape}")
        
        results = []
        for hwnd, title in ldplayer_windows:
            screenshot = self.capture_window(hwnd)
            if screenshot is None:
                print(f"{title}: 스크린샷을 캡처할 수 없습니다. (검사 이미지: {filename})")
                continue
            
            # 이미지 채널 수 확인 및 처리
            if len(template.shape) == 3 and template.shape[2] == 4:  # 알파 채널이 있는 경우
                template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
            
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 4:  # 알파 채널이 있는 경우
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # 그레이스케일로 변환
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            print(f"{title} 스크린샷 크기 (검사 이미지: {filename}): {screenshot_gray.shape}")
            
            # 디버깅을 위한 이미지 저장
            cv2.imwrite(f'debug_screenshot_{title}.png', screenshot_gray)
            cv2.imwrite(f'debug_template_{title}.png', template_gray)

            # 템플릿 매칭
            result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            print(f"{title} - 매칭 신뢰도 ({filename}): {max_val:.3f}")

            if max_val >= confidence:
                center_x = max_loc[0] + template_gray.shape[1] // 2
                center_y = max_loc[1] + template_gray.shape[0] // 2
                results.append((title, (center_x, center_y)))
                print(f"{title}: 매칭 성공 - {filename} 발견! 중심점 ({center_x}, {center_y})")
                
                # 디버깅을 위한 매칭 결과 시각화
                debug_img = screenshot_gray.copy()
                cv2.rectangle(debug_img, max_loc, 
                             (max_loc[0] + template_gray.shape[1], max_loc[1] + template_gray.shape[0]), 
                             255, 2)
                cv2.imwrite(f'debug_result_{title}.png', debug_img)

        return results
