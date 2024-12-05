import psutil
from datetime import datetime
import os
import win32gui
import win32process

class ProcessManager:
    @staticmethod
    def get_process_list():
        import psutil
        import win32gui
        import win32process

        def get_window_title(pid):
            def callback(hwnd, titles):
                if win32gui.IsWindowVisible(hwnd):
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid == pid:
                        title = win32gui.GetWindowText(hwnd)
                        if title.startswith('LDPlayer-'):
                            titles.append(title)
                return True

            titles = []
            win32gui.EnumWindows(callback, titles)
            return titles[0] if titles else "Unknown"

        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if 'dnplayer' in pinfo['name'].lower():
                    window_title = get_window_title(pinfo['pid'])
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'].replace('.exe', ''),
                        'window_title': window_title,
                        'cpu': f"{pinfo['cpu_percent']:.1f}%",
                        'memory': f"{pinfo['memory_percent']:.1f}%"
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return processes

    @staticmethod
    def kill_process(pid):
        try:
            os.system(f'taskkill /F /PID {pid}')
            return True
        except Exception as e:
            print(f"프로세스 종료 중 오류 발생: {str(e)}")
            return False

    @staticmethod
    def get_process_info(pid):
        try:
            import psutil
            process = psutil.Process(pid)
            name = process.name().replace('.exe', '')
            
            # 창 제목 가져오기
            def get_window_title(pid):
                def callback(hwnd, titles):
                    if win32gui.IsWindowVisible(hwnd):
                        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                        if found_pid == pid:
                            title = win32gui.GetWindowText(hwnd)
                            if title.startswith('LDPlayer-'):
                                titles.append(title)
                            elif title:  # 디버깅용
                                print(f"Found window for PID {pid}: '{title}'")
                    return True

                titles = []
                win32gui.EnumWindows(callback, titles)
                if not titles:  # 디버깅용
                    print(f"No window titles found for PID {pid}")
                return titles[0] if titles else None

            window_title = get_window_title(pid)
            if not window_title:  # 디버깅용
                print(f"Window title not found for process: {name} (PID: {pid})")
            
            return {
                'name': name,
                'pid': pid,
                'window_title': window_title if window_title else "Unknown"
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            print(f"Error getting process info: {str(e)}")  # 디버깅용
            return None
