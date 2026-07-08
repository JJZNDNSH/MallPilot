import type { ProductItem } from "../types/api";

// 做什么：定义商品卡片组件参数。
// 为什么：把商品视觉样式和字段渲染隔离出来。
interface ProductCardProps {
  /** 做什么：承载商品数据。为什么：页面需要按真实字段展示推荐事实。 */
  product: ProductItem;
}

// 做什么：把标签字符串拆成标签数组。
// 为什么：商品卡片要把标签做成更易扫读的短标签组。
function splitTags(tags: string): string[] {
  return tags
    .split(/[,\s|，]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

// 做什么：渲染单个商品卡片。
// 为什么：帮助用户快速比较候选商品的价格、口碑和适用场景。
export function ProductCard({ product }: ProductCardProps) {
  const tags = splitTags(product.tags);
  const savings = Math.max(product.original_price - product.price, 0);

  return (
    <article className="product-card">
      <div className="product-card__topline">
        <span className="product-card__category">{product.category}</span>
        <span className="product-card__stock">库存 {product.stock}</span>
      </div>

      <h3 className="product-card__title">{product.name}</h3>
      <p className="product-card__brand">{product.brand}</p>
      <p className="product-card__summary">{product.summary}</p>

      <div className="product-card__pricing">
        <span className="product-card__price">¥{product.price.toFixed(0)}</span>
        <span className="product-card__original">¥{product.original_price.toFixed(0)}</span>
        <span className="product-card__savings">省 ¥{savings.toFixed(0)}</span>
      </div>

      <dl className="product-card__facts">
        <div>
          <dt>评分</dt>
          <dd>{product.rating.toFixed(1)}</dd>
        </div>
        <div>
          <dt>销量</dt>
          <dd>{product.sales_count}</dd>
        </div>
        <div>
          <dt>推荐</dt>
          <dd>{product.is_featured ? "精选" : "标准"}</dd>
        </div>
      </dl>

      <div className="product-card__tags" aria-label="商品标签">
        {tags.map((tag) => (
          <span key={`${product.product_id}-${tag}`} className="product-tag">
            {tag}
          </span>
        ))}
      </div>
    </article>
  );
}
