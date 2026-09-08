# ports/

这里的「端口」**不是**网络端口，而是「接口定义」（类似 Java `interface`）。

文件 `protocols.py`：约定任务库、知识库、大模型调用该有哪些方法。  
真正干活的实现写在 `infrastructure/`。
