# DTC触发测试配置
class DTCTriggerConfig:
    """DTC触发测试配置类"""

    # 测试参数
    MONITOR_DURATION = 30.0  # 监控持续时间(秒)
    EXPECTED_TRIGGER_INTERVAL = 1.0  # 期望的触发间隔(秒)

    # 测试DTC列表（实际使用时需要根据项目配置修改）
    # 格式: {"dtc_code": 十六进制DTC代码, "fault_type": 故障类型, "description": 描述}
    TEST_DTC_LIST = [
        {"dtc_code": 0x1234, "fault_type": "voltage", "description": "电压过高故障"},
        {"dtc_code": 0x5678, "fault_type": "communication", "description": "通信超时故障"},
        {"dtc_code": 0x9ABC, "fault_type": "sensor", "description": "传感器异常故障"},
        {"dtc_code": 0xDEF0, "fault_type": "general", "description": "通用故障"}
    ]

    # 故障类型映射
    FAULT_TYPE_MAPPING = {
        "voltage": "电压相关故障",
        "communication": "通信相关故障",
        "sensor": "传感器相关故障",
        "general": "通用故障"
    }

    # DTC触发帧格式配置（根据上汽诊断规范）
    TRIGGER_FRAME_FORMAT = {
        "header": [0x55, 0xAA],  # 帧头标识
        "min_length": 8,  # 最小帧长度
        "checksum_start": 0,  # 校验和起始位置
        "checksum_end": 6,  # 校验和结束位置
        "checksum_position": [6, 7]  # 校验和位置
    }


class DTCTriggerTestConfig:
    """DTC触发测试用例配置"""

    # TG1_TC24 配置
    TG1_TC24_CONFIG = {
        "monitor_duration": 30.0,
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST,
        "expected_frames_per_dtc": 1  # 每个DTC期望的触发帧数量
    }

    # TG1_TC25 配置
    TG1_TC25_CONFIG = {
        "monitor_duration": 15.0,
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST[:2],
        "recovery_delay": 2.0,  # 恢复后延迟时间
        "retry_delay": 1.0  # 重试延迟时间
    }

    # TG1_TC26 配置
    TG1_TC26_CONFIG = {
        "monitor_duration": 5.0,
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST[:3],  # 测试三个无父子关系的DTC
        "expected_interval": DTCTriggerConfig.EXPECTED_TRIGGER_INTERVAL,
        "tolerance": 0.1  # 时间间隔容差
    }

    # TG1_TC29 配置 - 诊断故障代码配置检查（配置位为0）
    TG1_TC29_CONFIG = {
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST[:2],
        "dtc_configuration_identifier": 0x0100,  # DTC配置标识符DID
        "config_bit_setting": 0,  # 配置位设置为0
        "fault_simulation_delay": 2.0,
        "expected_status_byte": 0x00  # 期望状态字节为00
    }

    # TG1_TC30 配置 - 诊断故障代码配置检查（配置位为1）
    TG1_TC30_CONFIG = {
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST[:2],
        "dtc_configuration_identifier": 0x0100,  # DTC配置标识符DID
        "config_bit_setting": 1,  # 配置位设置为1
        "fault_simulation_delay": 2.0,
        "expected_status_byte": 0x01  # 期望状态字节为非00
    }

    # TG1_TC31 配置 - 最大诊断故障代码条目数检查
    TG1_TC31_CONFIG = {
        "max_dtc_count": 10,  # 最大DTC条目数
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST * 3,
        "snapshot_data_check": True,
        "extended_data_check": True
    }

    # TG1_TC32 配置 - 非易失存储器存储检查
    TG1_TC32_CONFIG = {
        "max_dtc_count": 10,  # 最大DTC条目数
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST * 3,
        "reset_delay": 3.0,  # 复位后延迟时间
        "data_loss_tolerance": 0.1,  # 数据丢失容忍度（10%）
        "snapshot_data_check": True,
        "extended_data_check": True
    }

    # TG1_TC33 配置 - 诊断故障代码溢出机制检查
    TG1_TC33_CONFIG = {
        "max_dtc_count": 10,  # 最大DTC条目数
        "test_dtc_list": DTCTriggerConfig.TEST_DTC_LIST * 3,
        "overflow_dtc_priority": "low",  # 溢出DTC优先级（low: 低优先级）
        "high_priority_dtc": {"dtc_code": 0x9999, "fault_type": "overflow", "description": "高优先级溢出测试DTC"},
        "overflow_check_delay": 2.0,  # 溢出检查延迟时间
        "snapshot_data_check": True,
        "extended_data_check": True
    }


# 项目特定的DTC配置（仅供参考）
class ProjectDTCConfig:
    """项目特定的DTC配置"""
    PROJECT_TEST_DTC_LIST = [
        {"dtc_code": 0x1001, "fault_type": "voltage", "description": "电源电压过高"},
        {"dtc_code": 0x2001, "fault_type": "communication", "description": "LIN通信超时"},
        {"dtc_code": 0x3001, "fault_type": "sensor", "description": "温度传感器异常"},
        {"dtc_code": 0x4001, "fault_type": "general", "description": "系统故障"}
    ]


def get_dtc_test_config(project_specific: bool = False):
    """获取DTC测试配置"""
    if project_specific:
        return ProjectDTCConfig.PROJECT_TEST_DTC_LIST
    else:
        return DTCTriggerConfig.TEST_DTC_LIST
