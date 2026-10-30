export type Product = {
  id: number;
  title: string;
  image_url: string;
  created_at: string;
};

export async function getProducts(): Promise<Product[]> {
  const apiUrl = process.env.API_INTERNAL_URL;
  if (!apiUrl) {
    throw new Error("API_INTERNAL_URL is not set");
  }
  const response = await fetch(`${apiUrl}/api/products?limit=100`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Catalog API responded with ${response.status}`);
  }
  return response.json();
}
