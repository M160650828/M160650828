import inspect
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd

from .e2e_module import (
    e2e_initialization, e2e_deinitialization,
    verify_can_crc, verify_can_counter, verify_can_busoff_counter,
    verify_can_crc_receive,verify_can_counter_receive,Counter_Miss_Error,Counter_Repeated_Error,Counter_Unorder_Error
)


class E2ETestFixture(TestFixture):
    def group_setup(self, context=None):
        e2e_initialization()

    def group_teardown(self, context=None):
        e2e_deinitialization()

    def case_setup(self, context=None):
        if context:
            TestStart(context["test_name"])

    def case_teardown(self, context=None):
        TestEnd("")
        TestLog("INFO", "测试结束", "执行测试结束和去初始化")


def test_TG1_TC1_CAN_CRC_Send_Check():
    """
    CAN节点发送CRC校验
    """

    TestLog("INFO", "CAN CRC", "开始校验")
    verify_can_crc(profile_1a=True)
    TestLog("INFO", "CAN CRC", "结束")


def test_TG1_TC2_CAN_Counter_Send_Check():
    """
    CAN节点发送Counter校验
    """

    TestLog("INFO", "CAN Counter", "开始校验")
    verify_can_counter(profile_1a=True)
    TestLog("INFO", "CAN Counter", "结束")


def test_TG1_TC3_CAN_BusOff_Counter_Send_Check():
    """
    CAN节点busoff后发送Counter校验
    """

    TestLog("INFO", "CAN busoff Counter", "开始校验")
    verify_can_busoff_counter(profile_1a=True)
    TestLog("INFO", "CAN busoff Counter", "结束")


def test_TG1_TC4_CAN_CRC_Receive_Check():
    """
    CAN节点接收CRC校验
    """
    TestLog("INFO", "CAN CRC接收", "开始校验")
    verify_can_crc_receive(profile_1a=True)
    TestLog("INFO", "CAN CRC接收", "结束")


def test_TG1_TC5_CAN_Counter_Miss_Receive_Check():
    """
    CAN节点接收Counter丢失校验
    """
    TestLog("INFO", "CAN Counter丢失", "开始校验")
    verify_can_counter_receive(profile_1a=True,counter_error_type=Counter_Miss_Error)
    TestLog("INFO", "CAN Counter丢失", "结束")


def test_TG1_TC6_CAN_Counter_Repeated_Receive_Check():
    """
    CAN节点接收Counter重复校验
    """
    TestLog("INFO", "CAN Counter重复", "开始校验")
    verify_can_counter_receive(profile_1a=True,counter_error_type=Counter_Repeated_Error)
    TestLog("INFO", "CAN Counter重复", "结束")


def test_TG1_TC7_CAN_Counter_Unorder_Receive_Check():
    """
    CAN节点接收Counter顺序错误校验
    """
    TestLog("INFO", "CAN Counter顺序错误", "开始校验")
    verify_can_counter_receive(profile_1a=True,counter_error_type=Counter_Unorder_Error)
    TestLog("INFO", "CAN Counter顺序错误", "结束")


def test_TG2_TC1_CANFD_CRC_Send_Check():
    """
    CANFD节点发送CRC校验
    """

    TestLog("INFO", "CANFD CRC", "开始校验")
    verify_can_crc(profile_1a=False)
    TestLog("INFO", "CANFD CRC", "结束")


def test_TG2_TC2_CANFD_Counter_Send_Check():
    """
    CANFD节点发送Counter校验
    """

    TestLog("INFO", "CANFD Counter", "开始校验")
    verify_can_counter(profile_1a=False)
    TestLog("INFO", "CANFD Counter", "结束")


def test_TG2_TC3_CANFD_BusOff_Counter_Send_Check():
    """
    CANFD节点busoff后发送Counter校验
    """

    TestLog("INFO", "CANFD busoff Counter", "开始校验")
    verify_can_busoff_counter(profile_1a=False)
    TestLog("INFO", "CANFD busoff Counter", "结束")


def test_TG2_TC4_CANFD_CRC_Receive_Check():
    """
    CANFD节点接收CRC校验
    """
    TestLog("INFO", "CANFD CRC接收", "开始校验")
    verify_can_crc_receive(profile_1a=False)
    TestLog("INFO", "CANFD CRC接收", "结束")


def test_TG2_TC5_CANFD_Counter_Miss_Receive_Check():
    """
    CANFD节点接收Counter丢失校验
    """
    TestLog("INFO", "CANFD Counter丢失", "开始校验")
    verify_can_counter_receive(profile_1a=False,counter_error_type=Counter_Miss_Error)
    TestLog("INFO", "CANFD Counter丢失", "结束")


def test_TG2_TC6_CANFD_Counter_Repeated_Receive_Check():
    """
    CANFD节点接收Counter重复校验
    """
    TestLog("INFO", "CANFD Counter重复", "开始校验")
    verify_can_counter_receive(profile_1a=False,counter_error_type=Counter_Repeated_Error)
    TestLog("INFO", "CANFD Counter重复", "结束")


def test_TG2_TC7_CANFD_Counter_Unorder_Receive_Check():
    """
    CANFD节点接收Counter顺序错误校验
    """
    TestLog("INFO", "CANFD Counter顺序错误", "开始校验")
    verify_can_counter_receive(profile_1a=False,counter_error_type=Counter_Unorder_Error)
    TestLog("INFO", "CANFD Counter顺序错误", "结束")


def get_all_test_cases():
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases

