import time
from uvtest.testlog import TestStopLogging, TestStartLogging, TestLog

from common.context import ctx
from env.config import CAN_TERMINATION
from common.params import P
from common.wakeup import WakeupStop

def TestStart(test_name=""):
    """
    测试开始
    """
    try:
        TestLog("DEBUG", "电源控制", "关闭DUT电源")
        ctx.power_ctrl.init(P.ProjectInfo.PowerType, P.ProjectInfo.PowerPortParam)
        ctx.bob_ctrl.init(P.ProjectInfo.DutConnectType, P.ECUInfo.BOBControlCan, power_ch=P.ECUInfo.ETS6124ECUChannel, addr=P.ECUInfo.ETS6124Addr_int)

        ctx.bob_ctrl.set_power('KL30', False)
        ctx.bob_ctrl.set_power('KL15', False)
        for can_ch, enable_term in CAN_TERMINATION.items():
            if enable_term:
                ctx.bob_ctrl.set_resistance(120, True, ch=can_ch)
                TestLog("DEBUG", "BOB Control", f"CAN{can_ch} 终端电阻已启用")


        TestLog("DEBUG", "日志记录", "开始录制日志")
        TestStartLogging()

        return 0

    except Exception as e:
        TestLog("ERROR", "测试执行", f"TestStart执行失败: {e}")
        return -1

def TestEnd(test_name=""):
    """
    测试结束
    """
    try:

        # 停止唤醒信号
        TestLog("DEBUG", "电源控制", "停止唤醒信号")
        WakeupStop()

        # 关闭DUT电源
        TestLog("DEBUG", "电源控制", "关闭DUT电源")
        ctx.bob_ctrl.set_power('KL30', False)
        time.sleep(2)
        ctx.bob_ctrl.set_power('KL15', False)

        for can_ch in CAN_TERMINATION.keys():
            ctx.bob_ctrl.set_resistance(120, False, ch=can_ch)
            TestLog("DEBUG", "BOB Control", f"CAN{can_ch} 终端电阻已关闭")

        # 将电源供应电压设置为0
        TestLog("DEBUG", "电源控制", "将电源供应电压设置为0V")
        ctx.power_ctrl.set_voltage(0.0)
        ctx.power_ctrl.deinit()

         # 停止日志记录
        TestStopLogging()
        time.sleep(1)

        TestLog("INFO", "测试结束", f"测试用例执行完成: {test_name}")

        return 0

    except Exception as e:
        TestLog("ERROR", "测试执行", f"TestEnd执行失败: {e}")
        return -1

