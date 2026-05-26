from library.security.generate_key import generate_key_ex


def calcKey_SA4(securityLevel, seedArray, KeyK):
    """
    SA4 安全级别算法
    :param securityLevel: 安全级别
    :param seedArray: Seed 字节数组
    :param KeyK: 密钥常量
    :return: Key 字节数组
    """
    SecM_Level4_Cycle_value = 32

    seed = seedArray[0] << 24 | seedArray[1] << 16 | seedArray[2] << 8 | seedArray[3]
    temp_key = seed ^ KeyK

    for _ in range(SecM_Level4_Cycle_value):
        temp_key = (temp_key << 7) | (temp_key >> 25)
        temp_key &= 0xFFFFFFFF
        temp_key ^= KeyK

    keyArray = []
    keyArray.append((temp_key >> 24) & 0xFF)
    keyArray.append((temp_key >> 16) & 0xFF)
    keyArray.append((temp_key >> 8) & 0xFF)
    keyArray.append((temp_key >> 0) & 0xFF)

    return keyArray


def Seed2KeyCR(securityLevel, seedArray, KeyK):
    """
    使用自定义算法计算 Key（Custom Route）
    :param securityLevel: 安全级别
    :param seedArray: Seed 字节数组
    :param KeyK: 密钥常量
    :return: Key 字节数组
    """
    if securityLevel == 4:
        return calcKey_SA4(securityLevel, seedArray, KeyK)
    else:
        raise Exception("SecurityLevel not supported")


def Seed2Key(dll_path, seedArray):
    """
    使用 DLL 计算 Key（通用方式）
    :param dll_path: DLL 文件路径
    :param seedArray: Seed 字节数组
    :return: Key 字节数组
    """
    return generate_key_ex(dll_path, seedArray)

