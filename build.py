import PyInstaller.__main__
import os

if __name__ == '__main__':
    # PyInstaller 인자 설정
    args = [
        'main.py',
        '--name', 'Anki Manager',
        '--onefile',
        '--windowed',
        '--noconfirm',
        # 데이터 파일 추가 (필요한 경우)
        # '--add-data', 'path/to/data:data',
    ]

    # macOS 관련 추가 옵션
    if os.uname().sysname == 'Darwin':
        # 아이콘이 있다면 여기에 경로를 추가하세요.
        # args.extend(['--icon', 'path/to/your/icon.icns'])
        pass

    PyInstaller.__main__.run(args)
