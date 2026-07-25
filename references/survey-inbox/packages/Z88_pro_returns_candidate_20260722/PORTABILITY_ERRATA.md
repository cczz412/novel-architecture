# Z88 小包便携性勘误

这个目录原来是一个指向 `reports/` 的仓外软链。`reports/` 不进 Git，所以干净克隆后会断。现在保留原路径不变，改成 Git 内的实体小包；`reports/Z88_pro_returns_candidate_20260722/` 原件没有移动、删除或回写。

旧 [`SHA256SUMS.txt`](SHA256SUMS.txt) 是历史收件账，必须原样保留。它登记的 `inventory.json` 是早期 1692 字节版本；后来 inventory 补了字段，实物变成 2874 字节，因此旧清单不能再代表当前包。

当前六个规范内容文件只认 [`SHA256SUMS.current.txt`](SHA256SUMS.current.txt)。别名 `Z88_return_receipt.md` 是包内相对软链，不重复计数。

来源：Codex
