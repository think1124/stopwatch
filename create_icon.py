# create_icon.py
import base64
from PIL import Image
import io

try:
    from icon_data import icon_base64
except ImportError:
    print("오류: icon_data.py를 찾을 수 없습니다.")
    exit(1)

try:
    icon_data = base64.b64decode(icon_base64)
    image_file = io.BytesIO(icon_data)
    img = Image.open(image_file)
    # 이제 'icon.ico' 라는 영구적인 파일로 저장합니다.
    img.save('icon.ico', format='ICO', sizes=[(256, 256)])
    print("성공: 'icon.ico' 파일이 생성되었습니다.")
    print("이제 이 스크립트는 다시 실행할 필요 없습니다.")
except Exception as e:
    print(f"아이콘 생성 중 오류: {e}")
    exit(1)
