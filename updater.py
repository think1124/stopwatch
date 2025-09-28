# updater.py
import sys
import os
import time
import requests
import subprocess
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    script = os.path.abspath(sys.argv[0])
    params = ' '.join([f'"{p}"' for p in sys.argv[1:]])
    try:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
    except Exception as e:
        print(f"관리자 권한으로 재실행 실패: {e}")
        time.sleep(5)

def main():
    if len(sys.argv) < 3:
        print("오류: 인수가 부족합니다.")
        time.sleep(5)
        return

    main_program_name = sys.argv[1] # 예: GO.exe
    download_url = sys.argv[2]
    
    print(f"'{main_program_name}' 업데이트를 시작합니다...")
    print(f"다운로드 URL: {download_url}")

    # 1. 메인 프로그램이 완전히 종료될 때까지 잠시 대기
    time.sleep(2)

    # 2. 새 파일 다운로드
    new_file_name = f"{main_program_name}.new"
    try:
        print("새 버전 다운로드 중...")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(new_file_name, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print("다운로드 완료.")
    except Exception as e:
        print(f"다운로드 실패: {e}")
        # 실패 시, 기존 프로그램 재실행
        if os.path.exists(main_program_name):
            subprocess.Popen([main_program_name])
        time.sleep(5)
        return

    # 3. 기존 파일 삭제 시도 (최대 5초)
    for i in range(5):
        try:
            if os.path.exists(main_program_name):
                os.remove(main_program_name)
            print("기존 파일 삭제 성공.")
            break
        except PermissionError:
            print(f"기존 파일 삭제 실패 (권한 문제). {i+1}초 후 재시도...")
            time.sleep(1)
        except Exception as e:
            print(f"기존 파일 삭제 중 오류: {e}")
            time.sleep(5)
            return
    else:
        print("기존 파일을 삭제할 수 없어 업데이트를 중단합니다.")
        os.remove(new_file_name) # 다운로드한 새 파일 삭제
        if os.path.exists(main_program_name):
            subprocess.Popen([main_program_name])
        return

    # 4. 새 파일을 원래 이름으로 변경
    try:
        os.rename(new_file_name, main_program_name)
        print("파일 교체 완료.")
    except Exception as e:
        print(f"파일 이름 변경 실패: {e}")
        time.sleep(5)
        return

    # 5. 업데이트된 프로그램 재실행
    print("업데이트된 프로그램을 시작합니다...")
    subprocess.Popen([main_program_name])

    # (업데이터 자신은 조용히 종료됨)

if __name__ == "__main__":
    if not is_admin():
        print("업데이트를 위해 관리자 권한이 필요합니다. 재실행합니다...")
        run_as_admin()
    else:
        main()
