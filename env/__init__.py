import sys
import os
import importlib
from enum import Enum


class run_type_enum(Enum):
    DISTRIBUTION = "bin"  # 正式发布模式
    RELEASE = "Release"  # release开发模式
    DEBUG = "Debug"  # debug开发模式

#此值按实际测试场景更改
RUN_TYPE = run_type_enum.DISTRIBUTION

global_path_dic= {}

def env_validation():
    print("=" * 70)
    print("[环境初始化]", __file__)
    print("=" * 70)

    phase = os.environ.get('UV_DEVELOP')
    setup_path = os.environ.get('SolarRT_Path')
    print("phase", phase)
    print("setup_path:", setup_path)
    # 外部python解释器运行
    if phase is None:
        print("===None phase，Running in external Python ===")
        print("RUN_TYPE", RUN_TYPE)
        os.environ['UV_RTE_MODE'] = 'SRE'
        os.environ['UV_DEVELOP'] = RUN_TYPE.name

        if RUN_TYPE == run_type_enum.DISTRIBUTION:
            setup_path_normalized = setup_path.rstrip('\\/')
            solar_base_path = os.path.dirname(setup_path_normalized)
            global_path_dic["solar_base_path"] =solar_base_path
        else:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            current_dir = os.path.dirname(os.path.dirname(current_dir))
            solar_base_path = os.path.join(current_dir, "x64")
            global_path_dic["solar_base_path"] =solar_base_path
        print("remendy current_dir:", solar_base_path)

        script_path = os.path.join(solar_base_path, 'script', 'pysolar')
        dll_path = os.path.join(solar_base_path, RUN_TYPE.value)
        print("script_path:", script_path)
        print("dll_path:", dll_path)

        if not os.path.exists(script_path):
            print(f"[错误] 找不到 API 库: {script_path}")
            exit(1)

        if not os.path.exists(dll_path):
            print(f"[错误] 找不到 DLL 库: {dll_path}")
            exit(1)

        if script_path not in sys.path:
            sys.path.insert(0, script_path)

        current_path = os.environ.get('PATH', '')
        if dll_path not in current_path:
            os.environ['PATH'] = dll_path + os.pathsep + current_path

        ts_path = os.path.join(solar_base_path, 'ts')
        if ts_path not in sys.path:
            sys.path.append(ts_path)
            print(f"[TS库]     {ts_path}")

        print(f"[Python库] {script_path}")
        print(f"[DLL库]    {dll_path}")

        try:
            importlib.import_module("_sl.runtime.sl")
            print("初始化文件加载成功")
        except Exception as e:
            print(f"初始化文件加载失败: {e}")

    else:
        print("===With phase，Running on internal Python===")
        print("RUN_TYPE", RUN_TYPE)
        print(f"UV_DEVELOP={phase}")

        if RUN_TYPE == run_type_enum.DISTRIBUTION:
            setup_path_normalized = setup_path.rstrip('\\/')
            solar_base_path = os.path.dirname(setup_path_normalized)
            global_path_dic["solar_base_path"] =solar_base_path
            pysolar_path=os.path.join(solar_base_path, 'script', 'pysolar')
        else:
            current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            tsengine_root = os.path.dirname(os.path.dirname(current_dir))
            solar_base_path=os.path.join(tsengine_root, 'x64')
            global_path_dic["solar_base_path"] =solar_base_path
            pysolar_path = os.path.join(solar_base_path, 'script', 'pysolar')

        if os.path.exists(pysolar_path) and pysolar_path not in sys.path:
            sys.path.insert(0, pysolar_path)
            print(f"[API库] {pysolar_path}")

        ts_path = os.path.join(solar_base_path, 'ts')
        if ts_path not in sys.path:
            sys.path.append(ts_path)
            print(f"[TS库] {ts_path}")

        try:
            importlib.import_module("_sl.runtime.sl")
        except Exception as e:
            print(f"初始化文件加载失败: {e}")
    print("=" * 70)
    print("[环境初始化] 完成")
    print("=" * 70)


env_validation()
