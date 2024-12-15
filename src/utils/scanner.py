import pyautogui
import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import win32process
from ctypes import windll
import os
import time
from datetime import datetime

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

    def find_center(self, image_path, window_title=None, confidence=0.8, suppress_logging=False):
        # 파일명 추출
        filename = os.path.basename(image_path)
        if not suppress_logging:
            print(f"\n현재 검사 중인 이미지: {filename}")

        # LDPlayer 창 목록 가져오기
        ldplayer_windows = self.find_ldplayer_windows()
        if not ldplayer_windows:
            if not suppress_logging:
                print("실행 중인 LDPlayer 창을 찾을 수 없습니다.")
            return None

        # window_title이 지정된 경우 해당 창만 처리
        if window_title:
            print(f"지정된 창 검색: {window_title}")
            ldplayer_windows = [(hwnd, title) for hwnd, title in ldplayer_windows if title == window_title]
            if not ldplayer_windows:
                if not suppress_logging:
                    print(f"지정된 창을 찾을 수 없습니다: {window_title}")
                return None

        # 템플릿 이미지 로드 및 전처리
        template = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            if not suppress_logging:
                print(f"템플릿 이미지를 불러올 수 없습니다: {filename}")
            return None
        
        if not suppress_logging:
            print(f"템플릿 이미지 크기 ({filename}): {template.shape}")
        
        results = []
        for hwnd, title in ldplayer_windows:
            screenshot = self.capture_window(hwnd)
            if screenshot is None:
                if not suppress_logging:
                    print(f"{title}: 스크린샷을 캡처할 수 없습니다.")
                continue
            
            # 이미지 크기 비교
            if (template.shape[0] > screenshot.shape[0] or 
                template.shape[1] > screenshot.shape[1]):
                if not suppress_logging:
                    print(f"{title}: 템플릿 이미지가 스크린샷보다 큽니다. 건너뜁니다.")
                    print(f"템플릿 크기: {template.shape}, 스크린샷 크기: {screenshot.shape}")
                continue
            
            # 이미지 채널 수 확인 및 처리
            if len(template.shape) == 3 and template.shape[2] == 4:
                template = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
            
            if len(screenshot.shape) == 3 and screenshot.shape[2] == 4:
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2BGR)
            
            # 그레이스케일로 변환
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            screenshot_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            
            if not suppress_logging:
                print(f"{title} 스크린샷 크기: {screenshot_gray.shape}")
                
                # 디버깅을 위한 이미지 저장
                debug_dir = "debug"
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir)
                cv2.imwrite(os.path.join(debug_dir, f'debug_screenshot_{title}.png'), screenshot_gray)
                cv2.imwrite(os.path.join(debug_dir, f'debug_template_{title}.png'), template_gray)

            # 템플릿 매칭
            result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            if not suppress_logging:
                print(f"{title} - 매칭 신뢰도: {max_val:.3f}")

            if max_val >= confidence:
                center_x = max_loc[0] + template_gray.shape[1] // 2
                center_y = max_loc[1] + template_gray.shape[0] // 2
                results.append((title, (center_x, center_y)))
                if not suppress_logging:
                    print(f"{title}: 매칭 성공 - 중심점 ({center_x}, {center_y})")
                    
                    # 디버깅을 위한 매칭 결과 시각화
                    debug_img = screenshot_gray.copy()
                    cv2.rectangle(debug_img, max_loc, 
                                (max_loc[0] + template_gray.shape[1], max_loc[1] + template_gray.shape[0]), 
                                255, 2)
                    cv2.imwrite(os.path.join(debug_dir, f'debug_result_{title}.png'), debug_img)

        return results

    def click_image(self, image_path, window_title=None, confidence=0.8, color_threshold=30, adb_path=None):
        import subprocess
        import cv2
        import numpy as np
        import time
        from datetime import datetime
        
        if not adb_path:
            print("ADB 경로가 설정되지 않았습니다.")
            return False
        
        results = self.find_center(image_path, window_title, confidence)
        if not results:
            return False

        success = False
        
        # 스크린샷과 실제 해상도 차이
        SCREENSHOT_WIDTH = 994
        SCREENSHOT_HEIGHT = 578
        ACTUAL_WIDTH = 960
        ACTUAL_HEIGHT = 540
        
        # 좌표 오프셋 계산
        offset_x = (SCREENSHOT_WIDTH - ACTUAL_WIDTH) // 2  # 17
        offset_y = (SCREENSHOT_HEIGHT - ACTUAL_HEIGHT) // 2  # 19

        for title, (center_x, center_y) in results:
            try:
                if window_title and title != window_title:
                    continue
                
                try:
                    instance_num = int(title.split('-')[1])
                    adb_port = 5555 + (instance_num * 2)
                    device_address = f"127.0.0.1:{adb_port}"
                    
                    # 좌표 보정
                    adjusted_x = center_x - offset_x
                    adjusted_y = center_y - offset_y
                    
                    print(f"처리 중 - 창: {title}, 인스턴스: {instance_num}, 포트: {adb_port}")
                    print(f"원본 좌표: ({center_x}, {center_y})")
                    print(f"보정된 좌표: ({adjusted_x}, {adjusted_y})")
                except Exception as e:
                    print(f"인덱스 추출 오류 ({title}): {str(e)}")
                    continue
                
                # 원본 이미지의 색상 가져오기
                template = cv2.imread(image_path)
                if template is None:
                    continue
                
                template = cv2.cvtColor(template, cv2.COLOR_BGR2RGB)
                template_center = template[template.shape[0]//2, template.shape[1]//2]
                
                hwnd = win32gui.FindWindow(None, title)
                if not hwnd:
                    continue
                
                screenshot = self.capture_window(hwnd)
                if screenshot is None:
                    continue
                
                # 클릭 위치 표시를 위한 이미지 복사
                display_image = screenshot.copy()
                
                # 빨간 점 그리기 (반경 5픽셀의 원)
                cv2.circle(display_image, (center_x, center_y), 5, (0, 0, 255), -1)
                # 위치 텍스트 표시
                cv2.putText(display_image, f"Click: ({center_x}, {center_y})", 
                           (center_x + 10, center_y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
                # 현재 시간을 포함한 파일명 생성
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"click_position_{title}_{timestamp}.png"
                
                # debug 폴더가 없으면 생성
                debug_dir = "debug"
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir)
                
                # 이미지 저장
                cv2.imwrite(os.path.join(debug_dir, filename), display_image)
                print(f"클릭 위치 이미지 저장됨: {filename}")
                
                screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2RGB)
                click_color = screenshot[center_y, center_x]
                color_diff = np.sum(np.abs(template_center - click_color[:3]))
                
                if color_diff <= color_threshold:
                    try:
                        print(f"클릭 시도 - 창: {title}, 주소: {device_address}")
                        
                        # ADB 연결 시도
                        try:
                            connect_result = subprocess.run(
                                [adb_path, "connect", device_address], 
                                capture_output=True, 
                                text=True  # 텍스트 모드로 출력 캡처
                            )
                            if connect_result.returncode != 0:
                                print(f"ADB 연결 명령 실패: {connect_result.stderr}")
                                if connect_result.stdout:
                                    print(f"출력: {connect_result.stdout}")
                        except Exception as e:
                            print(f"ADB 연결 중 오류 발생: {str(e)}")
                            continue
                        
                        # 디바이스 목록 확인
                        try:
                            devices_result = subprocess.run(
                                [adb_path, "devices"], 
                                capture_output=True, 
                                text=True
                            )
                            if devices_result.returncode != 0:
                                print(f"디바이스 목록 확인 실패: {devices_result.stderr}")
                                if devices_result.stdout:
                                    print(f"출력: {devices_result.stdout}")
                            print(f"연결된 디바이스 목록:\n{devices_result.stdout}")
                        except Exception as e:
                            print(f"디바이스 목록 확인 중 오류 발생: {str(e)}")
                            continue
                        
                        if device_address in devices_result.stdout:
                            # 보정된 좌표로 클릭
                            cmd = f"{adb_path} -s {device_address} shell input tap {adjusted_x} {adjusted_y}"
                            print(f"\n실행할 명령어: {cmd}")
                            
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            
                            result = subprocess.run(
                                cmd,
                                shell=True,
                                capture_output=True,
                                text=True,
                            )
                            
                            if result.returncode == 0:
                                print(f"이미지 클릭 성공: {title} ({adjusted_x}, {adjusted_y})")
                                if result.stdout:
                                    print(f"출력: {result.stdout}")
                                success = True
                            else:
                                print(f"클릭 명령 실패: {result.stderr}")
                                if result.stdout:
                                    print(f"출력: {result.stdout}")
                        else:
                            print(f"ADB 연결 실패: {device_address}가 디바이스 목록에 없습니다.")
                            
                    except Exception as e:
                        print(f"클릭 처리 중 오류 발생: {str(e)}")
                else:
                    print(f"색상이 일치하지 않습니다. 차이값: {color_diff}")
                    
            except Exception as e:
                print(f"처리 중 오류 발생: {str(e)}")
                continue
                
        return success