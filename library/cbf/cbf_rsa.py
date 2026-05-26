import json
import traceback


def cbf_header_end_pos(file_obj):
    left_quote, right_quote = 0, 0
    content_pos = 0
    while True:
        c = file_obj.read(1)
        content_pos += 1
        if c.hex().upper() == "7B":
            left_quote += 1
        if c.hex().upper() == "7D":
            right_quote += 1
        if left_quote != 0 and right_quote != 0 and left_quote == right_quote:
            break
    return content_pos


def cbf_header(cbf_file):
    try:
        with open(cbf_file, 'rb') as f:
            content_pos = cbf_header_end_pos(f)
            f.seek(0)
            data = f.read(content_pos)
            # CBF头是JSON文本，跳过前36字节元信息后解析
            header_text = data[36:].decode(errors='replace')
            return json.loads(header_text)
    except Exception:
        traceback.print_exc()
        return {}


def cbf_blocks(cbf_file):
    return len(cbf_header(cbf_file).get("erase", []))


def cbf_block_data(cbf_file):
    result = []
    block_number = cbf_blocks(cbf_file)
    with open(cbf_file, 'rb') as f:
        content_pos = cbf_header_end_pos(f)
        f.seek(content_pos)
        for _ in range(block_number):
            start_address = f.read(4)
            length = f.read(4)
            data_len = int.from_bytes(length, "big")
            data = f.read(data_len)
            checksum = f.read(2)
            result.append({
                "start_address": int.from_bytes(start_address, "big"),
                "length": int.from_bytes(length, "big"),
                "data": data,
                "checksum":int.from_bytes(checksum, "big")
            })

    return result


def read_cbf_file(cbf_file, start_pos, read_size):
    end_pos = 0
    with open(cbf_file, 'rb') as f:
        content_pos = cbf_header_end_pos(f)
        f.seek(content_pos + start_pos)  # 定位到数据块的位置
        data = f.read(read_size)
        end_pos = start_pos + len(data)
    return {
        "data": data,
        "actual_size": len(data),
        "start_pos": end_pos
    }


if __name__ == "__main__":
    filename = r"C:\Users\xuefeilong\Desktop\workspace\master\upload_file\CGW_S0000025084_000016_FLD1_MCU_UDS_20250709.cbf"
    filename = r"C:\Users\xuefeilong\Desktop\workspace\master\upload_file\CGW_S0000025085_000016_ASW1_MCU_UDS_20250709.cbf"
    result = cbf_block_data(filename)
    print(result)
    # header_dict = cbf_header(filename)
    # print(header_dict["erase"][0]["start_address"])
    #
    # res = {"start_pos": 0}
    # while True:
    #     res = read_cbf_file(filename, res["start_pos"], 0xFE0)
    #     print(res["start_pos"], 0xFE0, res["actual_size"], res["data"][-10:].hex())
    #     if res["actual_size"] < 0xFE0:
    #         break
