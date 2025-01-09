import os
import sys
import shutil
import PyInstaller.__main__
from pathlib import Path

def clean_dirs():
    """清理构建目录"""
    dirs_to_clean = ['dist', 'build']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"清理 {dir_name} 目录...")
            shutil.rmtree(dir_name)
    
    # 清理spec文件
    spec_file = 'WebScraper.spec'
    if os.path.exists(spec_file):
        print(f"删除 {spec_file} 文件...")
        os.remove(spec_file)

def format_data_path(src, dst):
    """格式化数据文件路径"""
    # 在Windows上使用分号，在其他平台使用冒号
    separator = ';' if sys.platform.startswith('win') else ':'
    return f"{src}{separator}{dst}"

def build_exe():
    """使用PyInstaller打包项目为EXE文件"""
    # 清理旧的构建文件
    clean_dirs()
    
    print("配置打包参数...")
    
    # 定义数据文件
    datas = [
        ('images/*.png', 'images'),
        ('requirements.txt', '.'),
        ('README.md', '.')
    ]
    
    # 格式化数据文件路径
    datas_args = []
    for src, dst in datas:
        datas_args.append('--add-data')
        datas_args.append(format_data_path(src, dst))
    
    # 定义隐藏导入
    hidden_imports = [
        'PyQt5',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngine',
        'PyQt5.QtWebEngineCore',
        'pandas'
    ]
    
    hidden_imports_args = []
    for imp in hidden_imports:
        hidden_imports_args.extend(['--hidden-import', imp])
    
    # PyInstaller参数
    args = [
        'main.py',                    # 主程序文件
        '--name=WebScraper',          # 生成的EXE名称
        '--windowed',                 # 使用GUI模式
        '--onefile',                  # 打包成单个EXE文件
        '--clean',                    # 清理临时文件
        '--icon=images/icon_app.png', # 设置程序图标
        '--noconfirm',                # 不确认覆盖
        '--noconsole',                # 禁用控制台输出
        '--log-level=INFO',           # 设置日志级别
        # 添加QtWebEngine相关文件
        '--collect-data=PyQt5.QtWebEngine',
    ]
    
    # 合并所有参数
    args.extend(datas_args)
    args.extend(hidden_imports_args)
    
    print("开始打包...")
    try:
        PyInstaller.__main__.run(args)
        print("\n打包成功！")
        print(f"可执行文件位置: {os.path.abspath('dist/WebScraper.exe')}")
    except Exception as e:
        print(f"\n打包失败: {str(e)}")
        sys.exit(1)

def check_requirements():
    """检查并安装必要的依赖"""
    required_packages = {
        'pyinstaller': 'PyInstaller',
        'pyqt5': 'PyQt5',
        'pandas': 'pandas'
    }
    
    for package, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"✓ {package} 已安装")
        except ImportError:
            print(f"正在安装 {package}...")
            os.system(f'{sys.executable} -m pip install {package}')

if __name__ == '__main__':
    print("=== 网页数据抓取工具打包程序 ===\n")
    
    # 检查Python版本
    if sys.version_info < (3, 6):
        print("错误: 需要Python 3.6或更高版本")
        sys.exit(1)
    
    # 检查工作目录
    if not all(os.path.exists(f) for f in ['main.py', 'element_selector.py', 'requirements.txt']):
        print("错误: 请在项目根目录下运行此脚本")
        sys.exit(1)
    
    # 检查并安装依赖
    print("检查依赖...")
    check_requirements()
    
    # 开始打包
    build_exe() 