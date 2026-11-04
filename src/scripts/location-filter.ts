type Region = { id: string; name: string };

const API = "https://www.emsifa.com/api-wilayah-indonesia/v2"
const cache = new Map<string, Region[]>();

async function getRegions(path: string): Promise<Region[]> {
  if (!cache.has(path)) {
    const response = await fetch(`${API}/${path}.json`);
    if (!response.ok) throw new Error("Data wilayah gagal dimuat.");
    const result = await response.json();
    cache.set(path, result.data as Region[]);
  }
  return cache.get(path)!;
}

function fill(select: HTMLSelectElement, label: string, rows: Region[] = []) {
  select.replaceChildren(new Option(label, ""));
  for (const row of rows) {
    const option = new Option(row.name, row.name);
    option.dataset.id = row.id;
    select.add(option);
  }
}

export async function setupLocationFilters(
  province: HTMLSelectElement,
  city: HTMLSelectElement,
  district: HTMLSelectElement,
  initial: { province?: string; city?: string; district?: string } = {}
) {
  fill(province, "Memuat provinsi...");
  fill(city, "Pilih provinsi dahulu");
  fill(district, "Pilih kota/kabupaten dahulu");
  city.disabled = true;
  district.disabled = true;

  const provinces = await getRegions("provinces");
  fill(province, "Semua provinsi", provinces);

  async function loadDistricts(districtName = "") {
    const id = city.selectedOptions[0]?.dataset.id;
    fill(district, "Memuat kecamatan...");
    district.disabled = !id;

    if (!id) {
      fill(district, "Semua kecamatan");
      return;
    }

    const rows = await getRegions(`districts/${id}`);
    fill(district, "Semua kecamatan", rows);
    if (districtName) district.value = districtName;
  }

  async function loadCities(cityName = "", districtName = "") {
    const id = province.selectedOptions[0]?.dataset.id;
    fill(city, "Memuat kota/kabupaten...");
    fill(district, "Pilih kota/kabupaten dahulu");
    district.disabled = true;
    city.disabled = !id;

    if (!id) {
      fill(city, "Semua kota/kabupaten");
      return;
    }

    const rows = await getRegions(`regencies/${id}`);
    fill(city, "Semua kota/kabupaten", rows);

    if (cityName) {
      city.value = cityName;
      if (city.value) await loadDistricts(districtName);
    }
  }

  province.addEventListener("change", () => void loadCities());
  city.addEventListener("change", () => void loadDistricts());

  if (initial.province) {
    province.value = initial.province;
    if (province.value) {
      await loadCities(initial.city, initial.district);
    }
  }
}
