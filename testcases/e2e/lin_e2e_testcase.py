import inspect
from uvtest.testlog import TestLog
from uvtest.framework import TestFixture
from common.control import TestStart, TestEnd

from .e2e_module import (
    e2e_initialization, e2e_deinitialization,
    verify_lin_crc_and_counter
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


def test_TG1_TC1_LIN_CRC8_Counter_Check():
    """
    节点发送报文CRC8 Counter值测试
    """
    try:
        TestLog("INFO", "LIN  Counter", "开始校验")
        verify_lin_crc_and_counter(profile_1a=True,crc_check=False)
        TestLog("INFO", "LIN Counter", "结束")
    finally:
        TestEnd("")


def test_TG1_TC2_LIN_CRC8_Checksun_Check():
    """
    节点发送报文CRC8 E2E算法值测试
    """
    try:
        TestLog("INFO", "LIN CRC8", "开始校验")
        verify_lin_crc_and_counter(profile_1a=True,counter_check=False)
        TestLog("INFO", "LIN CRC8", "结束")
    finally:
        TestEnd("")

def test_TG1_TC3_LIN_CRC16_Counter_Check():
    """
    节点发送报文CRC16 Counter值测试
    """
    try:
        TestLog("INFO", "LIN  Counter", "开始校验")
        verify_lin_crc_and_counter(profile_1a=False,crc_check=False)
        TestLog("INFO", "LIN Counter", "结束")
    finally:
        TestEnd("")


def test_TG1_TC4_LIN_CRC16_Checksun_Check():
    """
    节点发送报文CRC16 E2E算法值测试
    """
    try:
        TestLog("INFO", "LIN CRC16", "开始校验")
        verify_lin_crc_and_counter(profile_1a=False,counter_check=False)
        TestLog("INFO", "LIN CRC16", "结束")
    finally:
        TestEnd("")


def get_all_test_cases():
    current_module = inspect.getmodule(inspect.currentframe())
    test_cases = {}
    for name, obj in inspect.getmembers(current_module):
        if name.startswith('test_') and callable(obj):
            test_cases[name] = obj
    return test_cases

