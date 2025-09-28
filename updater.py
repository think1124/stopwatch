# updater.py
import sys
import os
import time
import requests
import subprocess
import psutil

def kill_process(process_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'].lower() == process_name.lower():
            try:
                proc.kill()
                print(f"'{process_name}' 프로세스를 종료했습니다.")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

if __name__ == "__main__":
    # 메인 프로그램으로부터 인자(argument)를 전달받습니다.
    main_program_name = sys.argv[1] # 예: "GO.exe"
    download_url = sys.argv[2]      # 새 버전 다운로드 URL
    new_version = sys.argv[3]       # 예: "1.1"

    print("업데이트를 시작합니다...")
    print(f"기존 프로그램: {main_program_name}")
    
    # 1. 기존 프로그램이 완전히 종료될 때까지 잠시 기다립니다.
    time.sleep(2)
    kill_process(main_program_name)
    time.sleep(1)

    try:
        # 2. 새 버전 파일을 다운로드합니다.
        print(f"새 버전({new_version}) 다운로드 중...: {download_url}")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()

        temp_file_name = "GO_new.exe"
        with open(temp_file_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("다운로드 완료.")

        # 3. 기존 파일을 새 파일로 덮어씁니다.
        os.replace(temp_file_name, main_program_name)
        print("파일 교체 완료.")

        # 4. 업데이트된 새 버전의 프로그램을 다시 실행합니다.
        print("업데이트된 프로그램을 실행합니다.")
        subprocess.Popen([main_program_name])

    except Exception as e:
        print(f"업데이트 중 오류가 발생했습니다: {e}")
        input("오류가 발생했습니다. Enter 키를 눌러 종료합니다.")
