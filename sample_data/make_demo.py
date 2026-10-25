"""Generate fictional examples. 999999 is not a verified administrative code."""

import csv
from pathlib import Path


def with_check_digit(prefix):
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    return prefix + "10X98765432"[sum(int(n) * w for n, w in zip(prefix, weights)) % 11]


def main():
    first = with_check_digit("99999919900101001")
    second = with_check_digit("99999919850512002")
    invalid = first[:-1] + ("0" if first[-1] != "0" else "1")
    rows = [
        ["001", "示例用户甲", "13800000001", "demo01@example.com", first, "开票前联系13800000001"],
        ["002", "示例用户乙", "13900000002", "contact02@example.org", second, "邮件联系contact02@example.org"],
        ["003", "误报演示", "", "", "", "订单号 13812345678（业务编码，请取消本候选）"],
        ["004", "疑似证件", "", "demo04@example.com", invalid, "校验位错误，默认不处理"],
        ["005", "无敏感信息", "0000123", "", "", "NA"],
        ["006", "公式演示", "+86 13700000003", "", "", "=1+1"],
    ]
    target = Path(__file__).with_name("demo.csv")
    with target.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["编号", "名称", "手机号", "邮箱", "证件候选", "备注"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} synthetic rows to {target.name}")


if __name__ == "__main__":
    main()
