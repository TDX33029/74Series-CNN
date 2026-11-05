"""Add a navigation outline to the review-guide PDF."""
from __future__ import annotations

import os
import sys

import pymupdf as fitz

TOC = [
    (1, "封面", 1),
    (1, "0. 文档范围与结论", 2),
    (1, "1. 系统总览", 3),
    (1, "2. 模块间连线与拓扑", 5),
    (2, "2.6 网表实测：哪些连接其实没有连", 9),
    (1, "3. 从输入到结果的完整过程", 10),
    (1, "4. 关键操作详解", 14),
    (2, "4.1 S01 监督微码", 14),
    (2, "4.2 S02 存储时序", 17),
    (2, "4.3 S07/S08/S09 本地 FSM 与流水线", 18),
    (2, "4.4 V2 Requant", 20),
    (2, "4.5 S05 Pool 与 S06 Argmax", 21),
    (1, "5. 时序与性能", 22),
    (1, "6. 评审发现与风险", 22),
    (2, "6.1 P0：功能/可制造性阻断", 22),
    (2, "6.2 P1：高风险", 24),
    (2, "6.3 文档/测试不一致", 24),
    (1, "7. 验证矩阵与边界", 24),
    (1, "8. 评审清单", 25),
    (1, "9. 附录", 26),
]


def main(path: str) -> int:
    doc = fitz.open(path)
    doc.set_toc(TOC)
    tmp = path + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, path)
    print(f"outline added: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
