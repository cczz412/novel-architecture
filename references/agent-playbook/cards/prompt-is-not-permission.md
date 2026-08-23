# 提示词不是权限

身份：外部先验（与已拍「签字必须显式」同向，仍不能冒充新合同）

## 遇到什么

怕 AI 越权、删错、改错篮子。只在提示词里写「不要乱动」行不行？

## 对的做法

高影响动作在模型之外拦截：能力边界、授权校验、审计和失败状态。工具元数据里的「只读、破坏性、幂等」不能当安全证明。[CLM-DR-UX-03-K01] [CLM-DR-UX-03-K02]

长任务的 task ID 不是授权凭证。每次恢复、查询或取消仍要重新校验用户、范围和权限。[CLM-DR-UX-03-K05] [CLM-DR-UX-03-K06]

聊天、按钮和管理员工具共用同一 Action 内核，比三套逻辑各自改数据更安全。[CLM-DR-UX-03-K12]

已拍同向：正史签字必须作者显式动作。SI-008 加固形状：签字不进工具表、不经过模型。

## 错的做法

只靠提示词「别偷看／别乱改／选择最新状态」。用聊天里的「好」代替签字。把 VS Code／Cursor「改了就落盘」搬到故事真值。

## 出处

- [EKB 产品 UX 页](../../external-knowledge-base/EXTERNAL_KNOWLEDGE_BASE_20260815_R01/background/06_PRODUCT_UX_AND_AGENT_TOOLS.md)（K01／K02／K05／K06／K09／K12）
- [SI-008 消化](../../survey-inbox/packages/AGENT_TOOLS_PIPELINE_RESEARCH_RETURNS_20260814_R01/02_RETURNS_DIGEST.md)

来源：#115
