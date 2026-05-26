import ctypes
import os

import subprocess
import json
def call_32bit_dll(param):
    path = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run([path +'//dll_32_read.exe', param], capture_output=True, text=True)
    val = result.stdout.strip()
    val.encode()
    val = val.split("\n")
    js_str = val[-1]
    val_list = json.loads(js_str)
    print(val_list,len(val_list))
    return val_list

def generate_key_ex(dll_path, seed, security_level: int =0, variant: str="", key_buf_size: int = 32):
    """
    Python封装的GenerateKeyEx接口
    :param seed: 种子字节流
    :param security_level: 安全等级
    :param variant: 变体名
    :param key_buf_size: 期望的key缓冲区大小
    :return: 生成的key字节流
    """
    try:
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
    except:
        sec_dll = None
        v = {}
        v["dll_path"]=dll_path
        v["seed"]= list(seed)
        v["security_level"]= security_level
        v["variant"]= variant
        v["key_buf_size"]= key_buf_size
        path = os.path.dirname(os.path.abspath(__file__))
        w_json_file = open(path +"//test.json",'w')
        w_json_file.write(json.dumps(v))
        w_json_file.close()
        return call_32bit_dll(path +"//test.json")


if __name__ == '__main__':
    dll_path = r"D:\0_code\solarproject\framework\testinputs\sec_dll\SHA_PICU_2701.dll"
    seed_array = list(bytes.fromhex("94 73 59 91 3f 32 34 8b 53 ad 85 db e8 80 42 de".replace(" ", "")))

    print(f"DLL 存在: {os.path.exists(dll_path)}")
    print(f"Seed: {[hex(s) for s in seed_array]}")

    if os.path.exists(dll_path):
        ret = generate_key_ex(str(dll_path), seed_array, 0, "")
        print(f"Key: {[hex(item) for item in ret]}")
    else:
        print("错误: DLL 文件不存在，请检查路径")
