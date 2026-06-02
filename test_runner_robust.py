import os
import sys
import importlib
import traceback
import env           # 环境初始化（路径、DLL、runtime）

from uvtest.framework import run_test_framework, discover_test_groups

def main():
    success = False
    try:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        testcases_dir = os.path.join(project_dir, "testcases_robust")
        sys.path.insert(0, project_dir)
        importlib.import_module("testcases_robust.session_fixture")  # 注册 SessionFixture
        discover_test_groups(testcases_dir)

        # 交互式
        success = run_test_framework()

        # 运行所有测试
        # success = run_test_framework(execution_mode="all")

        # 运行指定测试组
        # success = run_test_framework(
        #     session_mode="run",
        #     execution_mode="groups",
        #     target_groups=["CAN"]
        # )

        # 运行指定测试用例
        # success = run_test_framework(
        #     session_mode="run",
        #     execution_mode="tests",
        #     target_tests={
        #         "can": ["can/test_TG1_TC1_BusOffAutoRecoveryTest"]
        #     }
        # )

    except KeyboardInterrupt:
        print("\n\n用户中断，测试执行退出")
    except Exception as e:
        print(f"\n测试执行出错: {e}")
        traceback.print_exc()
    finally:
        exit_code = 0 if success else 1
        print(f"\n测试结束")
        os._exit(exit_code)

if __name__ == "__main__":
    main()
