import os
import traceback
import env           # 环境初始化（路径、DLL、runtime）
import env.test_session  # 注册标准测试 SessionFixture

from uvtest.framework import run_test_framework, discover_test_groups
def main():
    success = False
    try:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        testcases_canlin_dir = os.path.join(project_dir, "testcases_canlin")
        discover_test_groups(testcases_canlin_dir)

        # 交互式
        success = run_test_framework()

        # 运行所有测试
        #success = run_test_framework(execution_mode="all")

        # 运行指定测试组
        # success = run_test_framework(
        #     session_mode="run",
        #     execution_mode="groups",
        #     target_groups=["CAN"]
        # )

        # run_test_framework(session_mode="start", execution_mode="tests")

        # 运行指定测试用例
        # success = run_test_framework(
        #     session_mode="run",
        #     execution_mode="tests",
        #     target_tests={
        #         "can": ["can/test_InteractionLayer_MessageIDTest"]
        #     }
        # )

        # run_test_framework(session_mode="end", execution_mode="tests")

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
