import tkinter as tk
from tkinter import ttk
import sys
import os

# 현재 디렉토리의 부모 디렉토리를 path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from src.process_manager import ProcessManager
from src.utils.scanner import ImageScanner
import time
from tkinter import messagebox
import threading

class ProcessMonitorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("프로세스 모니터")
        self.root.geometry("1000x400")

        # 이미지 검사 관련 변수 초기화
        if getattr(sys, 'frozen', False):
            # PyInstaller로 패키징된 경우
            base_path = sys._MEIPASS
        else:
            # 일반 Python 스크립트로 실행된 경우
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        self.images_folder = os.path.join(base_path, "images")
        print(f"이미지 폴더 경로: {self.images_folder}")  # 디버깅용
        
        self.is_monitoring = False
        self.monitor_thread = None
        self.image_scanner = ImageScanner()
        self.selected_processes = set()

        # 트리뷰 생성 (체크박스 열 추가)
        self.tree = ttk.Treeview(root, columns=('체크', 'PID', '이름', '창 제목', 'CPU', '메모리'), show='headings')
        
        # 컬럼 설정
        self.tree.heading('체크', text='선택')
        self.tree.heading('PID', text='PID')
        self.tree.heading('이름', text='프로세스 이름')
        self.tree.heading('창 제목', text='창 제목')
        self.tree.heading('CPU', text='CPU 사용률')
        self.tree.heading('메모리', text='메모리 사용률')
        
        # 컬럼 너비 설정
        self.tree.column('체크', width=50)
        self.tree.column('PID', width=70)
        self.tree.column('이름', width=150)
        self.tree.column('창 제목', width=150)
        self.tree.column('CPU', width=100)
        self.tree.column('메모리', width=100)
        
        # 체크박스 이벤트 바인딩
        self.tree.bind('<ButtonRelease-1>', self.handle_click)
        
        # 스크롤바 추가
        scrollbar = ttk.Scrollbar(root, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 버튼 프레임 생성
        button_frame = ttk.Frame(root)
        
        # 선택된 프로세스 보기 버튼만 추가
        show_selected_button = ttk.Button(button_frame, text="선택된 프로세스 보기", 
                                        command=self.show_selected_processes)
        show_selected_button.pack(side='left', padx=5)
        
        # 위젯 배치
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        button_frame.pack(side='bottom', pady=10)
        
        # 초기 프로세스 목록 로드
        self.update_process_list()
        
        # 3초마다 자동 새로고침
        self.root.after(3000, self.auto_refresh)

        # 버튼 프레임에 모니터링 컨롤 추가
        self.status_label = ttk.Label(button_frame, text="모니터링 중지됨")
        self.status_label.pack(side='left', padx=5)
        
        self.monitor_button = ttk.Button(button_frame, text="모니터링 시작", 
                                       command=self.toggle_monitoring)
        self.monitor_button.pack(side='left', padx=5)

    def update_process_list(self):
        # 기존 항목 삭제
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 새로운 프로세스 목록 가져오기
        processes = ProcessManager.get_process_list()
        
        # 트리뷰에 프로세스 정보 추가
        for proc in processes:
            pid = proc['pid']
            # 체크박스 상태 설정
            check = "✓" if pid in self.selected_processes else " "
            self.tree.insert('', 'end', values=(
                check,
                pid,
                proc['name'],
                proc['window_title'],
                proc['cpu'],
                proc['memory'],
            ))

    def handle_click(self, event):
        # 클릭한 위치의 아이템과 컬럼 확인
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            
            # 체크박스 컬럼을 클릭했을 때만 처리
            if column == '#1' and item:
                values = self.tree.item(item)['values']
                if values:
                    pid = values[1]  # PID는 두 번째 컬럼
                    
                    # 선택 상태 토글
                    if pid in self.selected_processes:
                        self.selected_processes.remove(pid)
                    else:
                        self.selected_processes.add(pid)
                    
                    # 화면 갱신
                    self.update_process_list()

    def show_selected_processes(self):
        selected = "\n".join([f"PID: {pid}" for pid in self.selected_processes])
        if selected:
            tk.messagebox.showinfo("선택된 프로세스", f"선택된 프로세스:\n{selected}")
        else:
            tk.messagebox.showinfo("선택된 프로세스", "선택된 프로세스가 없습니다.")

    def auto_refresh(self):
        self.update_process_list()
        self.root.after(3000, self.auto_refresh)

    def toggle_monitoring(self):
        if not self.is_monitoring:
            if self.selected_processes:
                self.start_monitoring()
                self.status_label.config(text="모니터링 중...")
                self.monitor_button.config(text="모니터링 중지")
            else:
                messagebox.showwarning("경고", "프로세스를 선택해주세요.")
        else:
            self.stop_monitoring()
            self.status_label.config(text="모니터링 중지됨")
            self.monitor_button.config(text="모니터링 시작")

    def start_monitoring(self):
        if not self.is_monitoring:
            self.is_monitoring = True
            self.monitor_thread = threading.Thread(target=self.monitor_images, daemon=True)
            self.monitor_thread.start()

    def stop_monitoring(self):
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)

    def monitor_images(self):
        while self.is_monitoring:
            try:
                if not self.selected_processes:
                    print("선택된 프로세스가 없습니다.")
                    time.sleep(1)
                    continue

                if os.path.exists(self.images_folder):
                    image_files = [f for f in os.listdir(self.images_folder) 
                                 if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                    
                    if not image_files:
                        print("images 폴더에 이미지 파일이 없습니다.")
                        time.sleep(1)
                        continue

                    for filename in image_files:
                        if not self.is_monitoring:
                            break
                            
                        image_path = os.path.join(self.images_folder, filename)
                        try:
                            for pid in self.selected_processes:
                                process_info = ProcessManager.get_process_info(pid)
                                if process_info and 'window_title' in process_info:
                                    window_title = process_info['window_title']
                                    if window_title != "Unknown":
                                        print(f"검사할 창: {window_title}, PID: {pid}")
                                        
                                        results = self.image_scanner.find_center(image_path, window_title=window_title, confidence=0.8)
                                        if results:
                                            print(f"[{time.strftime('%H:%M:%S')}] {window_title}의 창에서 이미지 {filename} 발견!")
                                            ProcessManager.kill_process_by_name(process_info['name'])
                                            print(f"{window_title} 프로세스를 종료했습니다.")
                        except Exception as e:
                            print(f"이미지 {filename} 검사 중 오류 발생: {str(e)}")
                else:
                    print(f"이미지 폴더를 찾을 수 없습니다: {self.images_folder}")
            except Exception as e:
                print(f"모니터링 중 오류 발생: {str(e)}")
            
            time.sleep(1)

def main():
    root = tk.Tk()
    app = ProcessMonitorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
