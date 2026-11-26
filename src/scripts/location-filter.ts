type Region = { id: string; name: string };

const API = "https://www.emsifa.com/api-wilayah-indonesia/v2";
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
  const frag = document.createDocumentFragment();
  frag.append(new Option(label, ""));
  for (const row of rows) {
    const option = new Option(row.name, row.name);
    option.dataset.id = row.id;
    frag.append(option);
  }
  select.replaceChildren(frag);
}

export async function setupLocationFilters(
  province: HTMLSelectElement,
  city: HTMLSelectElement,
  district: HTMLSelectElement,
  initial: { province?: string; city?: string; district?: string } = {}
) {
  fill(province, "Semua provinsi");
  fill(city, "Pilih provinsi dahulu");
  fill(district, "Pilih kota/kabupaten dahulu");
  city.disabled = true;
  district.disabled = true;

  let provincesLoaded = false;
  let loadingProvinces: Promise<void> | null = null;

  async function ensureProvinces() {
    if (provincesLoaded) return;
    if (!loadingProvinces) {
      loadingProvinces = getRegions("provinces")
        .then((provinces) => {
          const currentVal = province.value;
          fill(province, "Semua provinsi", provinces);
          if (currentVal) province.value = currentVal;
          provincesLoaded = true;
        })
        .catch(() => {
          loadingProvinces = null;
        });
    }
    await loadingProvinces;
  }

  async function loadDistricts(districtName = "") {
    const id = city.selectedOptions[0]?.dataset.id;
    district.disabled = !id;

    if (!id) {
      fill(district, "Pilih kota/kabupaten dahulu");
      return;
    }

    fill(district, "Memuat kecamatan...");
    const rows = await getRegions(`districts/${id}`);
    fill(district, "Semua kecamatan", rows);
    if (districtName) district.value = districtName;
  }

  async function loadCities(cityName = "", districtName = "") {
    await ensureProvinces();
    const id = province.selectedOptions[0]?.dataset.id;
    fill(district, "Pilih kota/kabupaten dahulu");
    district.disabled = true;
    city.disabled = !id;

    if (!id) {
      fill(city, "Pilih provinsi dahulu");
      return;
    }

    fill(city, "Memuat kota/kabupaten...");
    const rows = await getRegions(`regencies/${id}`);
    fill(city, "Semua kota/kabupaten", rows);

    if (cityName) {
      city.value = cityName;
      if (city.value) await loadDistricts(districtName);
    }
  }

  // Lazy-load provinces only when the user interacts with the dropdown
  const triggerLoad = () => void ensureProvinces();
  province.addEventListener("pointerdown", triggerLoad, { once: true });
  province.addEventListener("focus", triggerLoad, { once: true });

  province.addEventListener("change", () => void loadCities());
  city.addEventListener("change", () => void loadDistricts());

  // Only fetch immediately if URL already has a province filter
  if (initial.province) {
    await ensureProvinces();
    province.value = initial.province;
    if (province.value) {
      await loadCities(initial.city, initial.district);
    }
  }
}
