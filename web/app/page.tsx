import { getProducts, type Product } from "@/lib/products";

export const dynamic = "force-dynamic";

export default async function CatalogPage() {
  let products: Product[] | null = null;
  try {
    products = await getProducts();
  } catch (error) {
    console.error("Failed to load catalog", error);
  }

  return (
    <main>
      <h1>Каталог</h1>
      {products === null && <p>Не удалось загрузить каталог. Обновите страницу.</p>}
      {products?.length === 0 && <p>Товаров пока нет.</p>}
      {products && products.length > 0 && (
        <ul>
          {products.map((product) => (
            <li key={product.id}>
              <img src={product.image_url} alt={product.title} width={160} />
              <p>{product.title}</p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
