import json
from pathlib import Path
from typing import Any


# 按 UTF-8 读取数据集中的全部商品 JSON。
def load_product_files(dataset_dir: str) -> list[dict[str, Any]]:
    root = Path(dataset_dir)
    products: list[dict[str, Any]] = []

    # 数据集按品类目录组织，每个品类下的 data 目录保存商品 JSON。
    for path in sorted(root.glob("*/data/*.json")):
        products.append(json.loads(path.read_text(encoding="utf-8")))
    return products


# 命令行入口，先输出数量用于校验数据集。
def main() -> None:
    products = load_product_files("data/ecommerce_agent_dataset")
    print(f"loaded_products={len(products)}")


if __name__ == "__main__":
    main()
