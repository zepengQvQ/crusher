# 给 Java 同学的 Python 速记

- 包管理：`pyproject.toml` + `pip install -e .`（类似 Maven `pom.xml`）
- 锁文件：`backend-python/requirements.lock`（类似锁定依赖版本）
- 配置：`pydantic-settings` 读根目录 `.env`
- 依赖注入：看 `composition_root.py`（显式构造，无魔法装饰器）
- 接口：`Protocol`（类似 interface）
- 启动地图：[`java-python-map.md`](java-python-map.md)
