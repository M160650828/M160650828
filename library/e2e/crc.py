def crc8_saej1850(data: bytes) -> int:
    """
    CRC-8 SAE J1850 算法

    用于 AUTOSAR E2E Profile 1, 1A, 2

    参数:
        Polynomial: 0x1D
        Initial Value: 0x00
        XOR Out: 0x00

    @param data: 待计算的数据
    @return: 8位CRC值 (0x00-0xFF)
    """
    crc_init_value = 0x00
    crc_polynomial = 0x1D
    crc_xor_value = 0x00

    crc = crc_init_value
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ crc_polynomial) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

    crc ^= crc_xor_value
    return crc


def crc16_ccitt(data: bytes) -> int:
    """
    CRC-16 CCITT-FALSE 算法

    用于 AUTOSAR E2E Profile 5

    参数:
        Polynomial: 0x1021
        Initial Value: 0xFFFF
        XOR Out: 0x0000

    @param data: 待计算的数据
    @return: 16位CRC值 (0x0000-0xFFFF)
    """
    crc_init_value = 0xFFFF
    crc_polynomial = 0x1021
    crc_xor_value = 0x0000

    crc = crc_init_value
    for byte in data:
        crc ^= (byte << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ crc_polynomial) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF

    crc ^= crc_xor_value
    return crc

