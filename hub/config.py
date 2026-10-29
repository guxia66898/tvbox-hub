"""运行配置与种子加载。"""
from __future__ import annotations

import json
from dataclasses import fields
from dataclasses import dataclass


@dataclass
class HubConfig:
    # 字段名与 config.example.json 一一对应
    seeds_path: str = "seeds/lines.json"
    out_dir: str = "dist"
    history_dir: str = "history"
    timeout_s: float = 8.0
    concurrency: int = 16
    max_depth: int = 3
    children_limit: int = 100
    max_nodes: int = 800
    samples: int = 1
    ua: str = "okhttp/4.12.0"
    harvest_enabled: bool = True
    harvest_per_page: int = 60
    l2_enabled: bool = True
    l2_max_sites: int = 20
    l2_concurrency: int = 16
    allow_private: bool = False
    max_bytes: int = 4_194_304
    max_pages: int | None = None
    # 自动发现新仓库
    discover_enabled: bool = True
    discover_max: int = 40
    discover_concurrency: int = 8
    discover_queries: list | None = None
    discover_index_pages: list | None = None
    github_token: str = ""
    # 采集子线自动晋升
    promote_enabled: bool = True
    promote_after: int = 3
    promote_prune_fails: int = 5
    promote_max: int = 300
    # jar 可达性检查（type:3 站点依赖 jar，失效 jar 下的站点必然不可用）
    jar_check_enabled: bool = True
    jar_check_workers: int = 12
    # 导出层：GitHub 直链镜像改写（国内电视台/盒子直连 raw.githubusercontent 不通）
    mirror_enabled: bool = True
    mirror_prefixes: list | None = None

    @classmethod
    def from_file(cls, path: str | None, overrides: dict | None = None) -> "HubConfig":
        """从 JSON 文件加载，overrides 中非 None 的键覆盖文件值。"""
        data: dict = {}
        if path:
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
            except FileNotFoundError as e:
                raise FileNotFoundError(f"配置文件不存在：{path}") from e
            known = {f.name for f in fields(cls)}
            data = {k: v for k, v in raw.items() if k in known and not k.startswith("_")}
        base = {f.name: getattr(cls(), f.name) for f in fields(cls)}
        if overrides:
            for k, v in overrides.items():
                if v is not None and k in base:
                    base[k] = v
        return cls(**base)


def load_seeds(path: str) -> tuple[list[list[str]], list[str]]:
    """读取种子文件：base_lines=[[name,url]...]，aggregator_pages=[url...]。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"种子文件不存在：{path}（应包含 base_lines 与 aggregator_pages）") from e
    base = [[str(n), str(u)] for n, u in data.get("base_lines", [])]
    pages = [str(p) for p in data.get("aggregator_pages", [])]
    return base, pages
