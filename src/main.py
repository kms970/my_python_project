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
        self.root.geometry("800x400")

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

        # 메인 프레임 생성
        main_frame = ttk.Frame(root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # 왼쪽 프레임 (프로세스 목록) - 전체 너비의 약 70%
        left_frame = ttk.Frame(main_frame, width=550)
        left_frame.pack(side='left', fill='both', expand=True)
        left_frame.pack_propagate(False)  # 프레임 크기 고정

        # 오른쪽 프레임 (선택된 프로세스) - 전체 너비의 약 30%
        right_frame = ttk.Frame(main_frame, width=200)
        right_frame.pack(side='left', fill='both', padx=(10, 10))
        right_frame.pack_propagate(False)  # 프레임 크기 고정

        # 선택된 프로세스 표시 레이블
        ttk.Label(right_frame, text="선택된 프로세스", font=('Arial', 10, 'bold')).pack(pady=5)
        
        # 리스트박스와 스크롤바를 담을 프레임
        listbox_frame = ttk.Frame(right_frame)
        listbox_frame.pack(fill='both', expand=True, padx=5, pady=(0, 10))
        
        # 선택된 프로세스 리스트박스
        self.selected_listbox = tk.Listbox(
            listbox_frame, 
            width=35, 
            height=15,
            borderwidth=1,
            relief="solid"
        )
        self.selected_listbox.pack(side='left', fill='both', expand=True)

        # 스크롤바 (리스트박스 안쪽에 배치)
        selected_scrollbar = ttk.Scrollbar(self.selected_listbox, orient='vertical', 
                                         command=self.selected_listbox.yview)
        selected_scrollbar.pack(side='right', fill='y')
        self.selected_listbox.configure(yscrollcommand=selected_scrollbar.set)

        # 트리뷰 생성 (왼쪽 프레임에 배치)
        self.tree = ttk.Treeview(left_frame, columns=('체크', 'PID', '이름', '창 제목'), 
                                show='headings', height=15)
        
        # 컬럼 설정
        self.tree.heading('체크', text='선택')
        self.tree.heading('PID', text='PID')
        self.tree.heading('이름', text='프로세스 이름')
        self.tree.heading('창 제목', text='창 제목')
        
        # 컬럼 너비 설정
        self.tree.column('체크', width=40, anchor='center')
        self.tree.column('PID', width=60, anchor='center')
        self.tree.column('이름', width=150)
        self.tree.column('창 제목', width=300)
        
        # 체크박스 이벤트 바인딩
        self.tree.bind('<ButtonRelease-1>', self.handle_click)
        
        # 스크롤바 추가
        scrollbar = ttk.Scrollbar(left_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 버튼 프레임을 왼쪽 프레임 하단에 배치
        button_frame = ttk.Frame(left_frame)
        button_frame.pack(side='bottom', pady=10)

        # 상태 표시 레이블 (스타일 적용)
        self.status_label = tk.Label(
            button_frame, 
            text="모니터링 중지됨",
            font=('Arial', 9, 'bold'),
            fg='red',  # 텍스트 색상
            bg='#f0f0f0',  # 배경 색상
            padx=10,
            pady=5,
            relief='groove',  # 테두리 스타일
            borderwidth=1
        )
        self.status_label.pack(side='left', padx=10)
        
        # 모니터링 버튼 (스타일 적용)
        self.monitor_button = tk.Button(
            button_frame, 
            text="모니터링 시작",
            font=('Arial', 9, 'bold'),
            fg='white',
            bg='#4CAF50',  # 초록색 배경
            activebackground='#45a049',  # 클릭 시 색상
            padx=15,
            pady=5,
            relief='raised',
            command=self.toggle_monitoring
        )
        self.monitor_button.pack(side='left', padx=10)

        # 트리뷰 패키지 추가
        self.tree.pack(side='left', fill='x')
        scrollbar.pack(side='right', fill='y')

        # 초기 프로세스 목록 로드
        self.update_process_list()
        
        # 3초마다 자동 새로고침
        self.root.after(3000, self.auto_refresh)

    def update_process_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        processes = ProcessManager.get_process_list()
        
        # 최대 8개까지만 표시
        for proc in processes[:8]:
            pid = proc['pid']
            check = "✓" if pid in self.selected_processes else " "
            self.tree.insert('', 'end', values=(
                check,
                pid,
                proc['name'],
                proc['window_title']
            ))
        
        # 선택된 프로세스 목록 업데이트
        self.update_selected_listbox()

    def handle_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            
            if column == '#1' and item:
                values = self.tree.item(item)['values']
                if values:
                    pid = values[1]
                    name = values[2]
                    window_title = values[3]
                    
                    if pid in self.selected_processes:
                        self.selected_processes.remove(pid)
                    else:
                        self.selected_processes.add(pid)
                    
                    self.update_process_list()
                    self.update_selected_listbox()  # 선택된 프로세스 목록 업데이트

    def update_selected_listbox(self):
        self.selected_listbox.delete(0, tk.END)
        for pid in self.selected_processes:
            process_info = ProcessManager.get_process_info(pid)
            if process_info:
                self.selected_listbox.insert(tk.END, 
                    f"PID: {pid} - {process_info['name']}")

    def auto_refresh(self):
        self.update_process_list()
        self.root.after(3000, self.auto_refresh)

    def toggle_monitoring(self):
        if not self.is_monitoring:
            if self.selected_processes:
                self.start_monitoring()
                self.status_label.config(
                    text="모니터링 중...",
                    fg='white',
                    bg='#2196F3'  # 파란색 배경
                )
                self.monitor_button.config(
                    text="모니터링 중지",
                    bg='#f44336',  # 빨간색 배경
                    activebackground='#da190b'
                )
            else:
                messagebox.showwarning("경고", "프로세스를 선택해주세요.")
        else:
            self.stop_monitoring()
            self.status_label.config(
                text="모니터링 중지됨",
                fg='red',
                bg='#f0f0f0'
            )
            self.monitor_button.config(
                text="모니터링 시작",
                bg='#4CAF50',
                activebackground='#45a049'
            )

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
                # 존재하지 않는 프로세스 필터링
                active_processes = set()
                for pid in self.selected_processes:
                    process_info = ProcessManager.get_process_info(pid)
                    if process_info:  # 프로세스가 존재하는 경우에만 추가
                        active_processes.add(pid)
                    else:
                        print(f"PID {pid}의 프로세스가 이미 종료되었습니다.")
                
                # 활성 프로세스 목록 업데이트
                self.selected_processes = active_processes
                
                # GUI 업데이트
                self.root.after(0, self.update_selected_listbox)
                
                if not self.selected_processes:
                    print("모니터링할 프로세스가 없습니다.")
                    self.is_monitoring = False
                    self.root.after(0, self.clear_and_stop_monitoring)
                    break
                
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
                            for pid in list(self.selected_processes):  # list로 변환하여 반복 중 수정 가능하게 함
                                process_info = ProcessManager.get_process_info(pid)
                                if process_info and 'window_title' in process_info:
                                    window_title = process_info['window_title']
                                    if window_title != "Unknown":
                                        print(f"검사할 창: {window_title}, PID: {pid}")
                                        
                                        results = self.image_scanner.find_center(
                                            image_path, 
                                            window_title=window_title, 
                                            confidence=0.8
                                        )
                                        
                                        if results and len(results) > 0:
                                            window_title, match_point = results[0]
                                            print(f"이미지 매칭 발견: {window_title}")
                                            print(f"[{time.strftime('%H:%M:%S')}] {window_title}의 창에서 이미지 {filename} 발견!")
                                            ProcessManager.kill_process(pid)
                                            print(f"PID {pid}의 {window_title} 프로세스를 종료했습니다.")
                                            self.selected_processes.remove(pid)  # 종료된 프로세스 제거
                                            self.root.after(0, self.update_selected_listbox)  # GUI 업데이트
                        except Exception as e:
                            print(f"이미지 {filename} 검사 중 오류 발생: {str(e)}")
                else:
                    print(f"이미지 폴더를 찾을 수 없습니다: {self.images_folder}")
            except Exception as e:
                print(f"모니터링 중 오류 발생: {str(e)}")
            
            time.sleep(1)

    def stop_monitoring_gui(self):
        """GUI 스레드에서 모니터링을 중지하는 메서드"""
        self.stop_monitoring()
        self.status_label.config(
            text="모니터링 중지됨",
            fg='red',
            bg='#f0f0f0'
        )
        self.monitor_button.config(
            text="모니터링 시작",
            bg='#4CAF50',
            activebackground='#45a049'
        )

    def clear_and_stop_monitoring(self):
        """프로세스 목록을 초기화하고 모니터링을 중지하는 메서드"""
        self.is_monitoring = False  # 모니터링 상태를 확실히 False로 설정
        self.selected_processes.clear()  # 프로세스 목록 초기화
        self.update_selected_listbox()   # 리스트박스 업데이트
        self.update_process_list()       # 프로세스 목록 업데이트
        
        # GUI 상태 업데이트
        self.status_label.config(
            text="모니터링 중지됨",
            fg='red',
            bg='#f0f0f0'
        )
        self.monitor_button.config(
            text="모니터링 시작",
            bg='#4CAF50',
            activebackground='#45a049'
        )

def main():
    root = tk.Tk()
    app = ProcessMonitorGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
