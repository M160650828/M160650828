import time
from uvtest.testlog import TestLog

class CommChecker:
    def set_and_check(self, voltage: float, delay: float):
        raise NotImplementedError("Implement in testcases layer, e.g., CanCommChecker/LinCommChecker")

def step_voltage_threshold(checker: CommChecker, start_voltage, end_voltage,
                                   step, step_delay, test_type="stop", label: str = ""):
    current_voltage = start_voltage

    if test_type == "resume":
        current_voltage += step

    while True:
        voltage_ok, has_comm, _ = checker.set_and_check(current_voltage, step_delay)
        if not voltage_ok:
            TestLog("FAIL", f"{label}电压阈值查找" if label else "电压阈值查找", f"电压设置失败: {current_voltage:.2f} V")
            return None
        if (test_type == "stop" and not has_comm) or (test_type == "resume" and has_comm):
            return current_voltage
        if step > 0:
            if current_voltage >= end_voltage:
                TestLog("WARNING" if test_type=="stop" else "FAIL",
                        f"{label}电压阈值查找" if label else "电压阈值查找",
                        f"电压升到 {end_voltage:.2f} V，通信仍未{ '停止' if test_type=='stop' else '恢复' }，测试结束")
                return None
        else:
            if current_voltage <= end_voltage:
                TestLog("WARNING" if test_type=="stop" else "FAIL",
                        f"{label}电压阈值查找" if label else "电压阈值查找",
                        f"电压降到 {end_voltage:.2f} V，通信仍未{ '停止' if test_type=='stop' else '恢复' }，测试结束")
                return None
        current_voltage += step


def voltage_threshold_test_with_validation(checker: CommChecker, test_type,
                                                   start_voltage, end_voltage,
                                                   step, step_delay,
                                                   validation_voltage, tolerance=0.0,
                                                   label_prefix: str = ""):
    try:
        if test_type == "stop":
            test_desc = f"{label_prefix}停止通信电压测试".strip()
            if step > 0:
                validation_condition = lambda actual: actual > validation_voltage
                expected_desc = f">{validation_voltage:.2f} V"
            else:
                validation_condition = lambda actual: actual < validation_voltage
                expected_desc = f"<{validation_voltage:.2f} V"
        else:  # resume
            test_desc = f"{label_prefix}恢复通信电压测试".strip()
            if tolerance >= 0:
                validation_condition = lambda actual: actual < validation_voltage + tolerance
                expected_desc = f"<{validation_voltage + tolerance:.2f} V"
            else:
                validation_condition = lambda actual: actual > validation_voltage + tolerance
                expected_desc = f">{validation_voltage + tolerance:.2f} V"

        TestLog("INFO", "", f"{test_desc}, 起始电压: {start_voltage:.2f} V, 步进值: {step:.2f} V")
        threshold_voltage = step_voltage_threshold(
            checker, start_voltage, end_voltage, step, step_delay, test_type,
            label_prefix)
        if threshold_voltage is not None:
            ok = validation_condition(threshold_voltage)
            TestLog("PASS" if ok else "FAIL", "",
                    f"测试结果: {threshold_voltage:.2f} V, 期望: {expected_desc}")
            return ok, threshold_voltage
        else:
            log_level = "WARNING" if test_type == "stop" else "FAIL"
            TestLog(log_level, "", f"未找到{test_type}阈值")
            return False, None
    except Exception as e:
        TestLog("FAIL", "", f"电压阈值测试异常: {e}")
        import traceback
        TestLog("DEBUG", "", f"详细错误: {traceback.format_exc()}")
        return False, None


