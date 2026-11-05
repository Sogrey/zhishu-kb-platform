from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)

MD = """# 知枢差旅报销制度（样例）

## 1. 适用范围
本制度适用于公司全体全职员工的国内差旅费用报销。

## 2. 交通标准
- 高铁：二等座可报销；一等座需事前书面审批。
- 飞机：经济舱可报销；公务舱需总监审批。

## 3. 住宿标准
- 一线城市：上限 500 元/晚。
- 其他城市：上限 350 元/晚。

## 4. 餐补
出差期间餐补 100 元/天，与招待费不得重复报销。

## 5. 报销时限
出差结束后 15 个工作日内提交报销单，逾期需说明原因。
"""

TXT = """产品 FAQ
问：知枢是什么？
答：知枢是以知识治理中枢为核心的企业智能知识库。

问：密级如何生效？
答：密级在检索层过滤，无权用户对密级文档不存在。
"""

(OUT / "travel_policy.md").write_text(MD, encoding="utf-8")
(OUT / "faq.txt").write_text(TXT, encoding="utf-8")
print(f"fixtures written to {OUT}")
