"""Minimal test runner for `robustcases` that records results via test_log_report.

This runner will walk the `robustcases` package, import modules, and attempt
to call one of the common entrypoints if present: `run`, `run_test`, `main`.
If none are found the module is skipped but recorded as such in the report.
"""
from __future__ import annotations

import pkgutil
import importlib
import traceback
from typing import Callable

from test_log_report import TestLogReport


COMMON_ENTRYPOINTS = ("run", "run_test", "main", "test")


def find_modules(package_name: str):
    try:
        package = importlib.import_module(package_name)
    except Exception:
        return []
    modules = []
    if hasattr(package, "__path__"):
        for finder, name, ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            if not ispkg:
                modules.append(name)
    return modules


def try_run_module(mod_name: str) -> tuple[str, str, str]:
    """Import module and try to run entrypoint; return (name,status,message)."""
    try:
        mod = importlib.import_module(mod_name)
    except Exception as e:
        return (mod_name, "error", f"import failed: {e}")

    for ep in COMMON_ENTRYPOINTS:
        func = getattr(mod, ep, None)
        if callable(func):
            try:
                func()
                return (mod_name, "passed", f"ran {ep}()")
            except Exception as e:
                tb = traceback.format_exc()
                return (mod_name, "failed", tb)

    return (mod_name, "skipped", "no known entrypoint found")


def run_all(out_dir: str = "logs"):
    report = TestLogReport(out_dir=out_dir)
    modules = find_modules("robustcases")
    if not modules:
        report.log_result("robustcases", "error", "no modules found or import failed")
        print("No robustcases modules found. Is the package installed?")
        print("Report:", report.write_report())
        return

    for m in modules:
        name, status, message = try_run_module(m)
        report.log_result(name, status, message)

    path = report.write_report()
    print("Robust test run finished. Report:", path)


if __name__ == "__main__":
    run_all()
import os
import sys
import traceback
import env           # 环境初始化（路径、DLL、runtime）

from uvtest.framework import run_test_framework, discover_test_groups

def main():
    success = False
    try:
        project_dir = os.path.dirname(os.path.abspath(__file__))
        robustcases_dir = os.path.join(project_dir, "robustcases")
        sys.path.insert(0, robustcases_dir)
        discover_test_groups(robustcases_dir)

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

        # run_test_framework(session_mode="start", execution_mode="tests")

        # 运行指定测试用例
        # success = run_test_framework(
        #     session_mode="run",
        #     execution_mode="tests",
        #     target_tests={
        #         "can": ["can/test_TG1_TC1_BusOffAutoRecoveryTest"]
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
