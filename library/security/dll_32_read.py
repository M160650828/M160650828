import sys
import ctypes
import os
import json
def generate_key_ex(dll_path, seed, security_level: int =0, variant: str="", key_buf_size: int = 32):
    """
    Python封装的GenerateKeyEx接口
    :param seed: 种子字节流
    :param security_level: 安全等级
    :param variant: 变体名
    :param key_buf_size: 期望的key缓冲区大小
    :return: 生成的key字节流
    """
    iSeedArray = (ctypes.c_ubyte * len(seed))(*seed)
    iSeedArraySize = ctypes.c_uint(len(seed))
    iSecurityLevel = ctypes.c_uint(security_level)
    iVariant = ctypes.c_char_p(variant.encode('utf-8'))
    ioKeyArray = (ctypes.c_ubyte * key_buf_size)()
    iKeyArraySize = ctypes.c_uint(key_buf_size)
    oSize = ctypes.c_uint(0)
    sec_dll = ctypes.CDLL(os.path.abspath(dll_path))
    # print(f"{dll_path} 加载成功")

    sec_dll.GenerateKeyEx.restype = ctypes.c_int
    sec_dll.GenerateKeyEx.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte),  # iSeedArray
        ctypes.c_uint,                   # iSeedArraySize
        ctypes.c_uint,                   # iSecurityLevel
        ctypes.c_char_p,                 # iVariant
        ctypes.POINTER(ctypes.c_ubyte),  # ioKeyArray
        ctypes.c_uint,                   # iKeyArraySize
        ctypes.POINTER(ctypes.c_uint)    # oSize
    ]

    ret = sec_dll.GenerateKeyEx(
        iSeedArray,
        iSeedArraySize,
        iSecurityLevel,
        iVariant,
        ioKeyArray,
        iKeyArraySize,
        ctypes.byref(oSize)
    )
    if ret != 0:
        raise RuntimeError(f"GenerateKeyEx failed, return code: {ret}")
    return list(ioKeyArray[:oSize.value])
def test_ex(dll_path, seed, security_level: int =0, variant: str="", key_buf_size: int = 32):
    val = list([1,2,3,4,5,6,7])
    return val
def main(*args):
    for arg in args:
        print(f"Argument: {arg}")
    f_json_file = open(args[0],'r')
    f_json_all = f_json_file.read()
    f_json_file.close()
    val_json = json.loads(f_json_all)
    print(val_json)
    val = generate_key_ex(val_json["dll_path"],bytes(val_json["seed"]),val_json["security_level"],val_json["variant"],val_json["key_buf_size"])
    print("")
    print(val)
if __name__ == "__main__":
    main(*sys.argv[1:])
    # v = {}
    # v["dll_path"]="D://test.json"
    # v["seed"]= [1,2,3,4,255]
    # v["security_level"]= 1
    # v["variant"]= "test"
    # v["key_buf_size"]= 32
    # print(v)
    # w_json_file = open("D://test.json",'w')
    # w_json_file.write(json.dumps(v))
    # w_json_file.close()
    # main(("D://test.json"))
    