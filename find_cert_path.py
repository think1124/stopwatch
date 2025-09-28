# find_cert_path.py
import certifi
import os

# certifi 라이브러리가 사용하는 인증서 파일의 경로를 출력합니다.
cert_path = certifi.where()
print(cert_path)

# PyInstaller의 --add-data 옵션에 맞게 경로를 수정합니다.
# 예: C:\...\venv\Lib\site-packages\certifi\cacert.pem -> certifi;certifi
# (세미콜론은 윈도우 경로 구분자입니다)
cert_dir = os.path.dirname(cert_path)
print(f'--add-data "{cert_dir}{os.pathsep}certifi"')
