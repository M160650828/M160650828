"""
S<Type><ByteCount><Address><Data><Checksum>
S: 起始符，固定为字符"S"，标识一条记录的开始
<Type>：表示记录类型，0-文件头（通常包含文件名或描述信息）
                   1-16位地址的数据记录，0x0000    ~0xFFFF
                   2-24位地址的数据记录，0x000000  ~0xFFFFFF
                   3-32位地址的数据记录，0x00000000~0xFFFFFFFF
                   5-记录计数（可选，表示S1/S2/S3记录的数量）
                   7/8/9-终止记录（表示程序入口地址或文件结束）
<ByteCount>：两位十六进制数，表示后续字段（地址+数据+校验和）的总字节数
<Address>：根据记录类型，确定长度，S1-2字节，S2-3字节，S3-4字节
<Data>：可变长度的二进制数据，以十六进制ASCII编码表示
<Checksum>：1字节，用于验证记录的完整性，=0xFF-(字节数+地址高位到地位+数据所有字节)的低8位
"""


class S19Section:
    def __init__(self, start_address, data):
        self.start_address = start_address
        self.data = data
        self.length = len(data)
        print(f"新建 section - 地址: 0x{start_address:08X}, 大小: 0x{self.length:08X}")


class S19Parser:
    def __init__(self):
        self.sections = []

    def parse_file(self, file_path):
        """解析S19文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                current_section = None
                current_data = bytearray()
                current_address = None

                for line_num, line in enumerate(f, 1):
                    try:
                        line = line.strip()
                        if not line or not line.startswith('S'):
                            continue

                        # 基本格式检查
                        if len(line) < 4:
                            raise ValueError(f"行 {line_num}: S19格式错误")

                        record_type = line[1]
                        if record_type not in ['0', '1', '2', '3', '5', '7', '8', '9']:
                            continue  # 跳过未知记录类型

                        # 只处理数据记录
                        if record_type in ['1', '2', '3']:
                            try:
                                count = int(line[2:4], 16)
                            except ValueError:
                                raise ValueError(f"行 {line_num}: 计数字段格式错误")

                            # 根据记录类型确定地址长度
                            if record_type == '1':
                                addr_len = 4
                            elif record_type == '2':
                                addr_len = 6
                            else:  # S3
                                addr_len = 8

                            # 检查行长度
                            if len(line) < 4 + addr_len + 2:  # 头部+地址+校验和
                                raise ValueError(f"行 {line_num}: 数据长度不足")

                            try:
                                # 解析地址和数据
                                address = int(line[4:4 + addr_len], 16)
                                data = bytearray.fromhex(line[4 + addr_len:-2])

                                # 检查是否需要开始新的section
                                if current_address is None:
                                    current_address = address
                                    current_data = data
                                elif address == current_address + len(current_data):
                                    # 连续地址，追加数据
                                    current_data.extend(data)
                                else:
                                    # 不连续地址，保存当前section并开始新的section
                                    if current_data:
                                        self.sections.append(S19Section(current_address, current_data))
                                    current_address = address
                                    current_data = data
                            except ValueError:
                                raise ValueError(f"行 {line_num}: 数据格式错误")

                    except Exception as e:
                        raise ValueError(f"行 {line_num}: {str(e)}")

                # 保存最后一个section
                if current_data:
                    self.sections.append(S19Section(current_address, current_data))

                # 检查是否有有效的sections
                if not self.sections:
                    raise ValueError("文件中没有找到有效的数据记录")

        except UnicodeDecodeError:
            raise ValueError("文件编码错误")
        except IOError as e:
            raise ValueError(f"文件读取错误: {str(e)}")
        except Exception as e:
            raise ValueError(f"S19文件解析失败: {str(e)}")

    def get_sections(self):
        """返回所有sections"""
        return self.sections


def parse_s19(s19_file_path):
    parser = S19Parser()
    parser.parse_file(s19_file_path)

    data_blocks = []  # 存储所有数据块 [{address: int, data: bytes}, ...]
    start_address = None

    for item in parser.get_sections():
        if start_address is None:
            start_address = item.start_address
        data_blocks.append({
            'address': item.start_address,
            'data': item.data
        })
    return data_blocks, start_address


if __name__ == '__main__':
    # s19_path = r"C:\Users\xuefeilong\Downloads\LVBM_BOD01A001_APP02.00.00_250513_HWV2.01\1-driver-a.s19"
    # s19_path = r"C:\Users\xuefeilong\Downloads\LVBM_BOD01A001_APP02.00.00_250513_HWV2.01\2-app-b.s19"
    # s19_path = r"C:\Users\xuefeilong\Downloads\IBS_CHS03A001_APP01.01.02_250512_HWV1.01\1-driver.s19"
    s19_path = r"C:\Users\xuefeilong\Downloads\IBS_CHS03A001_APP01.01.02_250512_HWV1.01\2-app.s19"

    block_infos, start_addr = parse_s19(s19_path)
    for idx, block in enumerate(block_infos):
        start_address = block["address"]
        data = block["data"]
        length = len(data)
        print(hex(start_address), hex(length), data[:100])
